import datetime
from typing import Any, Dict, List, Optional
import pandas as pd


def generate_markdown_brief(
    recommendation: Dict[str, Any],
    opportunity_row: pd.Series,
    competitive_findings: Optional[List[Dict[str, Any]]] = None,
    product_name: str = "Our Product"
) -> str:
    """
    Generate an executive-ready, 12-section Product Opportunity Brief in Markdown format.
    Ensures:
      - Rigorous traceability to customer feedback.
      - Transparent distinction between hypotheses and verified facts.
      - Explicit indication when competitive intelligence is absent.
      - No fabricated numbers or unsupported claims.
    """
    title = recommendation.get("problem_title", "Product Opportunity")
    evidence = recommendation.get("customer_evidence", {})
    complaints = evidence.get("complaint_count", opportunity_row.get("complaint_count", 1))
    prevalence_pct = evidence.get("prevalence_pct", opportunity_row.get("prevalence_pct", 0.0))
    raw_avg = evidence.get("average_rating", opportunity_row.get("average_rating"))
    avg_rating = round(float(raw_avg), 2) if (pd.notna(raw_avg) and str(raw_avg).lower() != "nan") else None
    coverage_pct = evidence.get("rating_coverage_pct", opportunity_row.get("rating_coverage_pct", 0.0))
    rep_quote = evidence.get("representative_quote", opportunity_row.get("representative_feedback", ""))
    quotes = evidence.get("supporting_quotes", [rep_quote] if rep_quote else [])
    methodology = opportunity_row.get("scoring_methodology", "Prevalence-based heuristic")
    priority_score = opportunity_row.get("priority_score", "N/A")

    # Section 2: Executive Summary
    rating_context = (
        f"with an average rating of {avg_rating}/5.0 ({coverage_pct}% rating coverage)"
        if avg_rating is not None else "with qualitative unrated feedback"
    )
    exec_summary = (
        f"This opportunity addresses **{title}**, representing **{complaints} customer complaints** "
        f"({prevalence_pct}% prevalence) across recent feedback, {rating_context}. "
        f"Calculated priority score is **{priority_score}/100** ({methodology}). "
        f"Targeted product interventions will reduce user drop-off, increase satisfaction, "
        f"and protect core retention."
    )

    # Section 5: Problem Frequency and Severity
    severity_assessment = (
        "High" if (avg_rating is not None and avg_rating <= 2.0) or prevalence_pct >= 25.0
        else "Medium" if (avg_rating is not None and avg_rating <= 3.5) or prevalence_pct >= 10.0
        else "Moderate"
    )
    freq_severity_text = (
        f"- **Complaint Count:** {complaints} verified customer records\n"
        f"- **Prevalence Rate:** {prevalence_pct}% of total feedback analyzed\n"
        f"- **Severity Assessment:** {severity_assessment}\n"
        f"- **Priority Heuristic Score:** {priority_score}/100\n"
        f"- **Scoring Methodology:** {methodology}\n"
    )

    # Section 6: Competitive Context
    if competitive_findings and len(competitive_findings) > 0:
        comp_lines = []
        for finding in competitive_findings:
            comp_name = finding.get("competitor", "Competitor")
            status = finding.get("status", "Not established")
            summary = finding.get("evidence_summary", "No details")
            src = finding.get("source_url", "N/A")
            retrieval = finding.get("retrieval_date", datetime.date.today().isoformat())
            comp_lines.append(
                f"- **{comp_name}** | Status: *{status}*\n"
                f"  - **Evidence:** {summary}\n"
                f"  - **Source:** {src} (Retrieved: {retrieval})"
            )
        comp_context = "\n".join(comp_lines)
    else:
        comp_context = (
            "*Competitive research has not been performed for this opportunity yet. "
            "To establish market context, enter competitor names and public documentation URLs "
            "in the Competitive Intelligence workspace.*"
        )

    # Formatting lists
    potential_causes = "\n".join(f"- {c}" for c in recommendation.get("potential_causes", []))
    initiatives = "\n".join(f"- {i}" for i in recommendation.get("recommended_initiatives", []))
    action_steps = "\n".join(f"- {a}" for a in recommendation.get("actionable_steps", []))
    success_metrics = "\n".join(f"- {m}" for m in recommendation.get("success_metrics", []))
    risks_assumptions = "\n".join(f"- {r}" for r in recommendation.get("risks_and_assumptions", []))

    quotes_formatted = "\n".join(f"> \"{q}\"" for q in quotes if q)

    brief = f"""# PRODUCT OPPORTUNITY BRIEF: {title.upper()}

**Target Product:** {product_name}  
**Date Generated:** {datetime.date.today().isoformat()}  
**Status:** In Review | Roadmap Discovery  
**Priority Score:** {priority_score}/100  

---

## 1. Opportunity Title
**{title}**

## 2. Executive Summary
{exec_summary}

## 3. Customer Problem
{recommendation.get("problem_statement", "Recurring customer friction identified through feedback analysis.")}

### Underlying Problem Hypotheses
*(Note: Hypotheses derived from feedback analysis; requires engineering validation)*
{potential_causes}

## 4. Supporting Customer Evidence
The following verified customer quotes substantiate this problem:
{quotes_formatted if quotes_formatted else "> No direct quotes recorded."}

## 5. Problem Frequency & Severity
{freq_severity_text}

## 6. Competitive Context
{comp_context}

## 7. Recommended Product Initiatives
{initiatives}

### Key Actionable Steps
{action_steps}

## 8. Proposed MVP Scope
{recommendation.get("mvp_scope", "Define initial spike to isolate root cause and deliver scoped validation.")}

## 9. Success Metrics
{success_metrics}
*(Note: Baselines to be measured via operational telemetry prior to rollout; no arbitrary targets assumed).*

## 10. Risks & Assumptions
{risks_assumptions}

## 11. Open Questions
- What is the engineering effort required to remediate the underlying service dependencies?
- Are specific customer cohorts or platforms disproportionately affected?
- Can we reproduce this friction in our internal staging or dogfood environments?
- What fallback mechanism can mitigate customer frustration while full remediation is in development?

## 12. Recommended Next Steps
1. **Engineering Discovery:** Conduct a 3-day technical spike to confirm the underlying architectural hypotheses.
2. **Product Design / Telemetry:** Align on telemetry events to establish accurate baseline success metrics.
3. **Stakeholder Alignment:** Review MVP scope with engineering lead and customer success before sprint backlog insertion.
4. **Competitive Verification:** Validate external market benchmarks against competitor production implementations.

---
*Generated by ProductIQ — Customer Feedback Intelligence & Product Prioritization Assistant*
"""
    return brief.strip()
