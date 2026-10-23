---
name: productiq
description: Analyzes customer reviews, support feedback, and user sentiment to identify recurring product friction, cluster semantically related complaints, calculate transparent priority scores, benchmark competitor capabilities against public documentation, and synthesize evidence-backed Product Opportunity Briefs. Use whenever the user asks to analyze customer feedback, discover product problems, prioritize roadmap features, benchmark competitor capabilities, or write a product brief.
---

# ProductIQ Claude Skill

ProductIQ is an AI-powered product intelligence and decision-support assistant designed for Product Managers, Strategy Consultants, and Engineering Leaders. It transforms raw, unstructured customer feedback into prioritized product opportunities, evidence-backed initiative recommendations, competitive gap analysis, and executive-ready Product Opportunity Briefs.

---

## Capabilities & Triggers

Activate this skill when the user asks to:
- **Analyze Customer Feedback:** "Analyze these customer reviews / support tickets and tell me what users are struggling with."
- **Prioritize Opportunities:** "Rank our top customer pain points based on volume and severity."
- **Recommend Interventions:** "What initiatives should we prioritize next to fix our notification delays or upload crashes?"
- **Benchmark Competitors:** "Check if Competitor A documents support for custom dashboards or calendar sync."
- **Generate Product Briefs:** "Write a product opportunity brief for our highest-priority customer complaint."
- **Export to Jira:** "Format these prioritized opportunities as Jira Epics or export a Jira import CSV."

---

## Architecture & Reusable CLI Entry Points

ProductIQ executes 100% locally on CPU without requiring the Streamlit dashboard to be running and without making any paid external API calls.

The core CLI engine is accessible via:
```bash
python src/cli.py <command> [options]
# Or via the skill wrapper:
python .claude/skills/productiq/scripts/run.py <command> [options]
```

### 1. Ingestion, Clustering & Prioritization (`analyze`)
Parses incoming customer reviews from files (.csv, .xlsx, .txt) or direct text strings, clusters them via sentence embeddings (`all-MiniLM-L6-v2`), and scores opportunities.

```bash
# Analyze a CSV, Excel, or TXT file:
python src/cli.py analyze path/to/feedback.csv --format json

# Analyze raw pasted text reviews:
python src/cli.py analyze --text "1 star - App crashes on upload.\n2 stars - Notifications are delayed." --format json

# Use built-in sample feedback:
python src/cli.py analyze --format text
```

**Key Arguments:**
- `input`: File path (`.csv`, `.xlsx`, `.txt`).
- `--text`: String containing raw customer reviews (supports `1 star - ...`, `4/5`, `Rating: 2`, and numbered lines).
- `--mode`: Text segmentation strategy: `auto` (default), `line`, or `paragraph`.
- `--product`: Product name under evaluation (default: `Our Product`).
- `--format`: Output format: `json` (for programmatic parsing) or `text` (human-readable report).
- `--output-dir`: Directory where intermediate processed CSVs are saved (default: `data/processed`).

### 2. Evidence-Backed PM Recommendations (`recommend`)
Generates actionable PM initiatives, concrete steps, measurable KPIs, and engineering hypotheses for any identified opportunity.

```bash
# Recommend for the top opportunity:
python src/cli.py recommend --format json

# Recommend for a specific problem by name or cluster ID:
python src/cli.py recommend --problem "Appointment Scheduling" --format text
python src/cli.py recommend --cluster-id 0 --format json
```

### 3. Public Competitor Benchmarking (`competitive`)
Benchmarks customer problems against official public documentation without fabricating evidence.

```bash
python src/cli.py competitive --problem "Limited Dashboard Customization" --competitor "Competitor A" --url "https://docs.competitor.com/dashboards" --format json
```

**Status Categories:**
- `Supported by evidence`: Documentation explicitly confirms the capability with verbatim quotes.
- `Partially supported`: Documentation mentions related keywords; manual verification suggested.
- `Not established`: No mention found (does not prove feature absence).
- `Unable to verify`: URL unreachable or request timed out.

### 4. Executive 12-Section Product Brief (`brief`)
Synthesizes verified customer quotes, problem metrics, competitive context, initiatives, and KPIs into a structured Product Opportunity Brief.

```bash
# Output brief to terminal:
python src/cli.py brief --problem "Confusing Appointment Scheduling" --product "TaskFlow"

# Save brief to Markdown file:
python src/cli.py brief --problem "Calendar Reliability Issues" --output data/processed/calendar_brief.md
```

### 5. Jira Backlog Export (`export-jira`)
Exports opportunities formatted as Epics or Stories ready for Jira's native External System Importer.

```bash
python src/cli.py export-jira --project "PROD" --type "Epic" --format csv --output data/processed/jira_epics.csv
```

---

## Operating Workflow for Claude

When answering customer feedback intelligence queries, follow this systematic workflow:

```
[User Request]
      │
      ▼
[Step 1: Ingest & Prioritize] ──> Run `python src/cli.py analyze ... --format json`
      │
      ▼
[Step 2: Inspect Findings] ─────> Parse JSON output (opportunities, prevalence, ratings, quotes)
      │
      ▼
[Step 3: Optional Benchmark] ───> If competitor URL provided, run `python src/cli.py competitive ...`
      │
      ▼
[Step 4: Generate Brief] ───────> Run `python src/cli.py brief ...` or synthesize executive response
      │
      ▼
[Step 5: Synthesize Answer] ────> Present clear PM recommendations directly to the user
```

### Rules & Guidelines
1. **Zero Fabrication:** Never invent customer statistics, percentages, or competitor capabilities. All claims must be traceable to the output of `src/cli.py` or the uploaded dataset.
2. **Ratings Transparency:** If ratings are absent, clearly state that opportunities are ranked by Complaint Prevalence only.
3. **Hypothesis vs. Fact:** Clearly distinguish engineering root-cause hypotheses from confirmed observations. Customer reviews identify *friction symptoms*, not technical architecture diagnoses.

---

## Reproducible Example

### User Query
> "Analyze these customer reviews, identify the most important product problems, research relevant competitor capabilities using available evidence, and recommend what the product team should prioritize next:
>
> 1. The mobile app takes too long to load.
> 2. Scheduling appointments is confusing.
> 3. The scheduling interface is difficult to navigate.
> 4. The app crashes whenever I open the calendar.
> 5. Calendar keeps crashing on my phone.
>
> Product: TaskFlow"

### Skill Execution
1. **Execute Ingestion & Prioritization:**
   ```bash
   python src/cli.py analyze --text "The mobile app takes too long to load.\nScheduling appointments is confusing.\nThe scheduling interface is difficult to navigate.\nThe app crashes whenever I open the calendar.\nCalendar keeps crashing on my phone." --product "TaskFlow" --format json
   ```

2. **Run Recommendations:**
   ```bash
   python src/cli.py recommend --problem "Calendar" --format json
   ```

3. **Output Synthesized Response:**
   - Summarize the top 3 problem clusters (`Confusing Appointment Scheduling`, `Calendar Reliability Issues`, `Slow Application Performance`).
   - Quote verbatim customer feedback.
   - Present concrete initiatives, proposed MVP boundary, and measurable KPIs (e.g. Crash-free session rate, Task completion rate).

---

## Installation & Setup in Claude Code

1. Ensure the Python environment is set up:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Ensure the skill directory is in your Claude skills path:
   ```bash
   .claude/skills/productiq/SKILL.md
   ```

3. Invoke natural-language queries in Claude Code:
   ```text
   claude "Use ProductIQ to analyze data/feedback/sample_feedback.csv and write an opportunity brief for the top issue."
   ```
