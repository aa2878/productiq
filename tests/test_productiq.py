import io
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

# Add src to python path
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from analyze_feedback import analyze_feedback, identify_problems
from brief_generator import generate_markdown_brief
from competitive import (
    analyze_competitor_capability,
    fetch_documentation_content,
    is_valid_url,
)
from ingest_feedback import (
    STANDARDIZED_COLUMNS,
    clean_feedback,
    detect_column_mappings,
    extract_rating_and_text,
    generate_ingestion_summary,
    load_excel_file,
    parse_raw_text_reviews,
    standardize_feedback_df,
    validate_feedback,
)
from prioritize import calculate_opportunities, generate_problem_label
from recommendations import generate_product_recommendation
from jira_export import (
    build_jira_issue_payload,
    format_jira_description,
    generate_jira_import_csv,
    map_priority_to_jira,
    send_to_jira_rest_api,
)
from local_llm import (
    check_local_llm_status,
    query_local_llm,
    synthesize_local_problem_statement,
)


class TestProductIQ(unittest.TestCase):

    # =========================================================================
    # INGESTION TESTS (Scenarios 1 - 15)
    # =========================================================================

    def test_01_existing_structured_csv(self):
        """1. Ingest existing structured CSV format."""
        sample_path = Path(__file__).resolve().parents[1] / "data" / "feedback" / "sample_feedback.csv"
        df = pd.read_csv(sample_path)
        mapping, _ = detect_column_mappings(list(df.columns))
        std = standardize_feedback_df(df, mapping)
        validated = validate_feedback(std)
        self.assertEqual(list(validated.columns), STANDARDIZED_COLUMNS)
        self.assertGreater(len(validated), 0)

    def test_02_csv_alternate_column_names(self):
        """2. CSV with alternate column headers."""
        alt_df = pd.DataFrame({
            "review": ["The app is sluggish and freezes."],
            "stars": [1],
            "created_at": ["2026-02-01"],
            "app": ["MobileApp"],
            "channel": ["PlayStore"],
            "review_id": ["rev_100"]
        })
        mapping, _ = detect_column_mappings(list(alt_df.columns))
        self.assertEqual(mapping["feedback"], "review")
        self.assertEqual(mapping["rating"], "stars")
        self.assertEqual(mapping["date"], "created_at")
        std = standardize_feedback_df(alt_df, mapping)
        self.assertEqual(std.iloc[0]["feedback"], "The app is sluggish and freezes.")
        self.assertEqual(std.iloc[0]["rating"], 1.0)
        self.assertEqual(std.iloc[0]["product"], "MobileApp")

    def test_03_csv_only_review_column(self):
        """3. CSV with only a review column."""
        single_col_df = pd.DataFrame({
            "customer_comment": ["Notifications arrive several hours late.", "Search fails completely."]
        })
        mapping, _ = detect_column_mappings(list(single_col_df.columns))
        std = standardize_feedback_df(single_col_df, mapping)
        self.assertEqual(len(std), 2)
        self.assertTrue(std["feedback_id"].is_unique)
        self.assertTrue(std["rating"].isna().all())

    def test_04_excel_spreadsheet(self):
        """4. Ingestion of Excel spreadsheet (.xlsx)."""
        test_df = pd.DataFrame({
            "feedback": ["Calendar crashes repeatedly."],
            "rating": [2]
        })
        # Write to memory buffer as excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            test_df.to_excel(writer, index=False, sheet_name="Reviews")
        buffer.seek(0)

        loaded_df, sheets = load_excel_file(buffer.getvalue())
        self.assertIn("Reviews", sheets)
        self.assertEqual(len(loaded_df), 1)
        self.assertEqual(loaded_df.iloc[0]["feedback"], "Calendar crashes repeatedly.")

    def test_05_plain_text_reviews(self):
        """5. Plain-text reviews parsing."""
        raw_text = (
            "The dashboard is extremely slow.\n"
            "Notifications arrive late.\n"
            "The app crashes when uploading files."
        )
        parsed = parse_raw_text_reviews(raw_text, mode="line")
        self.assertEqual(len(parsed), 3)
        self.assertIn("The dashboard is extremely slow.", parsed["feedback"].tolist())

    def test_06_numbered_reviews(self):
        """6. Numbered reviews parsing and prefix stripping."""
        raw_text = (
            "1. The dashboard is slow.\n"
            "2. The calendar crashes frequently.\n"
            "3) I wish there were more customization options."
        )
        parsed = parse_raw_text_reviews(raw_text, mode="line")
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed.iloc[0]["feedback"], "The dashboard is slow.")
        self.assertEqual(parsed.iloc[1]["feedback"], "The calendar crashes frequently.")
        self.assertEqual(parsed.iloc[2]["feedback"], "I wish there were more customization options.")

    def test_07_explicit_star_ratings(self):
        """7. Reviews containing explicit star and ratio ratings."""
        samples = [
            ("1 star - The application crashes constantly.", 1.0, "The application crashes constantly."),
            ("2 stars - Notifications are delayed.", 2.0, "Notifications are delayed."),
            ("5 stars - Excellent product.", 5.0, "Excellent product."),
            ("3/5 - Dashboard performance needs improvement.", 3.0, "Dashboard performance needs improvement."),
            ("Rating: 2 - Search results are inaccurate.", 2.0, "Search results are inaccurate.")
        ]
        for line, expected_rating, expected_text in samples:
            rating, text = extract_rating_and_text(line)
            self.assertEqual(rating, expected_rating, f"Failed on: {line}")
            self.assertEqual(text, expected_text, f"Failed text extraction on: {line}")

    def test_08_missing_ratings(self):
        """8. Reviews without ratings preserve missing values as None/NaN."""
        raw_text = "I cannot find the export button anywhere."
        parsed = parse_raw_text_reviews(raw_text, mode="line")
        self.assertIsNone(parsed.iloc[0]["rating"])
        summary = generate_ingestion_summary(parsed)
        self.assertEqual(summary["rated_reviews"], 0)
        self.assertEqual(summary["unrated_reviews"], 1)

    def test_09_mixed_rated_unrated_reviews(self):
        """9. Mixed rated and unrated reviews in single dataset."""
        raw_text = (
            "1 star - Application crashes on login.\n"
            "The search functionality is hard to use.\n"
            "4 stars - Good tool overall."
        )
        parsed = parse_raw_text_reviews(raw_text, mode="line")
        self.assertEqual(len(parsed), 3)
        summary = generate_ingestion_summary(parsed)
        self.assertEqual(summary["rated_reviews"], 2)
        self.assertEqual(summary["unrated_reviews"], 1)
        self.assertAlmostEqual(summary["rating_coverage_pct"], 66.7, places=1)

    def test_10_empty_input(self):
        """10. Empty text or dataset handled gracefully."""
        empty_text_df = parse_raw_text_reviews("", mode="line")
        self.assertTrue(empty_text_df.empty)
        cleaned_empty = clean_feedback(pd.DataFrame(columns=STANDARDIZED_COLUMNS))
        self.assertTrue(cleaned_empty.empty)
        summary = generate_ingestion_summary(cleaned_empty)
        self.assertEqual(summary["total_reviews"], 0)

    def test_11_missing_review_column(self):
        """11. Raise clear error when no review column exists."""
        invalid_df = pd.DataFrame({"age": [25, 30], "city": ["NY", "SF"]})
        with self.assertRaises(ValueError):
            standardize_feedback_df(invalid_df)

    def test_12_ambiguous_column_mapping(self):
        """12. Ambiguous column mapping resolved via explicit mapping dict."""
        multi_col_df = pd.DataFrame({
            "notes": ["Customer note"],
            "description": ["Actual complaint about slow speeds"],
            "rating": [2]
        })
        custom_mapping = {"feedback": "description", "rating": "rating"}
        std = standardize_feedback_df(multi_col_df, column_mapping=custom_mapping)
        self.assertEqual(std.iloc[0]["feedback"], "Actual complaint about slow speeds")

    def test_13_duplicate_reviews(self):
        """13. Conservative duplicate review handling."""
        df_dupes = pd.DataFrame({
            "feedback_id": ["1", "2", "3"],
            "product": ["App", "App", "App"],
            "source": ["Web", "Web", "Web"],
            "rating": [1, 1, 2],
            "feedback": ["The app crashes.", "The app crashes.", "Different feedback."],
            "date": ["2026-01-01", "2026-01-01", "2026-01-02"]
        })
        cleaned = clean_feedback(df_dupes)
        self.assertEqual(len(cleaned), 2)

    def test_14_invalid_rating_values(self):
        """14. Invalid ratings (out of 1-5 bounds or non-numeric) coerced to None."""
        raw_df = pd.DataFrame({
            "feedback": ["Issue A", "Issue B", "Issue C"],
            "rating": [99, -5, "not_a_number"]
        })
        std = standardize_feedback_df(raw_df)
        self.assertTrue(std["rating"].isna().all())

    def test_15_multiline_reviews(self):
        """15. Multiline paragraph reviews parsed as unified records."""
        paragraph_text = (
            "The dashboard is extremely slow, especially when loading large projects.\n"
            "It takes over twenty seconds to render anything.\n\n"
            "Notifications arrive several hours late.\n"
            "This caused our team to miss multiple deadlines."
        )
        parsed = parse_raw_text_reviews(paragraph_text, mode="paragraph")
        self.assertEqual(len(parsed), 2)
        self.assertIn("especially when loading large projects", parsed.iloc[0]["feedback"])
        self.assertIn("miss multiple deadlines", parsed.iloc[1]["feedback"])

    # =========================================================================
    # ANALYSIS & PRIORITIZATION TESTS (Scenarios 16 - 20)
    # =========================================================================

    def test_16_single_negative_review(self):
        """16. Dataset with single negative review clusters and scores properly."""
        df = pd.DataFrame([{
            "feedback_id": "1",
            "product": "App",
            "source": "Web",
            "rating": 1.0,
            "feedback": "The application crashes constantly.",
            "date": "2026-01-01"
        }])
        analyzed = analyze_feedback(df)
        self.assertTrue(analyzed.iloc[0]["has_problem"])

        # Mock clustering to avoid slow model load
        clustered = analyzed.copy()
        clustered["cluster_id"] = 0

        opps = calculate_opportunities(clustered, total_feedback=1)
        self.assertEqual(len(opps), 1)
        self.assertEqual(opps.iloc[0]["complaint_count"], 1)
        self.assertEqual(opps.iloc[0]["prevalence_pct"], 100.0)

    def test_17_positive_only_dataset(self):
        """17. Positive-only dataset produces empty problem opportunities."""
        df = pd.DataFrame([{
            "feedback_id": "1",
            "product": "App",
            "source": "Web",
            "rating": 5.0,
            "feedback": "The app is fantastic, fast, and easy to use!",
            "date": "2026-01-01"
        }])
        analyzed = analyze_feedback(df)
        self.assertFalse(analyzed.iloc[0]["has_problem"])
        problems = analyzed[analyzed["has_problem"]]
        opps = calculate_opportunities(problems, total_feedback=1)
        self.assertTrue(opps.empty)

    def test_18_completely_unrated_dataset(self):
        """18. Completely unrated dataset prioritizes via prevalence only."""
        clustered = pd.DataFrame([
            {"cluster_id": 0, "feedback": "Dashboard is slow.", "rating": None},
            {"cluster_id": 0, "feedback": "Loading dashboard takes forever.", "rating": None},
            {"cluster_id": 1, "feedback": "Calendar crashes.", "rating": None}
        ])
        opps = calculate_opportunities(clustered, total_feedback=3)
        self.assertEqual(len(opps), 2)
        # Cluster 0 has 2/3 prevalence = 66.7%
        self.assertEqual(opps.iloc[0]["cluster_id"], 0)
        self.assertEqual(opps.iloc[0]["complaint_count"], 2)
        self.assertEqual(opps.iloc[0]["prevalence_pct"], 66.7)
        self.assertIsNone(opps.iloc[0]["average_rating"])
        self.assertEqual(opps.iloc[0]["scoring_methodology"], "Prevalence Only (Unrated)")

    def test_19_partially_rated_dataset(self):
        """19. Partially rated dataset documents rating coverage and scoring."""
        clustered = pd.DataFrame([
            {"cluster_id": 0, "feedback": "Slow dashboard.", "rating": 2.0},
            {"cluster_id": 0, "feedback": "Laggy views.", "rating": None}
        ])
        opps = calculate_opportunities(clustered, total_feedback=2)
        self.assertEqual(len(opps), 1)
        self.assertEqual(opps.iloc[0]["rating_coverage_pct"], 50.0)
        self.assertEqual(opps.iloc[0]["average_rating"], 2.0)
        self.assertIn("Partial Ratings", opps.iloc[0]["scoring_methodology"])

    def test_20_existing_sample_dataset(self):
        """20. Analysis on existing sample dataset works end-to-end."""
        sample_path = Path(__file__).resolve().parents[1] / "data" / "feedback" / "sample_feedback.csv"
        df = pd.read_csv(sample_path)
        analyzed = analyze_feedback(df)
        problems = analyzed[analyzed["has_problem"]].copy()
        problems["cluster_id"] = [i % 3 for i in range(len(problems))]
        opps = calculate_opportunities(problems, total_feedback=len(df))
        self.assertGreater(len(opps), 0)
        self.assertTrue(all(c in opps.columns for c in ["problem", "priority_score", "scoring_methodology"]))

    # =========================================================================
    # RECOMMENDATION TESTS (Scenarios 21 - 23)
    # =========================================================================

    def test_21_appropriate_recommendations_known_categories(self):
        """21. Generates category-appropriate initiatives and metrics."""
        opp_row = pd.Series({
            "problem": "Slow Dashboard Performance",
            "complaint_count": 5,
            "prevalence_pct": 50.0,
            "average_rating": 2.0,
            "rating_coverage_pct": 100.0,
            "representative_feedback": "Dashboard is slow"
        })
        rec = generate_product_recommendation(opp_row)
        self.assertEqual(rec["archetype"], "Performance")
        self.assertTrue(any("latency" in m.lower() for m in rec["success_metrics"]))
        self.assertTrue(any("caching" in a.lower() for a in rec["actionable_steps"]))

    def test_22_no_fabricated_customer_statistics(self):
        """22. Recommendation claims match actual dataset values exactly."""
        opp_row = pd.Series({
            "problem": "File Upload Crashes",
            "complaint_count": 4,
            "prevalence_pct": 36.4,
            "average_rating": 1.5,
            "rating_coverage_pct": 100.0,
            "representative_feedback": "File uploads crash"
        })
        rec = generate_product_recommendation(opp_row)
        ev = rec["customer_evidence"]
        self.assertEqual(ev["complaint_count"], 4)
        self.assertEqual(ev["prevalence_pct"], 36.4)
        self.assertEqual(ev["average_rating"], 1.5)

    def test_23_correct_attribution_of_supporting_reviews(self):
        """23. Direct quotes are accurately attributed from cluster data."""
        cluster_df = pd.DataFrame({
            "feedback": ["Calendar crashes constantly.", "Calendar freezes upon opening."]
        })
        opp_row = pd.Series({
            "problem": "Calendar Reliability Issues",
            "complaint_count": 2,
            "prevalence_pct": 20.0,
            "average_rating": 1.5,
            "rating_coverage_pct": 100.0,
            "representative_feedback": "Calendar crashes constantly."
        })
        rec = generate_product_recommendation(opp_row, cluster_feedback_df=cluster_df)
        self.assertEqual(len(rec["customer_evidence"]["supporting_quotes"]), 2)
        self.assertIn("Calendar freezes upon opening.", rec["customer_evidence"]["supporting_quotes"])

    # =========================================================================
    # COMPETITIVE INTELLIGENCE TESTS (Scenarios 24 - 29)
    # =========================================================================

    @patch("competitive.requests.get")
    def test_24_valid_documentation_url(self, mock_get):
        """24. Valid documentation URL with relevant text extracts evidence."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.text = "<html><body><h1>Dashboard Customization</h1><p>Users can customize their dashboard widgets with drag-and-drop cards.</p></body></html>"
        mock_get.return_value = mock_resp

        result = analyze_competitor_capability("Competitor X", "Limited Dashboard Customization", "https://competitor.com/docs")
        self.assertIn(result["status"], ["Supported by evidence", "Partially supported"])
        self.assertEqual(result["source_url"], "https://competitor.com/docs")
        self.assertIn("widgets", result["evidence_summary"])

    @patch("competitive.requests.get")
    def test_25_unreachable_url(self, mock_get):
        """25. Unreachable URL returns 'Unable to verify' status without throwing."""
        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("DNS failure")

        result = analyze_competitor_capability("Competitor Y", "Delayed Notifications", "https://unreachable-competitor-site.com")
        self.assertEqual(result["status"], "Unable to verify")
        self.assertIn("Could not verify", result["evidence_summary"])

    @patch("competitive.requests.get")
    def test_26_missing_competitor_evidence(self, mock_get):
        """26. Page found but lacks relevant capability returns 'Not established'."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.text = "<html><body><h1>Pricing Information</h1><p>Our monthly plan starts at ten dollars per user.</p></body></html>"
        mock_get.return_value = mock_resp

        result = analyze_competitor_capability("Competitor Z", "Calendar Reliability Issues", "https://pricing.competitor.com")
        self.assertEqual(result["status"], "Not established")

    def test_27_unsupported_feature_claims(self):
        """27. Missing URL returns 'Not established' rather than claiming feature is missing."""
        result = analyze_competitor_capability("Competitor A", "File Upload Crashes", documentation_url=None)
        self.assertEqual(result["status"], "Not established")
        self.assertIn("No documentation URL", result["evidence_summary"])

    @patch("competitive.requests.get")
    def test_28_source_attribution(self, mock_get):
        """28. Findings include competitor name, retrieval date, and source URL."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.text = "<html><body><p>Instant real-time sync across devices.</p></body></html>"
        mock_get.return_value = mock_resp

        url = "https://example.com/sync"
        result = analyze_competitor_capability("SyncApp", "Slow Application Performance", url)
        self.assertEqual(result["competitor"], "SyncApp")
        self.assertEqual(result["source_url"], url)
        self.assertTrue(len(result["retrieval_date"]) == 10)  # YYYY-MM-DD

    @patch("competitive.requests.get")
    def test_29_network_timeout(self, mock_get):
        """29. Network timeout returns 'Unable to verify' gracefully."""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        result = analyze_competitor_capability("SlowComp", "Search Errors", "https://timeout.com")
        self.assertEqual(result["status"], "Unable to verify")
        self.assertIn("timed out", result["evidence_summary"])

    # =========================================================================
    # EXPORT TESTS (Scenarios 30 - 31)
    # =========================================================================

    def test_30_csv_export(self):
        """30. Opportunities CSV export maintains complete column structure."""
        opps = pd.DataFrame([{
            "cluster_id": 1,
            "problem": "Slow Dashboard",
            "complaint_count": 5,
            "prevalence_pct": 50.0,
            "average_rating": 2.0,
            "rating_coverage_pct": 100.0,
            "priority_score": 62.5,
            "scoring_methodology": "Prevalence + Dissatisfaction (Fully Rated)"
        }])
        csv_str = opps.to_csv(index=False)
        reloaded = pd.read_csv(io.StringIO(csv_str))
        self.assertEqual(len(reloaded), 1)
        self.assertEqual(reloaded.iloc[0]["problem"], "Slow Dashboard")

    def test_31_product_brief_export(self):
        """31. Generates complete 12-section Product Opportunity Brief."""
        opp_row = pd.Series({
            "problem": "Limited Dashboard Customization",
            "complaint_count": 3,
            "prevalence_pct": 30.0,
            "average_rating": 2.5,
            "rating_coverage_pct": 100.0,
            "representative_feedback": "Need custom cards",
            "priority_score": 45.0,
            "scoring_methodology": "Prevalence + Dissatisfaction (Fully Rated)"
        })
        rec = generate_product_recommendation(opp_row)
        brief = generate_markdown_brief(rec, opp_row, competitive_findings=None, product_name="TaskFlow")

        # Verify all 12 sections are present
        for i in range(1, 13):
            self.assertIn(f"## {i}.", brief, f"Missing section ## {i} in Product Brief")

        # Verify no placeholder unperformed competitive text
        self.assertIn("Competitive research has not been performed", brief)

    # =========================================================================
    # JIRA INTEGRATION & LOCAL LLM TESTS (Scenarios 32 - 37)
    # =========================================================================

    def test_32_map_priority_to_jira(self):
        """32. Maps numeric priority scores to Jira standard priorities."""
        self.assertEqual(map_priority_to_jira(75), "Highest")
        self.assertEqual(map_priority_to_jira(50), "High")
        self.assertEqual(map_priority_to_jira(35), "Medium")
        self.assertEqual(map_priority_to_jira(15), "Low")
        self.assertEqual(map_priority_to_jira("invalid"), "Medium")

    def test_33_jira_payload_structure(self):
        """33. Constructs valid Jira REST API payload."""
        opp_row = pd.Series({
            "problem": "Calendar Reliability Issues",
            "complaint_count": 2,
            "prevalence_pct": 20.0,
            "priority_score": 53.8,
            "average_rating": 1.5,
            "rating_coverage_pct": 100.0,
            "scoring_methodology": "Prevalence + Dissatisfaction"
        })
        rec = generate_product_recommendation(opp_row)
        payload = build_jira_issue_payload("ENG", rec, opp_row, issue_type="Epic")

        fields = payload["fields"]
        self.assertEqual(fields["project"]["key"], "ENG")
        self.assertEqual(fields["summary"], "[ProductIQ] Calendar Reliability Issues")
        self.assertEqual(fields["issuetype"]["name"], "Epic")
        self.assertEqual(fields["priority"]["name"], "High")
        self.assertIn("productiq", fields["labels"])
        self.assertIn("h2. ProductIQ Opportunity", fields["description"])

    def test_34_jira_import_csv(self):
        """34. Generates standard Jira External System Import CSV."""
        opps = pd.DataFrame([{
            "cluster_id": 1,
            "problem": "Delayed Notifications",
            "complaint_count": 2,
            "prevalence_pct": 20.0,
            "priority_score": 35.0,
            "average_rating": 3.0,
            "rating_coverage_pct": 100.0,
            "scoring_methodology": "Prevalence + Dissatisfaction"
        }])
        recs = {"Delayed Notifications": generate_product_recommendation(opps.iloc[0])}
        csv_data = generate_jira_import_csv(opps, recs, project_key="PROD", issue_type="Epic")

        reloaded = pd.read_csv(io.StringIO(csv_data))
        self.assertIn("Summary", reloaded.columns)
        self.assertIn("Issue Type", reloaded.columns)
        self.assertIn("Project Key", reloaded.columns)
        self.assertEqual(reloaded.iloc[0]["Summary"], "[ProductIQ] Delayed Notifications")
        self.assertEqual(reloaded.iloc[0]["Priority"], "Medium")

    @patch("jira_export.requests.post")
    def test_35_send_to_jira_rest_api_success(self, mock_post):
        """35. Successful Jira REST API issue creation."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": "10001", "key": "PROD-101"}
        mock_post.return_value = mock_resp

        opp_row = pd.Series({"problem": "Slow App", "priority_score": 50})
        rec = generate_product_recommendation(opp_row)
        success, msg = send_to_jira_rest_api(
            "https://test.atlassian.net", "pm@test.com", "token123", "PROD", rec, opp_row
        )
        self.assertTrue(success)
        self.assertIn("PROD-101", msg)

    @patch("jira_export.requests.post")
    def test_36_send_to_jira_rest_api_failure(self, mock_post):
        """36. Graceful failure on Jira unreachable or error."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Could not reach host")

        opp_row = pd.Series({"problem": "Slow App", "priority_score": 50})
        rec = generate_product_recommendation(opp_row)
        success, msg = send_to_jira_rest_api(
            "https://invalid.atlassian.net", "pm@test.com", "token123", "PROD", rec, opp_row
        )
        self.assertFalse(success)
        self.assertIn("Could not connect to Jira host", msg)

    def test_37_local_llm_status_and_fallback(self):
        """37. Local LLM checks offline status cleanly and returns fallback."""
        status = check_local_llm_status("http://localhost:99999", timeout=1)
        self.assertFalse(status["available"])
        self.assertEqual(status["models"], [])

        # Offline synthesis returns None without raising
        res = synthesize_local_problem_statement(
            "Test", ["Quote 1"], endpoint="http://localhost:99999"
        )
        self.assertIsNone(res)

    # =========================================================================
    # CLAUDE SKILL & CLI TESTS (Scenarios 38 - 39)
    # =========================================================================

    def test_38_skill_yaml_frontmatter_and_paths(self):
        """38. Validates .claude/skills/productiq/SKILL.md format and paths."""
        skill_path = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "productiq" / "SKILL.md"
        self.assertTrue(skill_path.exists(), "SKILL.md does not exist")

        content = skill_path.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---"), "SKILL.md must start with YAML frontmatter delimiter '---'")

        # Verify YAML frontmatter presence
        parts = content.split("---", 2)
        self.assertGreaterEqual(len(parts), 3, "Invalid frontmatter structure")
        frontmatter = parts[1]
        self.assertIn("name: productiq", frontmatter)
        self.assertIn("description:", frontmatter)

        # Verify referenced paths exist
        repo_root = Path(__file__).resolve().parents[1]
        self.assertTrue((repo_root / "src" / "cli.py").exists(), "src/cli.py must exist")
        self.assertTrue((repo_root / ".claude" / "skills" / "productiq" / "scripts" / "run.py").exists(), "scripts/run.py must exist")

    def test_39_cli_analysis_pipeline(self):
        """39. Validates run_analysis_pipeline programmatic entry point."""
        from cli import run_analysis_pipeline
        raw_text = "1 star - The upload crashes.\n2 stars - Upload is broken."
        result = run_analysis_pipeline(raw_text=raw_text, product_name="TestApp")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["product"], "TestApp")
        self.assertGreater(result["ingestion_summary"]["total_reviews"], 0)


if __name__ == "__main__":
    unittest.main()
