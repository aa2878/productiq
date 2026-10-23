import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE_DIR / "data" / "processed" / "clustered_feedback.csv"
ALL_FEEDBACK_FILE = BASE_DIR / "data" / "processed" / "clean_feedback.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "product_opportunities.csv"


PROBLEM_LABEL_RULES = [
    (
        ["upload", "document", "attachment", "file"],
        ["crash", "error", "fail", "broken"],
        "File Upload Crashes"
    ),
    (
        ["calendar"],
        ["crash", "freeze", "error", "broken"],
        "Calendar Reliability Issues"
    ),
    (
        ["login", "auth", "sign in", "password", "2fa"],
        ["fail", "error", "broken", "unable", "cannot", "issue"],
        "User Authentication Failures"
    ),
    (
        ["billing", "payment", "invoice", "charge", "subscription"],
        ["error", "fail", "wrong", "issue", "bug", "double"],
        "Billing & Payment Inaccuracies"
    ),
    (
        ["dashboard"],
        ["slow", "load", "lag", "speed", "forever"],
        "Slow Dashboard Performance"
    ),
    (
        ["app", "application", "mobile"],
        ["slow", "load", "lag", "speed"],
        "Slow Application Performance"
    ),
    (
        ["notification", "alert", "reminder"],
        ["late", "delay", "hour", "minute"],
        "Delayed Notifications"
    ),
    (
        ["setting", "menu"],
        ["confusing", "difficult", "navigate", "complicated"],
        "Confusing Settings Navigation"
    ),
    (
        ["appointment", "scheduling", "schedule"],
        ["confusing", "difficult", "navigate", "complicated"],
        "Confusing Appointment Scheduling"
    ),
    (
        ["dashboard"],
        ["customize", "customization", "limited", "wish"],
        "Limited Dashboard Customization"
    ),
    (
        ["report", "reporting"],
        ["customize", "customization", "limited", "wish"],
        "Limited Reporting Customization"
    ),
    (
        ["report", "export", "pdf", "csv", "excel"],
        ["export", "pdf", "download", "missing"],
        "Missing Report Export Options"
    ),
    (
        ["search", "searching"],
        ["error", "broken", "fail", "crash", "inaccurate", "wrong"],
        "Search Functionality Errors"
    ),
    (
        ["offline"],
        ["wish", "missing", "need", "mode"],
        "Missing Offline Functionality"
    ),
]

GENERAL_PROBLEM_RULES = [
    (
        ["crash", "freeze", "broken", "error", "bug"],
        "Application Reliability Issues"
    ),
    (
        ["slow", "lag", "speed", "loading", "forever"],
        "Slow Application Performance"
    ),
    (
        ["notification", "alert", "reminder"],
        "Notification Issues"
    ),
    (
        ["confusing", "difficult", "navigate", "complicated", "hard to use"],
        "Usability Issues"
    ),
    (
        ["wish", "missing", "limited", "customize", "customization"],
        "Missing or Limited Functionality"
    ),
    (
        ["search", "find", "filter"],
        "Search & Discovery Issues"
    ),
]


def normalize_text(text: Any) -> str:
    """Normalize text for consistent keyword matching."""
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def contains_keyword(text: str, keywords: List[str]) -> bool:
    """Return True if any keyword is present in text."""
    return any(keyword in text for keyword in keywords)


def parse_categories(value: Any) -> List[str]:
    """Safely convert stored category strings into lists."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, SyntaxError):
            pass
    return []


def generate_problem_label(group: pd.DataFrame) -> str:
    """
    Generate an informative problem label from reviews in a problem cluster.
    Uses deterministic rule matching and fallback to category modes.
    """
    feedback_text = " ".join(group["feedback"].fillna("").astype(str).tolist())
    text = normalize_text(feedback_text)

    # 1. Specific problem rules
    for feature_keywords, issue_keywords, label in PROBLEM_LABEL_RULES:
        if contains_keyword(text, feature_keywords) and contains_keyword(text, issue_keywords):
            return label

    # 2. General problem rules
    for keywords, label in GENERAL_PROBLEM_RULES:
        if contains_keyword(text, keywords):
            return label

    # 3. Fallback to detected problem categories
    if "problem_categories" in group.columns:
        categories = []
        for value in group["problem_categories"]:
            categories.extend(parse_categories(value))
        if categories:
            most_common = pd.Series(categories).mode()
            if not most_common.empty:
                category = str(most_common.iloc[0])
                category_labels = {
                    "Performance": "Performance Issues",
                    "Usability": "Usability Issues",
                    "Notifications": "Notification Issues",
                    "Reliability": "Application Reliability Issues",
                    "Missing Functionality": "Missing Functionality"
                }
                return category_labels.get(category, f"{category} Issues")

    return "Uncategorized Customer Problem"


def calculate_opportunities(df: pd.DataFrame, total_feedback: int) -> pd.DataFrame:
    """
    Summarize recurring customer problems and calculate priority scores.

    Supports:
      - Fully rated datasets: 50% complaint prevalence + 50% dissatisfaction
      - Completely unrated datasets: 100% complaint prevalence (transparent ranking)
      - Partially rated datasets: prevalence ranking with explicit rating coverage
    """
    columns = [
        "cluster_id",
        "problem",
        "representative_feedback",
        "complaint_count",
        "prevalence_pct",
        "average_rating",
        "rating_coverage_pct",
        "dissatisfaction_score",
        "priority_score",
        "scoring_methodology"
    ]

    if total_feedback <= 0:
        raise ValueError("Total feedback must be greater than zero.")

    if df.empty or "cluster_id" not in df.columns:
        return pd.DataFrame(columns=columns)

    opportunities = []

    for cluster_id, group in df.groupby("cluster_id"):
        count = len(group)
        prevalence = count / total_feedback
        prevalence_pct = round(prevalence * 100, 1)

        # Handle ratings safely
        valid_ratings = pd.Series(dtype=float)
        if "rating" in group.columns:
            numeric_ratings = pd.to_numeric(group["rating"], errors="coerce").dropna()
            valid_ratings = numeric_ratings[(numeric_ratings >= 1.0) & (numeric_ratings <= 5.0)]

        rated_count = len(valid_ratings)
        coverage_pct = round((rated_count / count) * 100, 1)

        if rated_count == count and count > 0:
            # Fully rated cluster
            avg_rating = round(float(valid_ratings.mean()), 2)
            dissatisfaction = (5.0 - avg_rating) / 4.0
            dissatisfaction_score = round(dissatisfaction * 100, 1)
            priority_score = round((0.5 * prevalence + 0.5 * dissatisfaction) * 100, 1)
            scoring_methodology = "Prevalence + Dissatisfaction (Fully Rated)"
        elif rated_count == 0:
            # Completely unrated cluster
            avg_rating = None
            dissatisfaction_score = None
            priority_score = round(prevalence * 100, 1)
            scoring_methodology = "Prevalence Only (Unrated)"
        else:
            # Partially rated cluster: conservative prevalence ranking
            avg_rating = round(float(valid_ratings.mean()), 2)
            dissatisfaction = (5.0 - avg_rating) / 4.0
            dissatisfaction_score = round(dissatisfaction * 100, 1)
            priority_score = round(prevalence * 100, 1)
            scoring_methodology = f"Prevalence Only (Partial Ratings: {coverage_pct}% coverage)"

        problem_label = generate_problem_label(group)
        representative_feedback = group.iloc[0]["feedback"]

        opportunities.append({
            "cluster_id": cluster_id,
            "problem": problem_label,
            "representative_feedback": representative_feedback,
            "complaint_count": count,
            "prevalence_pct": prevalence_pct,
            "average_rating": avg_rating,
            "rating_coverage_pct": coverage_pct,
            "dissatisfaction_score": dissatisfaction_score,
            "priority_score": priority_score,
            "scoring_methodology": scoring_methodology
        })

    if not opportunities:
        return pd.DataFrame(columns=columns)

    results = pd.DataFrame(opportunities)
    return results.sort_values(by="priority_score", ascending=False).reset_index(drop=True)


def main():
    print("\nPRODUCTIQ — PRODUCT OPPORTUNITY ANALYSIS\n")

    if not INPUT_FILE.exists() or not ALL_FEEDBACK_FILE.exists():
        print("Required processed files not found. Run ingestion, analysis, and clustering first.")
        return

    df = pd.read_csv(INPUT_FILE)
    all_feedback = pd.read_csv(ALL_FEEDBACK_FILE)

    if df.empty or all_feedback.empty:
        print("No feedback available for analysis.")
        return

    opportunities = calculate_opportunities(df, total_feedback=len(all_feedback))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    opportunities.to_csv(OUTPUT_FILE, index=False)

    print("RANKED CUSTOMER PROBLEMS\n")
    for rank, (_, row) in enumerate(opportunities.iterrows(), start=1):
        print(f"{rank}. {row['problem']}")
        print(f"   Example: {row['representative_feedback']}")
        print(f"   Complaints: {row['complaint_count']} ({row['prevalence_pct']}%)")
        print(f"   Avg Rating: {row['average_rating']} (Coverage: {row['rating_coverage_pct']}%)")
        print(f"   Priority Score: {row['priority_score']}/100")
        print(f"   Methodology: {row['scoring_methodology']}\n")

    print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
