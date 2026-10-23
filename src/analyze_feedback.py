import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE_DIR / "data" / "processed" / "clean_feedback.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "analyzed_feedback.csv"


PROBLEM_CATEGORIES = {
    "Performance": [
        "slow", "load", "loading", "lag", "speed"
    ],
    "Usability": [
        "confusing", "difficult", "hard to use",
        "complicated", "navigate"
    ],
    "Notifications": [
        "notification", "alert", "reminder"
    ],
    "Reliability": [
        "crash", "crashes", "bug", "error", "freeze"
    ],
    "Missing Functionality": [
        "wish", "customize", "missing",
        "limited", "feature"
    ]
}


def identify_problems(text):
    """
    Identify problem categories mentioned in customer feedback.
    """

    text = str(text).lower()

    identified = []

    for category, keywords in PROBLEM_CATEGORIES.items():

        if any(keyword in text for keyword in keywords):
            identified.append(category)

    return identified


def analyze_feedback(df):
    """
    Add identified problem categories to each feedback record.
    """

    df = df.copy()

    df["problem_categories"] = df["feedback"].apply(
        identify_problems
    )

    df["has_problem"] = df["problem_categories"].apply(
        lambda categories: len(categories) > 0
    )

    return df


def main():

    print("\nPRODUCTIQ — FEEDBACK ANALYSIS\n")

    df = pd.read_csv(INPUT_FILE)

    analyzed = analyze_feedback(df)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    analyzed.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print(f"Analyzed {len(analyzed)} feedback records.\n")

    for _, row in analyzed.iterrows():

        print(f"Feedback: {row['feedback']}")

        print(
            f"Problems: {row['problem_categories']}\n"
        )

    print(f"Results saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()