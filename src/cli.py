import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Ensure src directory is in sys.path
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from analyze_feedback import analyze_feedback
from brief_generator import generate_markdown_brief
from cluster_feedback import cluster_feedback
from competitive import analyze_competitor_capability
from ingest_feedback import (
    STANDARDIZED_COLUMNS,
    clean_feedback,
    detect_column_mappings,
    generate_ingestion_summary,
    load_excel_file,
    parse_raw_text_reviews,
    standardize_feedback_df,
)
from jira_export import (
    build_jira_issue_payload,
    generate_jira_import_csv,
    map_priority_to_jira,
)
from prioritize import calculate_opportunities
from recommendations import generate_product_recommendation

BASE_DIR = SRC_DIR.parent
DEFAULT_SAMPLE_FILE = BASE_DIR / "data" / "feedback" / "sample_feedback.csv"
DEFAULT_OUTPUT_DIR = BASE_DIR / "data" / "processed"


def run_analysis_pipeline(
    input_source: Optional[str] = None,
    raw_text: Optional[str] = None,
    mode: str = "auto",
    product_name: str = "Our Product",
    output_dir: Path = DEFAULT_OUTPUT_DIR
) -> Dict[str, Any]:
    """
    Run end-to-end feedback ingestion, semantic clustering, and prioritization.
    Returns structured results dictionary.
    """
    # 1. Ingestion
    if raw_text and raw_text.strip():
        raw_df = parse_raw_text_reviews(
            raw_text,
            mode=mode,
            default_product=product_name
        )
        standardized_df = raw_df
    elif input_source:
        source_path = Path(input_source)
        if not source_path.exists():
            raise FileNotFoundError(f"Input file not found: {source_path}")

        ext = source_path.suffix.lower()
        if ext == ".csv":
            raw_df = pd.read_csv(source_path)
            mapping, _ = detect_column_mappings(list(raw_df.columns))
            standardized_df = standardize_feedback_df(raw_df, mapping, default_product=product_name)
        elif ext == ".xlsx":
            raw_df, _ = load_excel_file(source_path)
            mapping, _ = detect_column_mappings(list(raw_df.columns))
            standardized_df = standardize_feedback_df(raw_df, mapping, default_product=product_name)
        elif ext == ".txt":
            with open(source_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            standardized_df = parse_raw_text_reviews(content, mode=mode, default_product=product_name)
        else:
            raise ValueError(f"Unsupported file format '{ext}'. Must be .csv, .xlsx, or .txt")
    else:
        # Default to sample feedback
        if not DEFAULT_SAMPLE_FILE.exists():
            raise FileNotFoundError(f"Sample feedback file not found at {DEFAULT_SAMPLE_FILE}")
        raw_df = pd.read_csv(DEFAULT_SAMPLE_FILE)
        mapping, _ = detect_column_mappings(list(raw_df.columns))
        standardized_df = standardize_feedback_df(raw_df, mapping, default_product=product_name)

    # 2. Cleaning
    cleaned_df = clean_feedback(standardized_df)
    ingestion_summary = generate_ingestion_summary(cleaned_df)

    if cleaned_df.empty:
        return {
            "status": "empty",
            "summary": ingestion_summary,
            "opportunities": [],
            "records_analyzed": 0
        }

    # 3. Categorization
    analyzed_df = analyze_feedback(cleaned_df)

    # 4. Semantic Clustering on CPU
    clustered_df = cluster_feedback(analyzed_df)

    # 5. Rating-Independent Prioritization
    if clustered_df.empty:
        opportunities_df = pd.DataFrame()
    else:
        opportunities_df = calculate_opportunities(clustered_df, total_feedback=len(cleaned_df))

    # Save to disk
    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(output_dir / "clean_feedback.csv", index=False)
    analyzed_df.to_csv(output_dir / "analyzed_feedback.csv", index=False)
    if not clustered_df.empty:
        clustered_df.to_csv(output_dir / "clustered_feedback.csv", index=False)
    if not opportunities_df.empty:
        opportunities_df.to_csv(output_dir / "product_opportunities.csv", index=False)

    opps_list = opportunities_df.to_dict(orient="records") if not opportunities_df.empty else []

    return {
        "status": "success",
        "product": product_name,
        "ingestion_summary": ingestion_summary,
        "opportunities_count": len(opps_list),
        "opportunities": opps_list
    }


def main():
    parser = argparse.ArgumentParser(
        description="ProductIQ — Customer Feedback Intelligence CLI Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -------------------------------------------------------------------------
    # Command: analyze
    # -------------------------------------------------------------------------
    analyze_parser = subparsers.add_parser("analyze", help="Ingest feedback and discover prioritized opportunities")
    analyze_parser.add_argument("input", nargs="?", help="Path to input feedback file (.csv, .xlsx, .txt)")
    analyze_parser.add_argument("--text", help="Raw feedback string to parse (alternative to file input)")
    analyze_parser.add_argument("--mode", choices=["auto", "line", "paragraph"], default="auto", help="Text segmentation strategy")
    analyze_parser.add_argument("--product", default="Our Product", help="Product name under review")
    analyze_parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for processed CSVs")
    analyze_parser.add_argument("--format", choices=["json", "text", "markdown"], default="text", help="Output display format")

    # -------------------------------------------------------------------------
    # Command: recommend
    # -------------------------------------------------------------------------
    rec_parser = subparsers.add_parser("recommend", help="Generate PM recommendations for a specific opportunity")
    rec_parser.add_argument("--cluster-id", type=int, help="Cluster ID of the opportunity")
    rec_parser.add_argument("--problem", help="Exact or partial problem title to inspect")
    rec_parser.add_argument("--processed-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory of processed files")
    rec_parser.add_argument("--format", choices=["json", "text"], default="text")

    # -------------------------------------------------------------------------
    # Command: competitive
    # -------------------------------------------------------------------------
    comp_parser = subparsers.add_parser("competitive", help="Verify capability evidence in competitor documentation")
    comp_parser.add_argument("--problem", required=True, help="Customer problem / capability to benchmark")
    comp_parser.add_argument("--competitor", default="Competitor", help="Competitor brand name")
    comp_parser.add_argument("--url", help="Public documentation URL to inspect")
    comp_parser.add_argument("--format", choices=["json", "text"], default="text")

    # -------------------------------------------------------------------------
    # Command: brief
    # -------------------------------------------------------------------------
    brief_parser = subparsers.add_parser("brief", help="Generate executive 12-section Product Opportunity Brief")
    brief_parser.add_argument("--cluster-id", type=int, help="Cluster ID of the opportunity")
    brief_parser.add_argument("--problem", help="Problem title to generate brief for")
    brief_parser.add_argument("--product", default="Our Product", help="Target product name")
    brief_parser.add_argument("--competitor", help="Competitor name for verified context")
    brief_parser.add_argument("--competitor-url", help="Competitor documentation URL")
    brief_parser.add_argument("--output", help="Optional path to save markdown file")
    brief_parser.add_argument("--processed-dir", default=str(DEFAULT_OUTPUT_DIR))

    # -------------------------------------------------------------------------
    # Command: export-jira
    # -------------------------------------------------------------------------
    jira_parser = subparsers.add_parser("export-jira", help="Export opportunities to Jira Import CSV or JSON")
    jira_parser.add_argument("--project", default="PROD", help="Jira project key (e.g. PROD)")
    jira_parser.add_argument("--type", default="Epic", choices=["Epic", "Story", "Task"], help="Jira issue type")
    jira_parser.add_argument("--format", choices=["csv", "json"], default="csv", help="Jira export format")
    jira_parser.add_argument("--output", help="File path to save the Jira export")
    jira_parser.add_argument("--processed-dir", default=str(DEFAULT_OUTPUT_DIR))

    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Execute: analyze
    # -------------------------------------------------------------------------
    if args.command == "analyze":
        out_dir = Path(args.output_dir)
        results = run_analysis_pipeline(
            input_source=args.input,
            raw_text=args.text,
            mode=args.mode,
            product_name=args.product,
            output_dir=out_dir
        )

        if args.format == "json":
            print(json.dumps(results, indent=2))
        else:
            summary = results["ingestion_summary"]
            print("\n==================================================")
            print(f" PRODUCTIQ ANALYSIS REPORT — {results['product'].upper()}")
            print("==================================================")
            print(f"Total Feedback Records:  {summary['total_reviews']}")
            print(f"Rating Coverage:         {summary['rating_coverage_pct']}% ({summary['rated_reviews']} rated / {summary['unrated_reviews']} unrated)")
            print(f"Average Rating:          {summary['average_rating'] or 'Unrated'}")
            print(f"Identified Opportunities:{results['opportunities_count']}")
            print("--------------------------------------------------")

            if not results["opportunities"]:
                print("No recurring problem clusters identified.")
            else:
                for idx, opp in enumerate(results["opportunities"], start=1):
                    rating_disp = f"{opp['average_rating']}/5.0" if opp['average_rating'] is not None else "Unrated"
                    print(f"{idx}. {opp['problem']} [Cluster {opp['cluster_id']}]")
                    print(f"   Priority Score: {opp['priority_score']}/100 | Volume: {opp['complaint_count']} ({opp['prevalence_pct']}%)")
                    print(f"   Rating: {rating_disp} (Coverage: {opp['rating_coverage_pct']}%)")
                    print(f"   Methodology: {opp['scoring_methodology']}")
                    print(f"   Quote: \"{opp['representative_feedback']}\"\n")

    # -------------------------------------------------------------------------
    # Execute: recommend
    # -------------------------------------------------------------------------
    elif args.command == "recommend":
        proc_dir = Path(args.processed_dir)
        opp_file = proc_dir / "product_opportunities.csv"
        clust_file = proc_dir / "clustered_feedback.csv"

        if not opp_file.exists():
            print(f"Error: Processed opportunities file not found at {opp_file}. Run 'analyze' first.", file=sys.stderr)
            sys.exit(1)

        opps_df = pd.read_csv(opp_file)
        clust_df = pd.read_csv(clust_file) if clust_file.exists() else pd.DataFrame()

        if args.cluster_id is not None:
            match = opps_df[opps_df["cluster_id"] == args.cluster_id]
        elif args.problem:
            match = opps_df[opps_df["problem"].str.contains(args.problem, case=False, na=False)]
        else:
            match = opps_df.head(1)

        if match.empty:
            print("No matching opportunity found.", file=sys.stderr)
            sys.exit(1)

        opp_row = match.iloc[0]
        cid = opp_row["cluster_id"]
        c_reviews = clust_df[clust_df["cluster_id"] == cid] if not clust_df.empty else pd.DataFrame()

        rec = generate_product_recommendation(opp_row, c_reviews)

        if args.format == "json":
            print(json.dumps(rec, indent=2))
        else:
            print(f"\nSTRATEGIC RECOMMENDATION: {rec['problem_title'].upper()}")
            print(f"Archetype: {rec['archetype']} | Priority: {opp_row['priority_score']}/100")
            print(f"\nProblem Statement:\n{rec['problem_statement']}\n")
            print("Potential Causes (Engineering Hypotheses):")
            for c in rec["potential_causes"]:
                print(f"  - {c}")
            print("\nRecommended Product Initiatives:")
            for i in rec["recommended_initiatives"]:
                print(f"  - {i}")
            print("\nActionable Steps:")
            for s in rec["actionable_steps"]:
                print(f"  - {s}")
            print("\nSuccess Metrics:")
            for m in rec["success_metrics"]:
                print(f"  - {m}")
            print(f"\nProposed MVP Scope:\n{rec['mvp_scope']}\n")

    # -------------------------------------------------------------------------
    # Execute: competitive
    # -------------------------------------------------------------------------
    elif args.command == "competitive":
        finding = analyze_competitor_capability(
            competitor_name=args.competitor,
            problem_title=args.problem,
            documentation_url=args.url
        )

        if args.format == "json":
            print(json.dumps(finding, indent=2))
        else:
            print(f"\nCOMPETITIVE BENCHMARK: {finding['competitor']}")
            print(f"Problem Compared:    {finding['problem_compared']}")
            print(f"Status:              [{finding['status'].upper()}]")
            print(f"Evidence Summary:    {finding['evidence_summary']}")
            print(f"Source URL:          {finding['source_url']}")
            print(f"Verification Date:   {finding['retrieval_date']}\n")

    # -------------------------------------------------------------------------
    # Execute: brief
    # -------------------------------------------------------------------------
    elif args.command == "brief":
        proc_dir = Path(args.processed_dir)
        opp_file = proc_dir / "product_opportunities.csv"
        clust_file = proc_dir / "clustered_feedback.csv"

        if not opp_file.exists():
            print(f"Error: {opp_file} not found. Run 'analyze' first.", file=sys.stderr)
            sys.exit(1)

        opps_df = pd.read_csv(opp_file)
        clust_df = pd.read_csv(clust_file) if clust_file.exists() else pd.DataFrame()

        if args.cluster_id is not None:
            match = opps_df[opps_df["cluster_id"] == args.cluster_id]
        elif args.problem:
            match = opps_df[opps_df["problem"].str.contains(args.problem, case=False, na=False)]
        else:
            match = opps_df.head(1)

        if match.empty:
            print("No matching opportunity found.", file=sys.stderr)
            sys.exit(1)

        opp_row = match.iloc[0]
        cid = opp_row["cluster_id"]
        c_reviews = clust_df[clust_df["cluster_id"] == cid] if not clust_df.empty else pd.DataFrame()

        rec = generate_product_recommendation(opp_row, c_reviews)

        comp_findings = []
        if args.competitor:
            c_find = analyze_competitor_capability(args.competitor, opp_row["problem"], args.competitor_url)
            comp_findings.append(c_find)

        brief_md = generate_markdown_brief(
            recommendation=rec,
            opportunity_row=opp_row,
            competitive_findings=comp_findings,
            product_name=args.product
        )

        if args.output:
            out_file = Path(args.output)
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(brief_md)
            print(f"Product Opportunity Brief saved to {out_file}")
        else:
            print(brief_md)

    # -------------------------------------------------------------------------
    # Execute: export-jira
    # -------------------------------------------------------------------------
    elif args.command == "export-jira":
        proc_dir = Path(args.processed_dir)
        opp_file = proc_dir / "product_opportunities.csv"
        clust_file = proc_dir / "clustered_feedback.csv"

        if not opp_file.exists():
            print(f"Error: {opp_file} not found. Run 'analyze' first.", file=sys.stderr)
            sys.exit(1)

        opps_df = pd.read_csv(opp_file)
        clust_df = pd.read_csv(clust_file) if clust_file.exists() else pd.DataFrame()

        recs_map = {}
        for _, r in opps_df.iterrows():
            cid = r["cluster_id"]
            c_revs = clust_df[clust_df["cluster_id"] == cid] if not clust_df.empty else pd.DataFrame()
            recs_map[str(r["problem"])] = generate_product_recommendation(r, c_revs)

        if args.format == "csv":
            csv_content = generate_jira_import_csv(
                opportunities_df=opps_df,
                recommendations_map=recs_map,
                project_key=args.project,
                issue_type=args.type
            )
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(csv_content)
                print(f"Saved Jira Import CSV to {args.output}")
            else:
                print(csv_content)
        else:
            # JSON format
            first_opp = opps_df.iloc[0]
            rec = recs_map.get(str(first_opp["problem"]), {})
            payload = build_jira_issue_payload(
                project_key=args.project,
                recommendation=rec,
                opportunity_row=first_opp,
                issue_type=args.type
            )
            json_str = json.dumps(payload, indent=2)
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(json_str)
                print(f"Saved Jira Issue JSON to {args.output}")
            else:
                print(json_str)


if __name__ == "__main__":
    main()
