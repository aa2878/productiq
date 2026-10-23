# ProductIQ Reference Documentation

## 1. Problem Archetype Taxonomy & Mapping

| Archetype | Trigger Keywords | Default Initiative Strategy | Target KPIs |
| :--- | :--- | :--- | :--- |
| **Performance** | slow, load, lag, speed, forever, render | Latency reduction, Redis/CDN caching, query optimization | P95 view load time (s), P99 API latency (ms) |
| **Reliability** | crash, freeze, error, broken, bug, upload | Input validation boundaries, error handling, worker offloading | Crash-free session rate (%), Fatal exception count |
| **Notifications** | notification, alert, reminder, late, delay | Queue scaling, delivery latency telemetry, in-app notification center | Delivery latency (s), Push success rate (%) |
| **Usability** | confusing, difficult, navigate, complicated | Workflow consolidation, wizard layout, contextual guidance | Task completion rate (%), Funnel drop-off rate (%) |
| **Missing Functionality** | wish, missing, customize, export, limited | Modular self-serve configuration, standardized export endpoints | Feature adoption rate (%), Export frequency |

---

## 2. Standardized 12-Section Product Opportunity Brief Schema

Every generated Product Brief adheres to the following structure:
1. **Opportunity Title:** Concise, professional problem label.
2. **Executive Summary:** Synthesized overview of customer complaints, volume, rating context, priority score, and strategic impact.
3. **Customer Problem:** Detailed problem statement and underlying engineering hypotheses.
4. **Supporting Customer Evidence:** Verbatim customer quotes extracted from the dataset.
5. **Problem Frequency & Severity:** Verified complaints, prevalence percentage, severity rating, and scoring methodology.
6. **Competitive Context:** Evidence status, excerpts, source URLs, and retrieval dates (or disclosure that research was unperformed).
7. **Recommended Product Initiatives:** Strategic initiatives and concrete actionable implementation steps.
8. **Proposed MVP Scope:** Initial delivery boundary for rapid validation.
9. **Success Metrics:** Measurable product KPIs (without fabricated baselines).
10. **Risks & Assumptions:** Key technical and operational unknowns.
11. **Open Questions:** Architectural, design, and cohort discovery questions.
12. **Recommended Next Steps:** Concrete discovery spikes and telemetry alignment items.

---

## 3. Jira Issue Mapping Specification

When exporting to Jira:
- **Summary:** `[ProductIQ] <Problem Title>`
- **Issue Type:** `Epic` (default), `Story`, or `Task`
- **Priority:**
  - `Highest`: Priority Score $\ge 60.0$
  - `High`: $45.0 \le$ Priority Score $< 60.0$
  - `Medium`: $30.0 \le$ Priority Score $< 45.0$
  - `Low`: Priority Score $< 30.0$
- **Labels:** `productiq`, `customer-feedback`, `<archetype>`
- **Description:** Formatted Jira wiki markup containing the Problem Statement, Customer Quotes, Hypotheses, Initiatives, Actions, and Success Metrics.
