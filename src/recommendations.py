from typing import Any, Dict, List, Optional
import pandas as pd


RECOMMENDATION_TEMPLATES = {
    "Performance": {
        "potential_causes": [
            "Hypothesis: Unindexed database queries or heavy join operations during data retrieval.",
            "Hypothesis: Excessive client-side re-rendering or unoptimized asset bundles loading synchronously.",
            "Hypothesis: Absence of response caching or pagination on high-volume data endpoints."
        ],
        "initiatives": [
            "Implement high-impact latency reduction and caching across primary user journeys.",
            "Optimize frontend asset delivery and defer non-critical script execution."
        ],
        "actions": [
            "Instrument client-side telemetry (e.g., Largest Contentful Paint, Time to Interactive).",
            "Introduce server-side cursor pagination and Redis/CDN caching on the affected endpoints.",
            "Audit database query execution plans and add targeted composite indexes.",
            "Conduct bundle analysis to remove unused third-party dependencies."
        ],
        "success_metrics": [
            "P95 page / view load latency (seconds)",
            "P99 API endpoint response time (milliseconds)",
            "Client-side session crash / hang rate (%)",
            "Performance-related customer complaint volume (monthly count)"
        ],
        "mvp_scope": (
            "Add response caching and pagination to the primary sluggish view; "
            "implement baseline client telemetry to track latency improvements."
        ),
        "risks_and_assumptions": [
            "Assumption: Network latency and database bottlenecks dominate over end-user device constraints.",
            "Risk: Aggressive caching policies may cause stale data visibility unless robust invalidation hooks exist.",
            "Risk: Architectural refactoring may require coordination with core backend infrastructure teams."
        ]
    },
    "Reliability": {
        "potential_causes": [
            "Hypothesis: Unhandled runtime edge cases or memory leaks during large file/data buffer operations.",
            "Hypothesis: State synchronization race conditions across asynchronous client components.",
            "Hypothesis: Unbounded file sizes or unsupported mime-types bypassing client-side validation."
        ],
        "initiatives": [
            "Harden application stability, error boundaries, and input validation guards.",
            "Establish automated crash monitoring with actionable diagnostic breadcrumbs."
        ],
        "actions": [
            "Deploy client-side error boundaries to prevent full-application crashes on component failure.",
            "Enforce strict file format and payload size validation with user-facing warnings before upload.",
            "Integrate structured crash telemetry to capture stack traces, device specs, and reproduction breadcrumbs.",
            "Offload resource-intensive parsing tasks to isolated background workers."
        ],
        "success_metrics": [
            "Crash-free user session rate (%)",
            "Fatal exception rate per 1,000 active sessions",
            "Component error rate during the targeted interaction (%)",
            "Mean Time to Detect (MTTD) and Resolve (MTTR) critical defects (hours)"
        ],
        "mvp_scope": (
            "Add pre-upload input validation and graceful error boundary fallbacks; "
            "log detailed client crash diagnostics to pinpoint failure modes."
        ),
        "risks_and_assumptions": [
            "Assumption: Crashes are reproducible across standard browser/OS environments.",
            "Risk: Blocking file uploads with strict format rules may temporarily increase user confusion if errors are unclear.",
            "Risk: Masking errors without root-cause remediation may hide silent data loss."
        ]
    },
    "Notifications": {
        "potential_causes": [
            "Hypothesis: Asynchronous job queue backlog or worker starvation during peak notification dispatch windows.",
            "Hypothesis: Push notification gateway throttling or exponential retry misconfigurations.",
            "Hypothesis: Mobile OS power management / battery saver policies suspending background execution."
        ],
        "initiatives": [
            "Overhaul notification dispatch architecture and delivery reliability monitoring.",
            "Introduce multi-channel failover including persistent in-app notification centers."
        ],
        "actions": [
            "Implement end-to-end delivery timestamp tracking from event trigger to client receipt.",
            "Scale background message queue workers with automated queue-depth auto-scaling.",
            "Add an in-app notification bell / inbox so critical alerts are accessible even if push fails.",
            "Tune retry backoff schedules and configure dead-letter queue alerting."
        ],
        "success_metrics": [
            "End-to-end notification delivery latency (P90 and P99 in seconds)",
            "Notification delivery success rate (%)",
            "In-app notification read / engagement rate (%)",
            "Notification-related support ticket escalations (weekly count)"
        ],
        "mvp_scope": (
            "Add delivery latency timestamps and queue monitoring; deploy a persistent "
            "in-app notification center to ensure mission-critical alerts are not missed."
        ),
        "risks_and_assumptions": [
            "Assumption: Users have granted push notification permissions in their OS settings.",
            "Risk: Aggressive retry storms could trigger downstream rate limits from third-party push services (e.g., APNs, FCM).",
            "Risk: Users may perceive redundant multi-channel notifications as spam if not configurable."
        ]
    },
    "Usability": {
        "potential_causes": [
            "Hypothesis: Non-intuitive information architecture or deep menu nesting obscuring key workflows.",
            "Hypothesis: Lack of visual affordances, progress indicators, or inline form validation.",
            "Hypothesis: Inconsistent terminology across different sections of the product."
        ],
        "initiatives": [
            "Redesign the interaction flow to reduce cognitive friction and streamline user tasks.",
            "Introduce guided onboarding, contextual tooltips, and persistent search shortcuts."
        ],
        "actions": [
            "Conduct 5-8 moderated user testing sessions on the specific confusing workflow.",
            "Consolidate multi-step journeys into a stepped wizard with clear status indicators.",
            "Provide inline validation and actionable error guidance beside form fields.",
            "Flatten navigation hierarchy and introduce global quick-search navigation."
        ],
        "success_metrics": [
            "Task completion rate on the targeted workflow (%)",
            "Average time to complete primary user task (seconds)",
            "Workflow funnel drop-off rate (%)",
            "System Usability Scale (SUS) benchmark score"
        ],
        "mvp_scope": (
            "Redesign the primary friction screen with a simplified 3-step layout, "
            "inline helper text, and contextual validation."
        ),
        "risks_and_assumptions": [
            "Assumption: High drop-off is driven by UI complexity rather than misaligned product value.",
            "Risk: Established power users may experience switching costs if familiar navigation patterns change drastically.",
            "Risk: Simplification must not compromise advanced configuration requirements."
        ]
    },
    "Missing Functionality": {
        "potential_causes": [
            "Hypothesis: Product capability gap where user workflow needs exceed current baseline functionality.",
            "Hypothesis: Lack of self-service customization forcing users into rigid defaults.",
            "Hypothesis: Missing export/interoperability hooks to integrate with downstream reporting tools."
        ],
        "initiatives": [
            "Deliver modular self-serve customization and flexible data export capabilities.",
            "Expand workflow flexibility through user-configurable templates and parameters."
        ],
        "actions": [
            "Survey affected users to rank specific missing parameters and desired export formats.",
            "Build a modular customization panel allowing users to toggle and reorder view components.",
            "Implement standardized export endpoints supporting CSV, PDF, and spreadsheet formats.",
            "Provide saved custom views / filters that persist across user sessions."
        ],
        "success_metrics": [
            "Feature adoption rate (% of active weekly accounts using customization/export)",
            "Export / customization frequency per active user",
            "Customer retention rate among accounts utilizing the new capability (%)",
            "Feature request ticket volume for this capability (monthly trend)"
        ],
        "mvp_scope": (
            "Support the top two most-requested customizations and provide a reliable, "
            "one-click CSV/PDF export capability."
        ),
        "risks_and_assumptions": [
            "Assumption: The requested functionality solves core operational needs across a significant user segment.",
            "Risk: Excessive customization options can increase product complexity and QA maintenance overhead.",
            "Risk: Large asynchronous exports could cause database compute spikes if not rate-limited."
        ]
    },
    "Default": {
        "potential_causes": [
            "Hypothesis: Underlying mismatch between user expectations and system behavior.",
            "Hypothesis: Insufficient logging or user-facing feedback during unexpected edge cases."
        ],
        "initiatives": [
            "Conduct deep-dive discovery and implement targeted product improvements for this workflow.",
            "Strengthen operational instrumentation to systematically capture user friction points."
        ],
        "actions": [
            "Review customer feedback sessions and support tickets to isolate specific friction triggers.",
            "Instrument diagnostic logging and funnels around the affected product area.",
            "Run rapid UX / engineering spike to prototype proposed workflow corrections.",
            "Publish updated user documentation and in-app guidance."
        ],
        "success_metrics": [
            "Workflow completion rate (%)",
            "Category-specific customer satisfaction (CSAT) rating",
            "Customer complaint frequency for this issue"
        ],
        "mvp_scope": (
            "Audit workflow friction points, improve inline guidance, and instrument event tracking."
        ),
        "risks_and_assumptions": [
            "Assumption: Qualitative feedback reflects a repeatable issue rather than an isolated anomaly.",
            "Risk: Premature solutions without sufficient telemetry may miss the root operational cause."
        ]
    }
}


def classify_problem_category(problem_name: str, group_text: str = "") -> str:
    """Classify problem name and text into a core PM problem archetype."""
    combined = f"{problem_name} {group_text}".lower()

    if any(k in combined for k in ["slow", "load", "lag", "speed", "performance", "forever"]):
        return "Performance"
    if any(k in combined for k in ["crash", "freeze", "bug", "broken", "error", "upload", "attachment"]):
        return "Reliability"
    if any(k in combined for k in ["notification", "alert", "reminder", "late", "delay"]):
        return "Notifications"
    if any(k in combined for k in ["confusing", "difficult", "navigate", "complicated", "usability", "schedule", "settings"]):
        return "Usability"
    if any(k in combined for k in ["customize", "customization", "missing", "wish", "export", "limited", "feature", "offline"]):
        return "Missing Functionality"

    return "Default"


def generate_product_recommendation(
    opportunity_row: pd.Series,
    cluster_feedback_df: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """
    Generate an evidence-backed product opportunity recommendation brief.
    Ensures:
      - All customer evidence claims are directly derived from uploaded data.
      - Potential causes are clearly labeled as hypotheses.
      - Recommendations are tailored, concrete, and measurable.
      - No fabricated numbers or artificial ratings.
    """
    problem = str(opportunity_row.get("problem", "Customer Opportunity"))
    complaints = int(opportunity_row.get("complaint_count", 1))
    prevalence_pct = opportunity_row.get("prevalence_pct", 0.0)
    avg_rating = opportunity_row.get("average_rating")
    coverage_pct = opportunity_row.get("rating_coverage_pct", 0.0)
    rep_quote = str(opportunity_row.get("representative_feedback", ""))

    # Extract all real customer quotes from cluster if provided
    quotes = []
    if cluster_feedback_df is not None and not cluster_feedback_df.empty:
        quotes = cluster_feedback_df["feedback"].dropna().tolist()
    if not quotes and rep_quote:
        quotes = [rep_quote]

    combined_text = " ".join(quotes)
    archetype = classify_problem_category(problem, combined_text)
    template = RECOMMENDATION_TEMPLATES.get(archetype, RECOMMENDATION_TEMPLATES["Default"])

    # Build customer evidence summary
    evidence = {
        "complaint_count": complaints,
        "prevalence_pct": prevalence_pct,
        "average_rating": avg_rating,
        "rating_coverage_pct": coverage_pct,
        "representative_quote": rep_quote,
        "supporting_quotes": quotes[:5],  # top real quotes
        "has_ratings": avg_rating is not None
    }

    problem_statement = (
        f"Customers report persistent issues regarding '{problem}', representing "
        f"{complaints} verified complaints ({prevalence_pct}% of total analyzed feedback). "
        + (f"Average user rating for this issue is {avg_rating}/5 across {coverage_pct}% rating coverage."
           if avg_rating is not None else "This issue was submitted without numerical ratings.")
    )

    return {
        "problem_title": problem,
        "archetype": archetype,
        "problem_statement": problem_statement,
        "customer_evidence": evidence,
        "potential_causes": template["potential_causes"],
        "recommended_initiatives": template["initiatives"],
        "actionable_steps": template["actions"],
        "success_metrics": template["success_metrics"],
        "mvp_scope": template["mvp_scope"],
        "risks_and_assumptions": template["risks_and_assumptions"]
    }
