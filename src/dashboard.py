import io
import json
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

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
    validate_feedback,
)
from jira_export import (
    build_jira_issue_payload,
    format_jira_description,
    generate_jira_import_csv,
    map_priority_to_jira,
    send_to_jira_rest_api,
)
from local_llm import check_local_llm_status, synthesize_local_problem_statement
from prioritize import calculate_opportunities
from recommendations import generate_product_recommendation

BASE_DIR = Path(__file__).resolve().parents[1]
SAMPLE_FILE = BASE_DIR / "data" / "feedback" / "sample_feedback.csv"

# ==========================================
# PAGE CONFIGURATION & CONSULTING DARK THEME
# ==========================================
st.set_page_config(
    page_title="ProductIQ | Decision Support Platform",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global Dark Canvas */
    html, body, [class*="css"], .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        background-color: #0B0F19 !important;
        color: #F8FAFC !important;
    }

    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }

    /* Executive Segmented Tab Navigation */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #131B2E !important;
        border: 1px solid #1E293B !important;
        padding: 5px !important;
        border-radius: 8px !important;
        gap: 6px !important;
        margin-bottom: 24px !important;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 6px !important;
        padding: 8px 18px !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        color: #94A3B8 !important;
        border: none !important;
        background-color: transparent !important;
        transition: all 0.15s ease-in-out !important;
    }

    .stTabs [data-baseweb="tab"]:hover {
        color: #F8FAFC !important;
        background-color: #1A2338 !important;
    }

    .stTabs [aria-selected="true"] {
        background-color: #2563EB !important;
        color: #FFFFFF !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.4) !important;
    }

    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* Dark Executive Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #0E1526 !important;
        border-right: 1px solid #1E293B !important;
    }

    /* Consulting Card Containers */
    .consulting-card {
        background-color: #131B2E;
        border: 1px solid #1E293B;
        border-radius: 8px;
        padding: 20px 24px;
        margin-bottom: 18px;
    }

    .consulting-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #1E293B;
        padding-bottom: 12px;
        margin-bottom: 16px;
    }

    /* KPI Summary Cards */
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 14px;
        margin-bottom: 22px;
    }

    .kpi-card {
        background-color: #131B2E;
        border: 1px solid #1E293B;
        border-top: 3px solid #3B82F6;
        border-radius: 6px;
        padding: 16px 18px;
    }

    .kpi-label {
        font-size: 0.70rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #94A3B8;
        margin-bottom: 6px;
    }

    .kpi-value {
        font-size: 1.65rem;
        font-weight: 700;
        color: #F8FAFC;
        line-height: 1.15;
    }

    .kpi-sub {
        font-size: 0.75rem;
        color: #64748B;
        margin-top: 4px;
    }

    /* Clean Status Badges */
    .badge {
        display: inline-block;
        padding: 3px 9px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .badge-blue { background: rgba(37, 99, 235, 0.2); color: #60A5FA; border: 1px solid #2563EB; }
    .badge-green { background: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid #059669; }
    .badge-amber { background: rgba(245, 158, 11, 0.2); color: #FBBF24; border: 1px solid #D97706; }
    .badge-red { background: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid #DC2626; }
    .badge-slate { background: rgba(148, 163, 184, 0.15); color: #CBD5E1; border: 1px solid #475569; }

    /* Verified Quote Boxes */
    .quote-box {
        background-color: #0E1526;
        border: 1px solid #1E293B;
        border-left: 3px solid #3B82F6;
        border-radius: 4px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }

    .quote-text {
        font-size: 0.88rem;
        color: #E2E8F0;
        line-height: 1.5;
        margin-bottom: 6px;
    }

    .quote-meta {
        font-size: 0.75rem;
        color: #64748B;
        display: flex;
        gap: 16px;
    }

    /* Buttons */
    div.stButton > button[kind="primary"], div.stButton > button[data-testid="stBaseButton-primary"] {
        background-color: #2563EB !important;
        border: 1px solid #1D4ED8 !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        font-size: 0.85rem !important;
        padding: 8px 18px !important;
    }

    div.stButton > button[kind="primary"]:hover, div.stButton > button[data-testid="stBaseButton-primary"]:hover {
        background-color: #1D4ED8 !important;
    }

    div.stButton > button[kind="secondary"], div.stButton > button[data-testid="stBaseButton-secondary"] {
        background-color: #131B2E !important;
        border: 1px solid #334155 !important;
        color: #E2E8F0 !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
    }

    div.stButton > button[kind="secondary"]:hover, div.stButton > button[data-testid="stBaseButton-secondary"]:hover {
        background-color: #1E293B !important;
        border-color: #475569 !important;
    }

    /* Streamlit Input fields dark styling */
    div[data-baseweb="input"], div[data-baseweb="textarea"], div[data-baseweb="select"] {
        background-color: #0E1526 !important;
        border-color: #1E293B !important;
        color: #F8FAFC !important;
    }

    /* Text areas and inputs */
    textarea, input {
        color: #F8FAFC !important;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_sample_dataset() -> pd.DataFrame:
    """Load the built-in sample feedback dataset."""
    if SAMPLE_FILE.exists():
        return pd.read_csv(SAMPLE_FILE)
    return pd.DataFrame()


def run_pipeline(standardized_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Execute cleaning, analysis, clustering, and prioritization."""
    cleaned = clean_feedback(standardized_df)
    if cleaned.empty:
        return cleaned, pd.DataFrame(), pd.DataFrame()

    analyzed = analyze_feedback(cleaned)
    clustered = cluster_feedback(analyzed)

    if clustered.empty:
        return cleaned, clustered, pd.DataFrame()

    opportunities = calculate_opportunities(clustered, total_feedback=len(cleaned))
    return cleaned, clustered, opportunities


# Initialize Session State
if "raw_df" not in st.session_state:
    st.session_state.raw_df = None
if "standardized_df" not in st.session_state:
    st.session_state.standardized_df = None
if "analyzed_data" not in st.session_state:
    st.session_state.analyzed_data = None
if "competitive_findings" not in st.session_state:
    st.session_state.competitive_findings = {}
if "product_name" not in st.session_state:
    st.session_state.product_name = "TaskFlow"


# ==========================================
# SIDEBAR NAVIGATION & CONFIGURATION
# ==========================================
st.sidebar.markdown("""
<div style="padding: 12px 0 16px 0; border-bottom: 1px solid #1E293B; margin-bottom: 16px;">
    <div style="font-size: 1.15rem; font-weight: 700; color: #F8FAFC; letter-spacing: -0.01em;">PRODUCTIQ</div>
    <div style="font-size: 0.75rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.05em;">Product Decision Intelligence</div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style="font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: #64748B; margin-bottom: 6px;">
    PORTFOLIO PRODUCT
</div>
""", unsafe_allow_html=True)
st.session_state.product_name = st.sidebar.text_input(
    "Active Product",
    value=st.session_state.product_name,
    help="Target product name for opportunity synthesis",
    label_visibility="collapsed"
)

st.sidebar.markdown("""
<div style="height: 12px;"></div>
<div style="font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: #64748B; margin-bottom: 6px;">
    SYSTEM ARCHITECTURE
</div>
<div style="font-size: 0.80rem; color: #94A3B8; line-height: 1.6; background-color: #131B2E; padding: 12px; border-radius: 6px; border: 1px solid #1E293B;">
    • <strong>NLP Engine:</strong> all-MiniLM-L6-v2<br>
    • <strong>Compute:</strong> Local CPU Only<br>
    • <strong>Privacy:</strong> Zero External Model Calls
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("""
<div style="height: 12px;"></div>
<div style="font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: #64748B; margin-bottom: 6px;">
    LOCAL LLM ENHANCEMENT
</div>
""", unsafe_allow_html=True)
enable_local_llm = st.sidebar.checkbox(
    "Enable Local LLM (Ollama)",
    value=False,
    help="Optionally synthesize customer problem statements via local Ollama or llama.cpp endpoint."
)
local_llm_endpoint = "http://localhost:11434"
if enable_local_llm:
    local_llm_endpoint = st.sidebar.text_input("Local Endpoint", value="http://localhost:11434")
    llm_status = check_local_llm_status(local_llm_endpoint)
    if llm_status["available"]:
        st.sidebar.markdown(f'<span class="badge badge-green">Connected: {llm_status["type"]}</span>', unsafe_allow_html=True)
        if llm_status["models"]:
            st.sidebar.caption(f"Models: {', '.join(llm_status['models'][:2])}")
    else:
        st.sidebar.markdown('<span class="badge badge-slate">Offline: Fallback to Rules</span>', unsafe_allow_html=True)

st.sidebar.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
if st.sidebar.button("Reset Workspace Data", use_container_width=True, type="secondary"):
    st.session_state.raw_df = None
    st.session_state.standardized_df = None
    st.session_state.analyzed_data = None
    st.session_state.competitive_findings = {}
    st.rerun()


# ==========================================
# EXECUTIVE HEADER BAR
# ==========================================
st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; padding: 14px 0 18px 0; border-bottom: 1px solid #1E293B; margin-bottom: 22px;">
    <div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 1.35rem; font-weight: 700; color: #F8FAFC; letter-spacing: -0.01em;">PRODUCTIQ</span>
            <span class="badge badge-blue">Executive Decision Support</span>
            <span class="badge badge-green">CPU Local Engine</span>
        </div>
        <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 4px;">
            Customer feedback intelligence, objective prioritization, and evidence-backed roadmap briefs
        </div>
    </div>
    <div style="text-align: right;">
        <div style="font-size: 0.70rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: #64748B;">Target Product Under Review</div>
        <div style="font-size: 0.95rem; font-weight: 600; color: #F8FAFC;">{st.session_state.product_name}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ==========================================
# WORKSPACE NAVIGATION TABS
# ==========================================
tab_intake, tab_diagnostics, tab_matrix, tab_benchmark, tab_briefs = st.tabs([
    "Data Intake",
    "Diagnostic Insights",
    "Prioritization Matrix",
    "Competitive Benchmarking",
    "Strategic Opportunity Briefs"
])


# -----------------------------------------------------------------------------
# TAB 1: DATA INTAKE
# -----------------------------------------------------------------------------
with tab_intake:
    st.markdown("""
    <div style="font-size: 1.05rem; font-weight: 600; color: #F8FAFC; margin-bottom: 4px;">Customer Feedback Ingestion</div>
    <div style="font-size: 0.85rem; color: #94A3B8; margin-bottom: 18px;">
        Accepts raw customer reviews, support transcripts, or structured datasets across CSV, XLSX, and TXT formats.
    </div>
    """, unsafe_allow_html=True)

    col_input_left, col_input_right = st.columns([1, 1])

    with col_input_left:
        input_mode = st.radio(
            "Select Intake Source",
            ["Dataset Upload (CSV / XLSX / TXT)", "Direct Text Reviews (Pasted)", "Sample Feedback Dataset"],
            horizontal=False
        )

        uploaded_df = None
        pasted_text = ""

        if input_mode == "Dataset Upload (CSV / XLSX / TXT)":
            uploaded_file = st.file_uploader(
                "Upload file",
                type=["csv", "xlsx", "txt"],
                help="Supports standard and customized schemas. Missing ratings are preserved without errors.",
                label_visibility="collapsed"
            )
            if uploaded_file is not None:
                file_ext = Path(uploaded_file.name).suffix.lower()
                if file_ext == ".csv":
                    try:
                        uploaded_df = pd.read_csv(uploaded_file)
                    except Exception as e:
                        st.error(f"Error reading CSV: {e}")
                elif file_ext == ".xlsx":
                    try:
                        df_excel, sheets = load_excel_file(uploaded_file.getvalue())
                        if len(sheets) > 1:
                            chosen_sheet = st.selectbox("Select Worksheet", sheets)
                            uploaded_df, _ = load_excel_file(uploaded_file.getvalue(), sheet_name=chosen_sheet)
                        else:
                            uploaded_df = df_excel
                    except Exception as e:
                        st.error(f"Error reading Excel file: {e}")
                elif file_ext == ".txt":
                    text_content = uploaded_file.getvalue().decode("utf-8", errors="replace")
                    uploaded_df = parse_raw_text_reviews(text_content, mode="auto", default_product=st.session_state.product_name)

        elif input_mode == "Direct Text Reviews (Pasted)":
            sample_prompt_text = (
                "1 star - The application crashes constantly when uploading files.\n"
                "2 stars - Notifications arrive several hours late.\n"
                "3/5 - The dashboard is slow and takes too long to load.\n"
                "Rating: 2 - Appointment scheduling is confusing and hard to navigate.\n"
                "I wish there were more customization options for my reports.\n"
                "5 stars - Excellent product, easy to use."
            )
            col_t1, _ = st.columns([1, 3])
            if col_t1.button("Insert Sample Feedback", type="secondary"):
                st.session_state.paste_box_content = sample_prompt_text

            pasted_text = st.text_area(
                "Raw Reviews",
                value=st.session_state.get("paste_box_content", ""),
                height=180,
                placeholder="Paste customer reviews here (supports star ratings, fractions, and numbered lines)...",
                label_visibility="collapsed"
            )
            parse_mode = st.radio(
                "Segmentation Strategy",
                ["auto", "line", "paragraph"],
                format_func=lambda x: {"auto": "Auto-Detect", "line": "One Review Per Line", "paragraph": "Blank-Line Paragraphs"}[x],
                horizontal=True
            )
            if pasted_text.strip():
                uploaded_df = parse_raw_text_reviews(
                    pasted_text,
                    mode=parse_mode,
                    default_product=st.session_state.product_name
                )

        else:
            sample_df = load_sample_dataset()
            if not sample_df.empty:
                st.info("Loaded built-in baseline dataset (10 representative records across support and app stores).")
                uploaded_df = sample_df
            else:
                st.warning("Sample dataset not found.")

    with col_input_right:
        if uploaded_df is not None and not uploaded_df.empty:
            raw_cols = list(uploaded_df.columns)
            auto_mapping, _ = detect_column_mappings(raw_cols)

            with st.expander("Schema Alignment Configuration", expanded=False):
                review_col = st.selectbox("Feedback Text Column", raw_cols, index=raw_cols.index(auto_mapping["feedback"]) if "feedback" in auto_mapping and auto_mapping["feedback"] in raw_cols else 0)
                rating_col = st.selectbox("Rating Column", ["[None / Not Provided]"] + raw_cols, index=raw_cols.index(auto_mapping["rating"]) + 1 if "rating" in auto_mapping and auto_mapping["rating"] in raw_cols else 0)
                custom_mapping = {
                    "feedback": review_col,
                    "rating": rating_col if rating_col != "[None / Not Provided]" else None
                }

            try:
                standardized = standardize_feedback_df(
                    uploaded_df,
                    column_mapping=custom_mapping if "custom_mapping" in locals() else auto_mapping,
                    default_product=st.session_state.product_name,
                    default_source="Direct Customer Feedback"
                )
                st.session_state.standardized_df = standardized
                summary = generate_ingestion_summary(standardized)

                st.markdown(f"""
                <div class="kpi-container" style="grid-template-columns: 1fr 1fr; margin-bottom: 12px;">
                    <div class="kpi-card">
                        <div class="kpi-label">INGESTED RECORDS</div>
                        <div class="kpi-value">{summary['total_reviews']}</div>
                        <div class="kpi-sub">Normalized feedback items</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">RATING COVERAGE</div>
                        <div class="kpi-value">{summary['rating_coverage_pct']}%</div>
                        <div class="kpi-sub">{summary['rated_reviews']} rated / {summary['unrated_reviews']} unrated</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if st.button("Execute Semantic Analysis & Clustering", type="primary", use_container_width=True):
                    with st.spinner("Executing local semantic clustering and prioritization..."):
                        cleaned, clustered, opps = run_pipeline(standardized)
                        st.session_state.analyzed_data = (cleaned, clustered, opps)
                        st.success(f"Analysis complete. Identified {len(opps)} problem clusters.")
                        st.info("Navigate to Diagnostic Insights or Prioritization Matrix to inspect findings.")

            except Exception as e:
                st.error(f"Schema standardization error: {e}")
        else:
            st.markdown("""
            <div class="consulting-card" style="text-align: center; padding: 40px 20px;">
                <div style="font-size: 0.90rem; color: #94A3B8;">Awaiting feedback intake on the left.</div>
                <div style="font-size: 0.78rem; color: #64748B; margin-top: 4px;">Choose an upload method or insert sample reviews to initiate ingestion.</div>
            </div>
            """, unsafe_allow_html=True)

    if uploaded_df is not None and not uploaded_df.empty and st.session_state.standardized_df is not None:
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 0.85rem; font-weight: 600; color: #94A3B8; text-transform: uppercase; margin-bottom: 6px;'>Normalized Ingestion Preview</div>", unsafe_allow_html=True)
        st.dataframe(st.session_state.standardized_df.head(6), use_container_width=True, hide_index=True)


# -----------------------------------------------------------------------------
# TAB 2: DIAGNOSTIC INSIGHTS
# -----------------------------------------------------------------------------
with tab_diagnostics:
    if st.session_state.analyzed_data is None:
        st.info("No feedback analyzed yet. Please execute analysis in the Data Intake workspace.")
    else:
        all_feedback, feedback, opportunities = st.session_state.analyzed_data

        total_count = len(all_feedback)
        complaint_count = len(feedback)
        opps_count = len(opportunities)
        valid_ratings = all_feedback["rating"].dropna()
        avg_rating = round(valid_ratings.mean(), 2) if not valid_ratings.empty else None
        coverage_pct = round((len(valid_ratings) / total_count) * 100, 1) if total_count > 0 else 0.0

        # Executive KPI Grid
        st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-label">TOTAL FEEDBACK VOLUME</div>
                <div class="kpi-value">{total_count}</div>
                <div class="kpi-sub">Across all intake channels</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">IDENTIFIED COMPLAINTS</div>
                <div class="kpi-value">{complaint_count}</div>
                <div class="kpi-sub">{round((complaint_count/total_count)*100, 1) if total_count>0 else 0}% dissatisfaction prevalence</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">PROBLEM CLUSTERS</div>
                <div class="kpi-value">{opps_count}</div>
                <div class="kpi-sub">Distinct thematic groups</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">RATING COVERAGE</div>
                <div class="kpi-value">{coverage_pct}%</div>
                <div class="kpi-sub">{len(valid_ratings)} records with explicit rating</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">OBSERVED AVERAGE RATING</div>
                <div class="kpi-value">{f"{avg_rating}/5.0" if avg_rating is not None else "Unrated"}</div>
                <div class="kpi-sub">Customer sentiment index</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if not opportunities.empty:
            c_diag1, c_diag2 = st.columns([3, 2])

            with c_diag1:
                st.markdown("<div style='font-size: 0.90rem; font-weight: 600; color: #F8FAFC; margin-bottom: 8px;'>Complaint Volume by Customer Problem Area</div>", unsafe_allow_html=True)
                fig_prev = px.bar(
                    opportunities,
                    x="complaint_count",
                    y="problem",
                    orientation="h",
                    labels={"complaint_count": "Complaints", "problem": "Problem Area"},
                    color_discrete_sequence=["#3B82F6"]
                )
                fig_prev.update_layout(
                    yaxis={"categoryorder": "total ascending", "tickfont": {"size": 11, "color": "#F8FAFC"}},
                    xaxis={"gridcolor": "#1E293B", "tickfont": {"size": 10, "color": "#94A3B8"}},
                    plot_bgcolor="#131B2E",
                    paper_bgcolor="#131B2E",
                    height=300,
                    margin={"l": 10, "r": 10, "t": 10, "b": 10},
                    font={"family": "Inter, sans-serif"}
                )
                st.plotly_chart(fig_prev, use_container_width=True)

            with c_diag2:
                st.markdown("<div style='font-size: 0.90rem; font-weight: 600; color: #F8FAFC; margin-bottom: 8px;'>Opportunity Prevalence vs. Severity Matrix</div>", unsafe_allow_html=True)
                fig_scatter = px.scatter(
                    opportunities,
                    x="prevalence_pct",
                    y="priority_score",
                    size="complaint_count",
                    hover_name="problem",
                    color_discrete_sequence=["#60A5FA"],
                    labels={"prevalence_pct": "Prevalence (%)", "priority_score": "Priority Score (0-100)"}
                )
                fig_scatter.update_layout(
                    yaxis={"gridcolor": "#1E293B", "tickfont": {"size": 10, "color": "#94A3B8"}},
                    xaxis={"gridcolor": "#1E293B", "tickfont": {"size": 10, "color": "#94A3B8"}},
                    plot_bgcolor="#131B2E",
                    paper_bgcolor="#131B2E",
                    height=300,
                    margin={"l": 10, "r": 10, "t": 10, "b": 10},
                    font={"family": "Inter, sans-serif"}
                )
                st.plotly_chart(fig_scatter, use_container_width=True)

            # Customer Voice Evidence Explorer
            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            st.markdown("<div style='font-size: 0.95rem; font-weight: 600; color: #F8FAFC; margin-bottom: 6px;'>Verbatim Customer Evidence Drill-Down</div>", unsafe_allow_html=True)

            prob_dict = opportunities.set_index("cluster_id")["problem"].to_dict()
            chosen_cluster = st.selectbox(
                "Filter Evidence by Problem Cluster",
                options=list(prob_dict.keys()),
                format_func=lambda x: prob_dict[x],
                key="diag_cluster_filter",
                label_visibility="collapsed"
            )

            cluster_reviews = feedback[feedback["cluster_id"] == chosen_cluster]
            for _, r in cluster_reviews.iterrows():
                r_rating = f"{r['rating']}/5.0" if pd.notna(r.get("rating")) else "Unrated"
                r_source = r.get("source", "Direct Customer Submission")
                r_date = f"Date: {r['date']}" if pd.notna(r.get("date")) else ""
                st.markdown(f"""
                <div class="quote-box">
                    <div class="quote-text">"{r['feedback']}"</div>
                    <div class="quote-meta">
                        <span>Source: <strong>{r_source}</strong></span>
                        <span>Rating: <strong>{r_rating}</strong></span>
                        <span>{r_date}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
            c_csv1, c_csv2 = st.columns(2)
            with c_csv1:
                st.download_button(
                    "Export Clean Feedback Dataset (CSV)",
                    data=all_feedback.to_csv(index=False).encode("utf-8"),
                    file_name="clean_feedback.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with c_csv2:
                st.download_button(
                    "Export Prioritized Opportunities (CSV)",
                    data=opportunities.to_csv(index=False).encode("utf-8"),
                    file_name="productiq_prioritized_opportunities.csv",
                    mime="text/csv",
                    use_container_width=True
                )


# -----------------------------------------------------------------------------
# TAB 3: PRIORITIZATION MATRIX
# -----------------------------------------------------------------------------
with tab_matrix:
    if st.session_state.analyzed_data is None:
        st.info("Analyze customer feedback to populate the opportunity prioritization matrix.")
    else:
        all_feedback, feedback, opportunities = st.session_state.analyzed_data

        if opportunities.empty:
            st.success("No recurring customer problems identified.")
        else:
            has_unrated = opportunities["average_rating"].isna().all()
            if has_unrated:
                st.markdown("""
                <div class="badge badge-amber" style="margin-bottom: 14px; padding: 6px 12px; font-size: 0.80rem;">
                    NOTICE: Dataset contains no numerical ratings. Opportunities are ranked strictly by complaint prevalence.
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<div style='font-size: 1.0rem; font-weight: 600; color: #F8FAFC; margin-bottom: 10px;'>Prioritized Opportunity Backlog</div>", unsafe_allow_html=True)
            display_opps = opportunities[[
                "problem", "complaint_count", "prevalence_pct",
                "average_rating", "rating_coverage_pct", "priority_score", "scoring_methodology"
            ]].copy()
            display_opps.columns = [
                "Customer Problem", "Complaints", "Prevalence (%)",
                "Avg Rating", "Rating Coverage (%)", "Priority Score", "Scoring Methodology"
            ]
            st.dataframe(display_opps, use_container_width=True, hide_index=True)

            st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
            st.markdown("<div style='font-size: 1.0rem; font-weight: 600; color: #F8FAFC; margin-bottom: 10px;'>Strategic Initiative Deep-Dive</div>", unsafe_allow_html=True)

            selected_prob = st.selectbox(
                "Select Problem for Analysis",
                options=opportunities["problem"].tolist(),
                label_visibility="collapsed"
            )

            opp_row = opportunities[opportunities["problem"] == selected_prob].iloc[0]
            cluster_id = opp_row["cluster_id"]
            cluster_df = feedback[feedback["cluster_id"] == cluster_id]

            rec = generate_product_recommendation(opp_row, cluster_df)

            st.markdown(f"""
            <div class="consulting-card">
                <div class="consulting-card-header">
                    <div>
                        <div style="font-size: 1.15rem; font-weight: 700; color: #F8FAFC;">{rec['problem_title']}</div>
                        <div style="font-size: 0.80rem; color: #94A3B8; margin-top: 2px;">
                            Archetype: <strong>{rec['archetype']}</strong> | Calculated Priority: <strong>{opp_row['priority_score']}/100</strong>
                        </div>
                    </div>
                    <div>
                        <span class="badge badge-blue">{opp_row['scoring_methodology']}</span>
                    </div>
                </div>
                <div style="background-color: #0E1526; border: 1px solid #1E293B; border-radius: 6px; padding: 14px 16px; font-size: 0.88rem; color: #E2E8F0; line-height: 1.5; margin-bottom: 18px;">
                    {rec['problem_statement']}
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.markdown("""
                <div class="consulting-card">
                    <div style="font-size: 0.90rem; font-weight: 600; color: #F8FAFC; margin-bottom: 10px;">
                        Underlying Hypotheses (Engineering Discovery)
                    </div>
                """, unsafe_allow_html=True)
                for cause in rec["potential_causes"]:
                    st.markdown(f"• {cause}")

                st.markdown("""
                <div style="height: 14px;"></div>
                <div style="font-size: 0.90rem; font-weight: 600; color: #F8FAFC; margin-bottom: 10px;">
                    Recommended Strategic Initiatives
                </div>
                """, unsafe_allow_html=True)
                for init in rec["recommended_initiatives"]:
                    st.markdown(f"• **{init}**")

                st.markdown("""
                <div style="height: 14px;"></div>
                <div style="font-size: 0.90rem; font-weight: 600; color: #F8FAFC; margin-bottom: 10px;">
                    Actionable Implementation Steps
                </div>
                """, unsafe_allow_html=True)
                for step in rec["actionable_steps"]:
                    st.markdown(f"• {step}")
                st.markdown("</div>", unsafe_allow_html=True)

            with col_m2:
                st.markdown("""
                <div class="consulting-card">
                    <div style="font-size: 0.90rem; font-weight: 600; color: #F8FAFC; margin-bottom: 10px;">
                        Measurable Success Metrics (KPIs)
                    </div>
                """, unsafe_allow_html=True)
                for metric in rec["success_metrics"]:
                    st.markdown(f"• {metric}")

                st.markdown("""
                <div style="height: 14px;"></div>
                <div style="font-size: 0.90rem; font-weight: 600; color: #F8FAFC; margin-bottom: 10px;">
                    Proposed MVP Delivery Boundary
                </div>
                """, unsafe_allow_html=True)
                st.write(rec["mvp_scope"])

                st.markdown("""
                <div style="height: 14px;"></div>
                <div style="font-size: 0.90rem; font-weight: 600; color: #F8FAFC; margin-bottom: 10px;">
                    Core Risks & Assumptions
                </div>
                """, unsafe_allow_html=True)
                for risk in rec["risks_and_assumptions"]:
                    st.markdown(f"• {risk}")
                st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# TAB 4: COMPETITIVE BENCHMARKING
# -----------------------------------------------------------------------------
with tab_benchmark:
    st.markdown("""
    <div style="font-size: 1.05rem; font-weight: 600; color: #F8FAFC; margin-bottom: 4px;">Competitive Intelligence & Feature Gap Verification</div>
    <div style="font-size: 0.85rem; color: #94A3B8; margin-bottom: 18px;">
        Evaluates customer friction against official public competitor documentation. Findings require verified text citations and avoid fabricated claims.
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.analyzed_data is None or st.session_state.analyzed_data[2].empty:
        st.info("Analyze customer feedback first to select problem areas for competitive benchmarking.")
    else:
        opportunities = st.session_state.analyzed_data[2]
        comp_problem = st.selectbox(
            "Select Opportunity to Benchmark",
            options=opportunities["problem"].tolist(),
            key="comp_prob_select"
        )

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            comp_name_1 = st.text_input("Competitor A Name", value="Competitor A")
            comp_url_1 = st.text_input("Competitor A Documentation URL", placeholder="https://docs.competitor.com/features")
        with col_c2:
            comp_name_2 = st.text_input("Competitor B Name", value="Competitor B")
            comp_url_2 = st.text_input("Competitor B Documentation URL", placeholder="https://docs.competitor.com/features")

        if st.button("Execute Documentation Verification", type="primary"):
            findings_list = []
            with st.spinner("Retrieving and analyzing public documentation citations..."):
                if comp_name_1.strip():
                    f1 = analyze_competitor_capability(comp_name_1, comp_problem, comp_url_1)
                    findings_list.append(f1)
                if comp_name_2.strip():
                    f2 = analyze_competitor_capability(comp_name_2, comp_problem, comp_url_2)
                    findings_list.append(f2)
                st.session_state.competitive_findings[comp_problem] = findings_list

        if comp_problem in st.session_state.competitive_findings:
            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            findings = st.session_state.competitive_findings[comp_problem]

            badge_styles = {
                "Supported by evidence": "badge-green",
                "Partially supported": "badge-amber",
                "Not established": "badge-slate",
                "Unable to verify": "badge-red"
            }

            for f in findings:
                badge_cls = badge_styles.get(f["status"], "badge-slate")
                st.markdown(f"""
                <div class="consulting-card">
                    <div class="consulting-card-header">
                        <div>
                            <div style="font-size: 1.05rem; font-weight: 600; color: #F8FAFC;">{f['competitor']}</div>
                            <div style="font-size: 0.80rem; color: #94A3B8;">{f['relevant_capability']}</div>
                        </div>
                        <div>
                            <span class="badge {badge_cls}">{f['status']}</span>
                        </div>
                    </div>
                    <div style="font-size: 0.88rem; color: #E2E8F0; line-height: 1.5; margin-bottom: 10px;">
                        <strong>Evidence Summary:</strong> {f['evidence_summary']}
                    </div>
                    <div style="font-size: 0.75rem; color: #64748B;">
                        Source: <strong>{f['source_url']}</strong> | Verification Date: <strong>{f['retrieval_date']}</strong>
                    </div>
                </div>
                """, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# TAB 5: STRATEGIC OPPORTUNITY BRIEFS
# -----------------------------------------------------------------------------
with tab_briefs:
    st.markdown("""
    <div style="font-size: 1.05rem; font-weight: 600; color: #F8FAFC; margin-bottom: 4px;">Strategic Product Briefs & Roadmap Integration</div>
    <div style="font-size: 0.85rem; color: #94A3B8; margin-bottom: 18px;">
        Generates 12-section consulting product briefs and enables one-click export into Jira backlog (Epics & Stories).
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.analyzed_data is None or st.session_state.analyzed_data[2].empty:
        st.info("Import and analyze customer feedback first to generate opportunity briefs.")
    else:
        opportunities = st.session_state.analyzed_data[2]
        feedback = st.session_state.analyzed_data[1]

        brief_problem = st.selectbox(
            "Select Opportunity for Brief Generation",
            options=opportunities["problem"].tolist(),
            key="brief_select"
        )

        selected_row = opportunities[opportunities["problem"] == brief_problem].iloc[0]
        cluster_id = selected_row["cluster_id"]
        cluster_df = feedback[feedback["cluster_id"] == cluster_id]

        rec = generate_product_recommendation(selected_row, cluster_df)
        comp_findings = st.session_state.competitive_findings.get(brief_problem, [])

        if enable_local_llm:
            col_llm_btn, col_llm_msg = st.columns([1, 3])
            if col_llm_btn.button("Refine Statement with Local LLM", type="secondary"):
                with st.spinner("Synthesizing problem statement using local model..."):
                    llm_statement = synthesize_local_problem_statement(
                        problem_title=brief_problem,
                        quotes=cluster_df["feedback"].tolist(),
                        endpoint=local_llm_endpoint
                    )
                    if llm_statement:
                        rec["problem_statement"] = f"{llm_statement} (Synthesized by Local LLM)"
                        st.success("Refined problem statement with local model.")
                    else:
                        st.info("Local model unreachable; retaining deterministic PM brief.")

        markdown_brief = generate_markdown_brief(
            recommendation=rec,
            opportunity_row=selected_row,
            competitive_findings=comp_findings,
            product_name=st.session_state.product_name
        )

        col_dl_md, col_dl_jira_csv, col_dl_jira_json = st.columns(3)
        with col_dl_md:
            st.download_button(
                label="Download Strategic Brief (.md)",
                data=markdown_brief.encode("utf-8"),
                file_name=f"strategic_brief_{selected_row['cluster_id']}_{brief_problem.lower().replace(' ', '_')}.md",
                mime="text/markdown",
                type="primary",
                use_container_width=True
            )

        with col_dl_jira_csv:
            all_recs = {
                str(row["problem"]): generate_product_recommendation(row, feedback[feedback["cluster_id"] == row["cluster_id"]])
                for _, row in opportunities.iterrows()
            }
            jira_csv_data = generate_jira_import_csv(
                opportunities_df=opportunities,
                recommendations_map=all_recs,
                project_key="PROD",
                issue_type="Epic",
                product_name=st.session_state.product_name
            )
            st.download_button(
                label="Export Jira Import CSV",
                data=jira_csv_data.encode("utf-8"),
                file_name="jira_backlog_epics_import.csv",
                mime="text/csv",
                help="Pre-formatted for Jira External System Importer (Settings > System > External System Import > CSV).",
                use_container_width=True
            )

        with col_dl_jira_json:
            jira_payload = build_jira_issue_payload(
                project_key="PROD",
                recommendation=rec,
                opportunity_row=selected_row,
                issue_type="Epic",
                product_name=st.session_state.product_name
            )
            st.download_button(
                label="Export Jira Issue JSON",
                data=json.dumps(jira_payload, indent=2).encode("utf-8"),
                file_name=f"jira_epic_{brief_problem.lower().replace(' ', '_')}.json",
                mime="application/json",
                use_container_width=True
            )

        # Direct Jira REST API Integration Expander
        with st.expander("Jira REST API Direct Synchronization", expanded=False):
            st.caption("Publish this opportunity directly as an Epic or Story into your Jira instance via REST API.")
            jira_c1, jira_c2 = st.columns(2)
            with jira_c1:
                jira_url = st.text_input("Jira Instance URL", placeholder="https://your-domain.atlassian.net", key="jira_host_input")
                jira_project = st.text_input("Project Key", value="PROD", placeholder="e.g. PROD, ENG", key="jira_key_input")
                jira_type = st.selectbox("Issue Type", ["Epic", "Story", "Task"], index=0, key="jira_type_input")
            with jira_c2:
                jira_email = st.text_input("User Email", placeholder="user@company.com", key="jira_email_input")
                jira_token = st.text_input("API Token", type="password", key="jira_token_input")

            if st.button("Publish Directly to Jira", type="secondary"):
                with st.spinner("Connecting to Jira REST API..."):
                    success, msg = send_to_jira_rest_api(
                        jira_base_url=jira_url,
                        email=jira_email,
                        api_token=jira_token,
                        project_key=jira_project,
                        recommendation=rec,
                        opportunity_row=selected_row,
                        issue_type=jira_type,
                        product_name=st.session_state.product_name
                    )
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 1.0rem; font-weight: 600; color: #F8FAFC; margin-bottom: 10px;'>Executive Brief Document Preview</div>", unsafe_allow_html=True)
        st.markdown(markdown_brief)


if __name__ == "__main__":
    pass
