import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
INPUT_FILE = BASE_DIR / "data" / "feedback" / "sample_feedback.csv"
OUTPUT_FILE = BASE_DIR / "data" / "processed" / "clean_feedback.csv"

STANDARDIZED_COLUMNS = [
    "feedback_id",
    "product",
    "source",
    "rating",
    "feedback",
    "date"
]

COLUMN_ALIASES = {
    "feedback": [
        "feedback", "review", "reviews", "customer_comment", "comment",
        "comments", "text", "description", "issue", "complaint", "complaints",
        "content", "notes", "message", "body", "customer_feedback"
    ],
    "rating": [
        "rating", "ratings", "stars", "star", "score", "scores",
        "star_rating", "review_rating", "user_rating", "rate"
    ],
    "product": [
        "product", "product_name", "app", "application", "item", "service", "project"
    ],
    "date": [
        "date", "created_at", "timestamp", "time", "submission_date",
        "datetime", "posted_at", "review_date"
    ],
    "source": [
        "source", "channel", "platform", "feedback_source", "origin", "type"
    ],
    "feedback_id": [
        "feedback_id", "id", "review_id", "complaint_id", "ticket_id",
        "entry_id", "index"
    ]
}


def normalize_column_name(col: str) -> str:
    """Normalize column header for robust matching."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", str(col).strip().lower())
    return cleaned.strip("_")


def detect_column_mappings(columns: List[str]) -> Tuple[Dict[str, str], List[str]]:
    """
    Detect mapping from input columns to standardized schema.
    Returns (mapping_dict: {standard_col: actual_col}, unmapped_columns).
    """
    normalized_cols = {col: normalize_column_name(col) for col in columns}
    mapping = {}
    used_cols = set()

    for std_col, aliases in COLUMN_ALIASES.items():
        matched = None
        for orig_col, norm_col in normalized_cols.items():
            if orig_col in used_cols:
                continue
            if norm_col in aliases:
                matched = orig_col
                break
        if matched:
            mapping[std_col] = matched
            used_cols.add(matched)

    unmapped = [col for col in columns if col not in used_cols]
    return mapping, unmapped


def extract_rating_and_text(raw_text: str) -> Tuple[Optional[float], str]:
    """
    Detect explicit ratings from review lines/paragraphs:
    - '1 star - The application crashes constantly.'
    - '2 stars: Notifications are delayed.'
    - '5 stars - Excellent product.'
    - '3/5 - Dashboard performance needs improvement.'
    - 'Rating: 2 - Search results are inaccurate.'
    - 'Score: 4.5/5 Great service'
    """
    text = raw_text.strip()
    rating = None

    # Pattern: Rating: X or Score: X (e.g., "Rating: 2 - ...", "Rating: 4.5/5 - ...")
    m_rating_prefix = re.match(
        r"^(?:rating|score)\s*[:=\-]\s*([0-5](?:\.\d+)?)(?:\s*/\s*5)?\s*[\-–—:\|]?\s*(.*)$",
        text,
        re.IGNORECASE | re.DOTALL
    )
    if m_rating_prefix:
        val = float(m_rating_prefix.group(1))
        if 1.0 <= val <= 5.0:
            rating = val
            text = m_rating_prefix.group(2).strip()
            return rating, text

    # Pattern: X star(s) (e.g., "1 star - ...", "5 stars: ...")
    m_stars = re.match(
        r"^([1-5](?:\.\d+)?)\s*(?:stars?|★)\s*[\-–—:\|]?\s*(.*)$",
        text,
        re.IGNORECASE | re.DOTALL
    )
    if m_stars:
        rating = float(m_stars.group(1))
        text = m_stars.group(2).strip()
        return rating, text

    # Pattern: X/5 (e.g., "3/5 - ...", "4.0/5: ...")
    m_fraction = re.match(
        r"^([1-5](?:\.\d+)?)\s*/\s*5\s*[\-–—:\|]?\s*(.*)$",
        text,
        re.IGNORECASE | re.DOTALL
    )
    if m_fraction:
        rating = float(m_fraction.group(1))
        text = m_fraction.group(2).strip()
        return rating, text

    return None, text


def strip_list_numbering(text: str) -> str:
    """Remove leading list markers such as '1.', '1)', '[1]', or '-'."""
    return re.sub(r"^(?:(?:\d+[\.\)]|\[\d+\]|[\-\*\•])\s+)", "", text).strip()


def parse_raw_text_reviews(
    text: str,
    mode: str = "auto",
    default_product: str = "Pasted Feedback",
    default_source: str = "Direct Input"
) -> pd.DataFrame:
    """
    Parse pasted plain text or TXT files into a standardized DataFrame.
    Modes:
      - 'line': One review per line
      - 'paragraph': One review per blank-line-separated paragraph
      - 'auto': Automatically select paragraph if multi-line blank gaps exist, else lines.
    """
    if not text or not text.strip():
        return pd.DataFrame(columns=STANDARDIZED_COLUMNS)

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")

    if mode == "auto":
        # If there are double newlines with multiline chunks, use paragraph mode.
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", normalized_text) if p.strip()]
        if len(paragraphs) > 1 and any("\n" in p for p in paragraphs):
            selected_mode = "paragraph"
        else:
            selected_mode = "line"
    else:
        selected_mode = mode

    if selected_mode == "paragraph":
        raw_chunks = [p.strip() for p in re.split(r"\n\s*\n+", normalized_text) if p.strip()]
    else:
        raw_chunks = [line.strip() for line in normalized_text.split("\n") if line.strip()]

    records = []
    for idx, chunk in enumerate(raw_chunks, start=1):
        cleaned_chunk = strip_list_numbering(chunk)
        rating, cleaned_review = extract_rating_and_text(cleaned_chunk)
        # Check again if after rating extraction there is a leftover list numbering
        cleaned_review = strip_list_numbering(cleaned_review)

        if not cleaned_review:
            continue

        records.append({
            "feedback_id": f"txt_{idx}",
            "product": default_product,
            "source": default_source,
            "rating": rating,
            "feedback": cleaned_review,
            "date": None
        })

    return pd.DataFrame(records, columns=STANDARDIZED_COLUMNS)


def parse_xlsx_fallback(file_bytes: bytes) -> Dict[str, pd.DataFrame]:
    """
    Fallback parser for .xlsx files using standard library zipfile and xml,
    guaranteeing zero external dependency failure even if openpyxl is not loaded.
    """
    with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
        # Load shared strings
        shared_strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
            ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for si in tree.findall(".//s:si", ns):
                t_elem = si.find(".//s:t", ns)
                shared_strings.append(t_elem.text if t_elem is not None and t_elem.text else "")

        # Find sheets
        sheet_files = [n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
        sheet_dict = {}
        for s_file in sheet_files:
            sheet_name = Path(s_file).stem
            tree = ET.fromstring(z.read(s_file))
            ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            rows_data = []
            for row_elem in tree.findall(".//s:row", ns):
                row_vals = []
                for c_elem in row_elem.findall("s:c", ns):
                    c_type = c_elem.get("t")
                    v_elem = c_elem.find("s:v", ns)
                    val = v_elem.text if v_elem is not None else ""
                    if c_type == "s" and val.isdigit():
                        idx = int(val)
                        val = shared_strings[idx] if idx < len(shared_strings) else val
                    row_vals.append(val)
                if any(v != "" for v in row_vals):
                    rows_data.append(row_vals)

            if rows_data:
                headers = rows_data[0]
                data = rows_data[1:]
                df = pd.DataFrame(data, columns=headers)
                sheet_dict[sheet_name] = df

        return sheet_dict


def load_excel_file(file_obj, sheet_name: Optional[str] = None) -> Tuple[pd.DataFrame, List[str]]:
    """
    Load an Excel (.xlsx) file, returning (selected_df, list_of_sheet_names).
    Tries pandas (with openpyxl), falling back to parse_xlsx_fallback.
    """
    if hasattr(file_obj, "read"):
        content = file_obj.read()
    elif isinstance(file_obj, (str, Path)):
        with open(file_obj, "rb") as f:
            content = f.read()
    else:
        content = file_obj

    sheet_names = []
    try:
        import openpyxl  # noqa: F401
        excel_file = pd.ExcelFile(io.BytesIO(content), engine="openpyxl")
        sheet_names = excel_file.sheet_names
        chosen_sheet = sheet_name if sheet_name in sheet_names else sheet_names[0]
        df = pd.read_excel(io.BytesIO(content), sheet_name=chosen_sheet, engine="openpyxl")
        return df, sheet_names
    except Exception:
        # Fallback to pure standard library parser
        sheets = parse_xlsx_fallback(content)
        sheet_names = list(sheets.keys())
        if not sheet_names:
            return pd.DataFrame(), []
        chosen_sheet = sheet_name if sheet_name in sheet_names else sheet_names[0]
        return sheets[chosen_sheet], sheet_names


def standardize_feedback_df(
    df: pd.DataFrame,
    column_mapping: Optional[Dict[str, str]] = None,
    default_product: str = "Uploaded Product",
    default_source: str = "User Upload"
) -> pd.DataFrame:
    """
    Standardize any arbitrary incoming DataFrame to standardized columns:
    feedback_id, product, source, rating, feedback, date.
    """
    if df.empty:
        return pd.DataFrame(columns=STANDARDIZED_COLUMNS)

    df = df.copy()

    if column_mapping is None:
        column_mapping, _ = detect_column_mappings(list(df.columns))

    if "feedback" not in column_mapping or not column_mapping["feedback"]:
        raise ValueError(
            "Could not identify a feedback/review column in the dataset. "
            "Please select the review column manually."
        )

    res = pd.DataFrame()

    # Feedback text
    fb_col = column_mapping["feedback"]
    res["feedback"] = df[fb_col].astype(str)

    # Feedback ID
    if "feedback_id" in column_mapping and column_mapping["feedback_id"] in df.columns:
        res["feedback_id"] = df[column_mapping["feedback_id"]].astype(str)
        # If any empty or duplicate, re-generate missing
        if res["feedback_id"].duplicated().any() or (res["feedback_id"].str.strip() == "").any():
            res["feedback_id"] = [f"fb_{i}" for i in range(1, len(res) + 1)]
    else:
        res["feedback_id"] = [f"fb_{i}" for i in range(1, len(res) + 1)]

    # Product
    if "product" in column_mapping and column_mapping["product"] in df.columns:
        res["product"] = df[column_mapping["product"]].fillna(default_product).astype(str)
    else:
        res["product"] = default_product

    # Source
    if "source" in column_mapping and column_mapping["source"] in df.columns:
        res["source"] = df[column_mapping["source"]].fillna(default_source).astype(str)
    else:
        res["source"] = default_source

    # Rating
    if "rating" in column_mapping and column_mapping["rating"] in df.columns:
        res["rating"] = pd.to_numeric(df[column_mapping["rating"]], errors="coerce")
        # Validate rating range: invalid ratings become NaN rather than crashing
        res["rating"] = res["rating"].apply(
            lambda r: r if (pd.notna(r) and 1.0 <= float(r) <= 5.0) else None
        )
    else:
        res["rating"] = None

    # Date
    if "date" in column_mapping and column_mapping["date"] in df.columns:
        res["date"] = df[column_mapping["date"]].astype(str).replace({"nan": None, "None": None, "": None})
    else:
        res["date"] = None

    return res[STANDARDIZED_COLUMNS]


def validate_feedback(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the dataset contains required columns."""
    missing = [c for c in STANDARDIZED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df


def clean_feedback(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean customer feedback for analysis:
    - Removes empty or whitespace-only feedback.
    - Strips whitespace.
    - Conservatively removes duplicates (same product + feedback text).
    """
    if df.empty:
        return pd.DataFrame(columns=STANDARDIZED_COLUMNS)

    df = df.copy()

    # Drop empty or whitespace-only feedback
    df = df.dropna(subset=["feedback"])
    df["feedback"] = df["feedback"].astype(str).str.strip()
    df = df[df["feedback"] != ""]

    # Drop duplicates on feedback_id
    if "feedback_id" in df.columns:
        df = df.drop_duplicates(subset=["feedback_id"])

    # Drop duplicates on (product, feedback)
    if "product" in df.columns and "feedback" in df.columns:
        df = df.drop_duplicates(subset=["product", "feedback"])

    return df.reset_index(drop=True)


def generate_ingestion_summary(df: pd.DataFrame) -> Dict[str, Union[int, float]]:
    """Generate high-level ingestion preview statistics."""
    total = len(df)
    if total == 0:
        return {
            "total_reviews": 0,
            "rated_reviews": 0,
            "unrated_reviews": 0,
            "rating_coverage_pct": 0.0,
            "average_rating": None
        }

    rated_count = int(df["rating"].dropna().count())
    unrated_count = total - rated_count
    coverage_pct = round((rated_count / total) * 100, 1)
    avg_rating = round(float(df["rating"].dropna().mean()), 2) if rated_count > 0 else None

    return {
        "total_reviews": total,
        "rated_reviews": rated_count,
        "unrated_reviews": unrated_count,
        "rating_coverage_pct": coverage_pct,
        "average_rating": avg_rating
    }


def load_feedback(file_path: Union[str, Path]) -> pd.DataFrame:
    """Load customer feedback from CSV file."""
    return pd.read_csv(file_path)


def main():
    print("\nPRODUCTIQ — UNIVERSAL CUSTOMER FEEDBACK INGESTION\n")
    df = load_feedback(INPUT_FILE)
    print(f"Loaded {len(df)} feedback records.")

    mapping, _ = detect_column_mappings(list(df.columns))
    print(f"Detected mappings: {mapping}")

    standardized = standardize_feedback_df(df, mapping)
    cleaned = clean_feedback(standardized)
    print(f"Cleaned dataset contains {len(cleaned)} records.")

    summary = generate_ingestion_summary(cleaned)
    print(f"Summary: {summary}")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(OUTPUT_FILE, index=False)
    print(f"\nFeedback ingestion complete! Saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
