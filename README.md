# ProductIQ — AI Product Intelligence & Prioritization Assistant

ProductIQ is an AI-powered product strategy and decision-support application designed for Product Managers, Strategy Consultants, and Engineering Leaders. It transforms raw, unstructured customer feedback into prioritized product opportunities, evidence-backed initiative recommendations, competitive gap analysis, and executive-ready Product Opportunity Briefs.

---

## 1. What ProductIQ Is

ProductIQ bridges the gap between qualitative customer sentiment and quantitative product roadmap prioritization. It offers **two complementary interfaces**:
1. **Interactive Streamlit Application:** An executive-styled visual dashboard for exploratory data discovery, problem matrix visualization, and one-click Jira exports.
2. **Reusable Claude Skill (`.claude/skills/productiq`):** A headless, command-line and agent-driven workflow enabling Claude Code to ingest customer reviews, cluster complaints, verify competitor capabilities, and synthesize Product Briefs directly from natural-language prompts.

Product teams use ProductIQ to:
- Automatically extract, cluster, and label customer pain points.
- Score and prioritize opportunities using transparent, reproducible heuristics.
- Synthesize actionable product initiatives with measurable success metrics.
- Benchmark capability gaps against verified competitor documentation.
- Export standardized executive Product Opportunity Briefs and Jira backlog tickets.

---

## 2. The Problem It Solves

- **Fragmented, Messy Feedback:** Reviews, app store comments, and support tickets arrive in varying schemas, pasted text, or without numerical star ratings.
- **Rating Bias & Brittleness:** Traditional scoring models fail when customer datasets lack star ratings or have partial coverage.
- **Vague Problem Definitions:** Engineering and product teams frequently disagree on root causes because complaints are not structured into traceable themes.
- **Unverified Competitive Claims:** Teams often assume competitor capabilities based on anecdotal hearsay rather than verifiable documentation evidence.
- **Roadmap Alignment Latency:** Writing structured product requirement briefs and executive summaries consumes days of manual effort.

---

## 3. Target Users

- **Product Managers:** Rapidly triage customer friction, quantify feature requests, and justify roadmap trade-offs with customer quotes.
- **Management & Strategy Consultants:** Accelerate voice-of-customer (VoC) diagnostics and product due diligence during client engagements.
- **Product Operations & Customer Support Leads:** Synthesize support ticket trends into structured issue clusters for engineering backlog insertion.
- **Founders & Engineering Leaders:** Identify critical product stability and usability bottlenecks without configuring complex enterprise analytics stacks.

---

## 4. Core Capabilities

1. **Universal Feedback Ingestion:**
   - Ingest CSV, Excel (`.xlsx`), plain text (`.txt`), or direct pasted reviews.
   - Intelligent regex-based rating extraction (e.g., `1 star - ...`, `4/5`, `Rating: 2`).
   - Flexible column matching tolerant of header aliases, hyphens, and casing.
   - Interactive schema validation and record preview before triggering embedding calculations.

2. **Rating-Independent Prioritization:**
   - **Fully Rated Datasets:** Balanced heuristic combining Complaint Prevalence (50%) and Dissatisfaction (50%).
   - **Completely Unrated Datasets:** Ranked transparently by Complaint Prevalence (100%) without inventing artificial ratings.
   - **Partially Rated Datasets:** Conservative prevalence ranking with explicit per-cluster rating coverage reporting.

3. **Evidence-Backed Product Recommendations:**
   - Classifies customer pain points into actionable archetypes (*Performance*, *Reliability*, *Notifications*, *Usability*, *Missing Functionality*).
   - Generates concrete product initiatives, implementation steps, MVP scope, and measurable KPIs.
   - Distinct separation of engineering hypotheses from verified customer evidence.

4. **Competitive Intelligence & Benchmarking:**
   - Evaluates identified product gaps against public competitor documentation URLs.
   - Categorizes evidence into four strict statuses: `Supported by evidence`, `Partially supported`, `Not established`, and `Unable to verify`.
   - Caches external pages, enforces request timeouts (5s), and never fabricates competitive claims.

5. **Executive Product Opportunity Briefs & Jira Export:**
   - Generates standardized 12-section Product Briefs ready for stakeholder and sprint planning.
   - Direct traceability to verbatim customer quotes.
   - One-click export to Markdown (`.md`) format.
   - **Jira Integration Suite:** Direct Jira REST API issue creation (Epics, Stories, Tasks), native Jira External System Import CSV export, and standard Jira issue JSON payload generation.

6. **Optional Local LLM Synthesis (Ollama / llama.cpp):**
   - Seamless toggle to connect to local offline model endpoints (e.g., `http://localhost:11434`).
   - Refines problem statements without making paid API calls or downloading models automatically.
   - Graceful zero-latency fallback to deterministic PM rules when offline.

---

## 5. System Architecture & Workflow

```
[Raw Customer Feedback] (CSV / XLSX / TXT / Pasted Text)
           │
           ▼
[1. Universal Ingestion & Normalization] ──> Standardized Schema (feedback_id, product, rating, feedback, date)
           │
           ▼
[2. Keyword Problem Tagging] ───────────────> Multi-category problem identification
           │
           ▼
[3. Local Semantic Embedding] ──────────────> MiniLM-L6-v2 (100% CPU inference, offline support)
           │
           ▼
[4. Hierarchical Clustering] ───────────────> AgglomerativeClustering (Cosine distance thresholding)
           │
           ▼
[5. Transparent Opportunity Scoring] ───────> Prevalence + Dissatisfaction / Prevalence Only
           │
           ├───> [6. Evidence-Backed PM Recommendations] (Initiatives, MVP, Metrics, Hypotheses)
           ├───> [7. Competitive Intelligence Analysis] (Public Documentation Verification)
           └───> [8. Executive 12-Section Product Brief] (Downloadable Markdown)
```

---

## 6. Technology Stack

- **Application & UI:** Streamlit, Plotly Express
- **Data Engineering:** Pandas, openpyxl, NumPy
- **Machine Learning & NLP:** Scikit-learn, Sentence-Transformers (`all-MiniLM-L6-v2`), PyTorch (CPU-only)
- **Competitive Scraping:** Requests, BeautifulSoup4
- **Testing:** Python `unittest` framework (built-in standard library)
- **APIs & Cost:** **100% Free & Local.** Zero paid cloud services, zero external model APIs.

---

## 7. Local Installation Instructions

Ensure you have Python 3.10+ installed on your local machine (macOS / Linux / Windows).

1. **Clone the repository:**
   ```bash
   git clone https://github.com/aa2878/productiq.git
   cd productiq
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 8. Interfaces & Execution Modes

ProductIQ provides two primary operating interfaces:

### Interface 1: Streamlit Visual Dashboard
Run the interactive application using the stability flags:
```bash
python -m streamlit run src/dashboard.py --server.fileWatcherType none
```
Then open `http://localhost:8501`. Features include:
- Five structured workspaces (*Data Intake*, *Diagnostics*, *Prioritization Matrix*, *Competitive Benchmarking*, *Strategic Opportunity Briefs*).
- Real-time Plotly volume and severity distributions.
- Direct Jira REST API push and External System Import CSV export.

### Interface 2: Reusable Claude Skill & CLI Engine
The headless analysis engine is accessible directly from the command line and configured as an official **Claude Skill** located at `.claude/skills/productiq/SKILL.md`.

#### CLI Commands:
```bash
# Ingest feedback and discover prioritized opportunities:
python src/cli.py analyze data/feedback/sample_feedback.csv --format json

# Analyze raw pasted review text directly:
python src/cli.py analyze --text "1 star - App crashes on upload.\n2 stars - Notifications arrive late." --format text

# Generate strategic PM recommendations for an opportunity:
python src/cli.py recommend --problem "Appointment Scheduling" --format text

# Benchmark competitor capability against official documentation:
python src/cli.py competitive --problem "Limited Customization" --competitor "Competitor A" --url "https://docs.competitor.com"

# Generate a 12-section Product Opportunity Brief:
python src/cli.py brief --problem "Appointment Scheduling" --output brief.md

# Export Jira backlog CSV:
python src/cli.py export-jira --project "PROD" --type "Epic" --output jira_epics.csv
```

#### Claude Code Skill Usage:
With `.claude/skills/productiq/SKILL.md` installed, Claude activates the skill automatically for queries such as:
> *"Analyze these customer reviews, identify the most important product problems, research relevant competitor capabilities using available evidence, and recommend what the product team should prioritize next."*

---

## 9. Supported Input Formats

### A. Direct Text Input
Supports multi-format pasted reviews:
- **One review per line:**
  ```text
  The dashboard is slow and takes too long to load.
  Notifications arrive several hours late.
  The app crashes when uploading large files.
  ```
- **Numbered reviews:**
  ```text
  1. The dashboard is slow.
  2. The calendar crashes frequently.
  3. I wish there were more customization options.
  ```
- **Explicit rating prefixes:**
  ```text
  1 star - The application crashes constantly.
  2 stars - Notifications are delayed.
  5 stars - Excellent product.
  3/5 - Dashboard performance needs improvement.
  Rating: 2 - Search results are inaccurate.
  ```
- **Blank-line-separated multiline paragraphs.**

### B. Flexible CSV / Excel Uploads (`.csv`, `.xlsx`)
Header matching is case-insensitive and supports aliases:
- **Review column:** `feedback`, `review`, `comment`, `customer_comment`, `text`, `description`, `issue`
- **Rating column:** `rating`, `stars`, `score`, `star_rating`, `user_rating`
- **Product column:** `product`, `product_name`, `app`, `application`, `service`
- **Date column:** `date`, `created_at`, `timestamp`, `datetime`
- **Source column:** `source`, `channel`, `platform`, `origin`

---

## 10. Prioritization Methodology

Priority scores are normalized on a 0–100 scale:

### Fully Rated Datasets (100% Rating Coverage)
$$\text{Priority Score} = 100 \times [0.5 \times \text{Complaint Prevalence} + 0.5 \times \text{Dissatisfaction}]$$

Where:
- $\text{Complaint Prevalence} = \frac{\text{Cluster Complaint Count}}{\text{Total Feedback Records}}$
- $\text{Dissatisfaction} = \frac{5.0 - \text{Average Rating}}{4.0}$

### Completely Unrated Datasets (0% Rating Coverage)
$$\text{Priority Score} = 100 \times \text{Complaint Prevalence}$$
*Transparent message displayed:* `"Ratings were not provided. Opportunities are ranked using complaint prevalence only."*

### Partially Rated Datasets
When rating coverage is incomplete, ProductIQ ranks conservatively by Complaint Prevalence while displaying observed average ratings and rating coverage percentage separately to avoid skewed averages.

---

## 11. Competitive Research Methodology

- **Input:** Product name, competitor names, and public documentation URLs.
- **Retrieval:** Lightweight HTTP request with a 5-second timeout and custom User-Agent.
- **Evidence Extraction:** Extracts verbatim sentences matching problem capabilities.
- **Confidence Statuses:**
  - **Supported by evidence:** Verbatim sentences confirm relevant functionality.
  - **Partially supported:** Documentation mentions related keywords; manual verification suggested.
  - **Not established:** Documentation does not mention the capability (does not prove feature absence).
  - **Unable to verify:** Server unreachable, timeout, or invalid URL.
- **Zero Fabrication:** ProductIQ never generates fictional competitor claims if sources are unreachable.

---

## 12. Product Recommendation Methodology

Recommendations are deterministic and tailored to identified problem archetypes:
- **Hypotheses:** Formulates actionable engineering hypotheses (clearly distinguished from confirmed diagnoses).
- **Initiatives & Actions:** Proposes concrete architectural or UX interventions.
- **Success Metrics:** Recommends standard product KPIs (e.g., P95 latency, crash-free session rate, task completion rate) without inventing baseline measurements.
- **MVP Scope & Risks:** Identifies initial delivery boundary and core operational assumptions.

---

## 13. Limitations

- **Heuristic Prioritization:** Priority scores are prioritization heuristics, not validated financial impact models.
- **Documentation Scraping:** Competitive intelligence depends on publicly accessible static documentation; pages requiring authentication, Single Page App rendering without SSR, or CAPTCHA cannot be scraped automatically.
- **Local Language Support:** Keyword categorizations and label rules are currently optimized for English-language feedback.

---

## 14. Future Improvements

- **Multi-language NLP:** Add multi-lingual embedding support for global customer feedback.
- **Linear Integration:** Direct API synchronization with Linear teams and cycles.
- **Cohort Filtering:** Drill down into opportunities by customer segment, enterprise tier, or device platform.

---

## 15. Automated Testing

Run the test suite covering all 39 end-to-end scenarios (ingestion, ratings, recommendations, competitive intelligence, exports, Jira integration, local LLM fallback, Claude Skill specification, and CLI entry points):

```bash
python -m unittest tests/test_productiq.py
```
