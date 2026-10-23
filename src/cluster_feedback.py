import os
import ast
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

# Prevent Hugging Face Hub retry delays in offline / local environments
os.environ.setdefault("HF_HUB_OFFLINE", "1")


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE_DIR / "data" / "processed" / "analyzed_feedback.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "clustered_feedback.csv"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

SIMILARITY_THRESHOLD = 0.60
CATEGORY_SIMILARITY_THRESHOLD = 0.45


def parse_categories(value):
    """
    Convert stored category strings back into Python lists.
    """

    if isinstance(value, list):
        return value

    try:
        result = ast.literal_eval(str(value))

        return result if isinstance(result, list) else []

    except (ValueError, SyntaxError):
        return []


@lru_cache(maxsize=1)
def load_model():
    """
    Load the semantic similarity model once per process.

    Force CPU processing to avoid Apple Silicon
    Metal GPU crashes.
    """

    print("Loading semantic similarity model on CPU...")

    os.environ["HF_HUB_OFFLINE"] = "1"

    try:
        model = SentenceTransformer(
            MODEL_NAME,
            device="cpu",
            local_files_only=True
        )
    except Exception:
        model = SentenceTransformer(
            MODEL_NAME,
            device="cpu"
        )

    return model


def cluster_feedback(df):
    """
    Group semantically similar customer complaints.

    Uses sentence embeddings and shared problem categories
    to identify reviews describing similar customer issues.
    """

    df = df.copy()

    df["problem_categories"] = df["problem_categories"].apply(
        parse_categories
    )

    # Only analyze feedback identified as containing problems.
    problems = df[
        df["has_problem"].astype(str).str.lower() == "true"
    ].copy()

    if problems.empty:

        print("No customer problems identified.")

        return pd.DataFrame()

    # Load cached model.
    model = load_model()

    print("Generating feedback embeddings...")

    embeddings = model.encode(
        problems["feedback"].tolist(),
        normalize_embeddings=True,
        show_progress_bar=False
    )

    # Handle datasets containing only one complaint.
    if len(problems) == 1:

        problems["cluster_id"] = 0

    else:

        # Calculate semantic similarity.
        similarity = cosine_similarity(embeddings)

        # Retrieve detected problem categories.
        categories = problems["problem_categories"].tolist()

        # Adjust similarity when reviews share categories.
        for i in range(len(categories)):

            for j in range(i + 1, len(categories)):

                shared_categories = (
                    set(categories[i]) & set(categories[j])
                )

                if (
                    shared_categories
                    and similarity[i, j] >= CATEGORY_SIMILARITY_THRESHOLD
                ):

                    similarity[i, j] = max(
                        similarity[i, j],
                        SIMILARITY_THRESHOLD
                    )

                    similarity[j, i] = similarity[i, j]

        # Convert similarity into distance.
        distance = 1 - similarity

        # Avoid negative distances caused by floating-point errors.
        distance = distance.clip(min=0)

        # Perform hierarchical clustering.
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=1 - SIMILARITY_THRESHOLD,
            metric="precomputed",
            linkage="average"
        )

        problems["cluster_id"] = clustering.fit_predict(
            distance
        )

    return problems


def main():

    print("\nPRODUCTIQ — SEMANTIC FEEDBACK CLUSTERING\n")

    df = pd.read_csv(INPUT_FILE)

    clustered = cluster_feedback(df)

    if clustered.empty:
        return

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    clustered.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print("\nCUSTOMER PROBLEM CLUSTERS\n")

    for cluster_id, group in clustered.groupby("cluster_id"):

        count = len(group)

        print(f"Cluster {cluster_id} ({count} reviews)")

        for feedback in group["feedback"]:

            print(f"  - {feedback}")

        print()

    print(f"Total complaints analyzed: {len(clustered)}")

    print(
        f"Unique problem clusters: "
        f"{clustered['cluster_id'].nunique()}"
    )

    print(f"\nResults saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()