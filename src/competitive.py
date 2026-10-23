import datetime
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


_URL_CACHE: Dict[str, Tuple[str, str]] = {}  # url -> (clean_text, page_title)

CAPABILITY_KEYWORDS = {
    "dashboard": ["dashboard", "overview", "widget", "analytics", "metrics", "chart"],
    "customization": ["customize", "customization", "custom", "drag-and-drop", "layout", "tailor", "preferences"],
    "performance": ["fast", "performance", "speed", "latency", "real-time", "scalable", "instant"],
    "calendar": ["calendar", "scheduling", "events", "agenda", "sync", "booking"],
    "notifications": ["notification", "alert", "reminder", "push", "sms", "email alert", "webhook"],
    "upload": ["upload", "attachment", "import", "file", "document", "cloud storage"],
    "export": ["export", "download", "pdf", "csv", "excel", "report"],
    "search": ["search", "filter", "query", "indexing", "autocomplete"],
    "reliability": ["uptime", "sla", "reliable", "status", "resilient", "backup"]
}


def is_valid_url(url: str) -> bool:
    """Validate URL format."""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def fetch_documentation_content(url: str, timeout: int = 5) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Fetch and extract clean text from a public documentation URL.
    Returns: (clean_text, page_title, error_message).
    Uses caching to avoid redundant downloads.
    """
    url = url.strip()
    if not is_valid_url(url):
        return None, None, "Invalid URL format. Must start with http:// or https://"

    if url in _URL_CACHE:
        clean_text, title = _URL_CACHE[url]
        return clean_text, title, None

    headers = {
        "User-Agent": "ProductIQ/1.0 (Customer Feedback & Product Intelligence Analyzer; +https://github.com/productiq)"
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code != 200:
            return None, None, f"HTTP Error {response.status_code}: {response.reason}"

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return None, None, f"Unsupported Content-Type: {content_type}"

        html_content = response.text
        title = ""
        clean_text = ""

        if BS4_AVAILABLE:
            soup = BeautifulSoup(html_content, "html.parser")
            for elem in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                elem.extract()
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            clean_text = " ".join(soup.stripped_strings)
        else:
            # Fallback regex-based HTML text extractor
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html_content, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else ""
            stripped = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", html_content, flags=re.IGNORECASE | re.DOTALL)
            stripped = re.sub(r"<[^>]+>", " ", stripped)
            clean_text = " ".join(stripped.split())

        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        _URL_CACHE[url] = (clean_text, title)
        return clean_text, title, None

    except requests.exceptions.Timeout:
        return None, None, "Network request timed out (limit: 5s)."
    except requests.exceptions.ConnectionError:
        return None, None, "Connection failed. Documentation server is unreachable or DNS failed."
    except requests.exceptions.RequestException as e:
        return None, None, f"Network error during retrieval: {str(e)}"


def extract_relevant_excerpts(text: str, query_keywords: List[str], max_excerpts: int = 3) -> List[str]:
    """Find sentences from text that mention the query keywords."""
    if not text:
        return []

    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)
    matched = []

    for s in sentences:
        s_clean = s.strip()
        if len(s_clean) < 20 or len(s_clean) > 300:
            continue
        s_lower = s_clean.lower()
        if any(kw.lower() in s_lower for kw in query_keywords):
            matched.append(s_clean)
            if len(matched) >= max_excerpts:
                break

    return matched


def analyze_competitor_capability(
    competitor_name: str,
    problem_title: str,
    documentation_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compare an identified customer problem against a competitor's public documentation.
    Strictly follows evidence attribution rules:
      - Supported by evidence
      - Partially supported
      - Not established
      - Unable to verify
    Never fabricates findings.
    """
    today_str = datetime.date.today().isoformat()
    competitor = competitor_name.strip() if competitor_name else "Competitor"

    if not documentation_url or not documentation_url.strip():
        return {
            "competitor": competitor,
            "problem_compared": problem_title,
            "relevant_capability": f"Analysis for '{problem_title}'",
            "evidence_summary": "No documentation URL was provided. Feature presence or gap is unverified.",
            "source_url": "N/A",
            "retrieval_date": today_str,
            "status": "Not established",
            "confidence": "Low"
        }

    url = documentation_url.strip()
    text, title, error = fetch_documentation_content(url)

    if error:
        return {
            "competitor": competitor,
            "problem_compared": problem_title,
            "relevant_capability": f"Analysis for '{problem_title}'",
            "evidence_summary": f"Could not verify competitor documentation: {error}",
            "source_url": url,
            "retrieval_date": today_str,
            "status": "Unable to verify",
            "confidence": "None"
        }

    # Derive search keywords from problem title
    prob_lower = problem_title.lower()
    search_keywords = []
    for concept, kws in CAPABILITY_KEYWORDS.items():
        if concept in prob_lower or any(k in prob_lower for k in kws):
            search_keywords.extend(kws)

    if not search_keywords:
        # Extract alphanumeric words longer than 3 characters
        search_keywords = [w for w in re.findall(r"\b[a-zA-Z]{4,}\b", prob_lower)]

    excerpts = extract_relevant_excerpts(text, search_keywords, max_excerpts=3)

    if excerpts:
        # Verify if excerpt has multiple matching terms
        strong_matches = [
            ex for ex in excerpts
            if sum(1 for kw in search_keywords if kw.lower() in ex.lower()) >= 2
        ]

        if strong_matches:
            status = "Supported by evidence"
            confidence = "High"
            summary = f"Documentation confirms capability: \"{strong_matches[0]}\""
        else:
            status = "Partially supported"
            confidence = "Moderate"
            summary = f"Documentation mentions related keywords: \"{excerpts[0]}\""

        return {
            "competitor": competitor,
            "problem_compared": problem_title,
            "relevant_capability": f"Competitor feature addressing '{problem_title}'",
            "evidence_summary": summary,
            "source_url": url,
            "page_title": title,
            "retrieval_date": today_str,
            "status": status,
            "confidence": confidence,
            "excerpts": excerpts
        }
    else:
        return {
            "competitor": competitor,
            "problem_compared": problem_title,
            "relevant_capability": f"Feature addressing '{problem_title}'",
            "evidence_summary": (
                f"No direct mention of capability matching '{problem_title}' "
                f"was found on the retrieved page. Note: Missing documentation "
                f"does not confirm the absence of this feature."
            ),
            "source_url": url,
            "page_title": title,
            "retrieval_date": today_str,
            "status": "Not established",
            "confidence": "Moderate"
        }
