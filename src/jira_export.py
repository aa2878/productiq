import datetime
import io
import json
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests


def map_priority_to_jira(priority_score: Any) -> str:
    """Map ProductIQ priority score (0-100) to standard Jira priority levels."""
    try:
        score = float(priority_score)
        if score >= 60.0:
            return "Highest"
        elif score >= 45.0:
            return "High"
        elif score >= 30.0:
            return "Medium"
        else:
            return "Low"
    except (ValueError, TypeError):
        return "Medium"


def format_jira_description(
    recommendation: Dict[str, Any],
    opportunity_row: pd.Series,
    product_name: str = "Our Product"
) -> str:
    """
    Format a comprehensive Jira description using Jira markup/markdown.
    Compatible with Jira Cloud / Jira Data Center issue views.
    """
    title = recommendation.get("problem_title", opportunity_row.get("problem", "Product Opportunity"))
    evidence = recommendation.get("customer_evidence", {})
    complaints = evidence.get("complaint_count", opportunity_row.get("complaint_count", 1))
    prevalence_pct = evidence.get("prevalence_pct", opportunity_row.get("prevalence_pct", 0.0))
    avg_rating = evidence.get("average_rating", opportunity_row.get("average_rating"))
    coverage_pct = evidence.get("rating_coverage_pct", opportunity_row.get("rating_coverage_pct", 0.0))
    priority_score = opportunity_row.get("priority_score", "N/A")
    methodology = opportunity_row.get("scoring_methodology", "Heuristic")
    quotes = evidence.get("supporting_quotes", [])

    rating_str = f"{avg_rating}/5.0 ({coverage_pct}% coverage)" if avg_rating is not None else "Unrated qualitative feedback"

    quotes_block = "\n".join(f"> \"{q}\"" for q in quotes[:4])
    causes_block = "\n".join(f"* {c}" for c in recommendation.get("potential_causes", []))
    initiatives_block = "\n".join(f"* {i}" for i in recommendation.get("recommended_initiatives", []))
    actions_block = "\n".join(f"* {a}" for a in recommendation.get("actionable_steps", []))
    metrics_block = "\n".join(f"* {m}" for m in recommendation.get("success_metrics", []))
    risks_block = "\n".join(f"* {r}" for r in recommendation.get("risks_and_assumptions", []))

    description = f"""h2. ProductIQ Opportunity: {title}

*Product:* {product_name}
*Priority Score:* {priority_score}/100 ({methodology})
*Impact:* {complaints} complaints ({prevalence_pct}% prevalence) | Rating: {rating_str}

----

h3. Problem Statement
{recommendation.get("problem_statement", "Customer friction identified from feedback analysis.")}

h3. Verified Customer Quotes
{quotes_block if quotes_block else "No direct quotes recorded."}

h3. Potential Causes (Engineering Hypotheses)
{causes_block}

h3. Recommended Product Initiatives
{initiatives_block}

h3. Actionable Implementation Steps
{actions_block}

h3. Proposed MVP Scope
{recommendation.get("mvp_scope", "Define targeted discovery spike.")}

h3. Success Metrics (KPIs)
{metrics_block}

h3. Risks & Assumptions
{risks_block}

----
_Created automatically via ProductIQ AI Product Strategy Assistant_
"""
    return description.strip()


def build_jira_issue_payload(
    project_key: str,
    recommendation: Dict[str, Any],
    opportunity_row: pd.Series,
    issue_type: str = "Epic",
    product_name: str = "Our Product"
) -> Dict[str, Any]:
    """
    Construct standard Jira REST API v2/v3 issue payload.
    """
    title = recommendation.get("problem_title", opportunity_row.get("problem", "Product Opportunity"))
    summary = f"[ProductIQ] {title}"
    description = format_jira_description(recommendation, opportunity_row, product_name)
    jira_priority = map_priority_to_jira(opportunity_row.get("priority_score", 0))

    archetype = recommendation.get("archetype", "General").lower().replace(" ", "-")

    payload = {
        "fields": {
            "project": {"key": project_key.upper().strip()},
            "summary": summary[:250],
            "description": description,
            "issuetype": {"name": issue_type},
            "priority": {"name": jira_priority},
            "labels": ["productiq", "customer-feedback", archetype]
        }
    }
    return payload


def generate_jira_import_csv(
    opportunities_df: pd.DataFrame,
    recommendations_map: Dict[str, Dict[str, Any]],
    project_key: str = "PROD",
    issue_type: str = "Epic",
    product_name: str = "Our Product"
) -> str:
    """
    Generate standard CSV formatted for Jira's native External System Importer.
    Compatible with Jira Cloud and Data Center.
    """
    rows = []
    for _, opp_row in opportunities_df.iterrows():
        prob_name = str(opp_row["problem"])
        rec = recommendations_map.get(prob_name, {})
        description = format_jira_description(rec, opp_row, product_name)
        priority = map_priority_to_jira(opp_row.get("priority_score", 0))
        archetype = rec.get("archetype", "General").lower().replace(" ", "-")

        rows.append({
            "Summary": f"[ProductIQ] {prob_name}",
            "Issue Type": issue_type,
            "Project Key": project_key.upper().strip(),
            "Priority": priority,
            "Description": description,
            "Labels": f"productiq customer-feedback {archetype}",
            "Priority Score": opp_row.get("priority_score", ""),
            "Prevalence Pct": opp_row.get("prevalence_pct", ""),
            "Complaint Count": opp_row.get("complaint_count", "")
        })

    df = pd.DataFrame(rows)
    return df.to_csv(index=False)


def send_to_jira_rest_api(
    jira_base_url: str,
    email: str,
    api_token: str,
    project_key: str,
    recommendation: Dict[str, Any],
    opportunity_row: pd.Series,
    issue_type: str = "Epic",
    product_name: str = "Our Product",
    timeout: int = 10
) -> Tuple[bool, str]:
    """
    Push issue directly to Jira REST API endpoint (POST /rest/api/2/issue).
    Returns (success: bool, message: str).
    """
    base_url = jira_base_url.strip().rstrip("/")
    if not base_url.startswith("http://") and not base_url.startswith("https://"):
        return False, "Invalid Jira URL. Must start with https:// or http://"

    if not email.strip() or not api_token.strip():
        return False, "Jira user email and API token / personal access token are required."

    if not project_key.strip():
        return False, "Jira Project Key is required (e.g., 'PROD')."

    endpoint = f"{base_url}/rest/api/2/issue"
    payload = build_jira_issue_payload(
        project_key=project_key,
        recommendation=recommendation,
        opportunity_row=opportunity_row,
        issue_type=issue_type,
        product_name=product_name
    )

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        response = requests.post(
            endpoint,
            auth=(email.strip(), api_token.strip()),
            headers=headers,
            json=payload,
            timeout=timeout
        )
        if response.status_code in (200, 201):
            data = response.json()
            issue_key = data.get("key", "Created")
            issue_url = f"{base_url}/browse/{issue_key}"
            return True, f"Successfully created Jira {issue_type} {issue_key}: {issue_url}"
        else:
            return False, f"Jira API returned HTTP {response.status_code}: {response.text}"

    except requests.exceptions.Timeout:
        return False, "Jira request timed out. Check network connectivity or Jira server response time."
    except requests.exceptions.ConnectionError:
        return False, f"Could not connect to Jira host at '{base_url}'. Verify URL."
    except requests.exceptions.RequestException as e:
        return False, f"Network error during Jira export: {str(e)}"
