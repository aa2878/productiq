import json
from typing import Any, Dict, List, Optional
import requests


def check_local_llm_status(endpoint: str = "http://localhost:11434", timeout: int = 2) -> Dict[str, Any]:
    """
    Check if a local LLM server (e.g. Ollama, LM Studio, or llama.cpp) is running locally.
    Does not require internet access.
    """
    clean_endpoint = endpoint.strip().rstrip("/")
    try:
        # Check Ollama root or tags
        resp = requests.get(f"{clean_endpoint}/api/tags", timeout=timeout)
        if resp.status_code == 200:
            models_info = resp.json().get("models", [])
            model_names = [m.get("name") for m in models_info if "name" in m]
            return {
                "available": True,
                "type": "Ollama",
                "endpoint": clean_endpoint,
                "models": model_names
            }
    except Exception:
        pass

    # Check OpenAI-compatible local endpoints (e.g. LM Studio, llama.cpp, LocalAI)
    try:
        resp = requests.get(f"{clean_endpoint}/v1/models", timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            model_list = [m.get("id") for m in data.get("data", []) if "id" in m]
            return {
                "available": True,
                "type": "Local OpenAI-Compatible Server",
                "endpoint": clean_endpoint,
                "models": model_list
            }
    except Exception:
        pass

    return {
        "available": False,
        "type": "None",
        "endpoint": clean_endpoint,
        "models": []
    }


def query_local_llm(
    prompt: str,
    system_prompt: str = "You are a senior product management assistant. Provide concise, actionable synthesis.",
    endpoint: str = "http://localhost:11434",
    model: Optional[str] = None,
    timeout: int = 8
) -> Optional[str]:
    """
    Query a locally running LLM.
    Returns synthesized text, or None on failure/unreachability.
    Never calls external paid APIs.
    """
    clean_endpoint = endpoint.strip().rstrip("/")

    # Try Ollama native endpoint
    try:
        chosen_model = model or "llama3"
        payload = {
            "model": chosen_model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False
        }
        resp = requests.post(
            f"{clean_endpoint}/api/generate",
            json=payload,
            timeout=timeout
        )
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
    except Exception:
        pass

    # Try OpenAI-compatible chat endpoint (LM Studio / llama.cpp / Ollama /v1)
    try:
        chosen_model = model or "local-model"
        payload = {
            "model": chosen_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 400
        }
        resp = requests.post(
            f"{clean_endpoint}/v1/chat/completions",
            json=payload,
            timeout=timeout
        )
        if resp.status_code == 200:
            choices = resp.json().get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception:
        pass

    return None


def synthesize_local_problem_statement(
    problem_title: str,
    quotes: List[str],
    endpoint: str = "http://localhost:11434",
    model: Optional[str] = None
) -> Optional[str]:
    """
    Use local LLM to optionally polish a problem statement from real quotes.
    Falls back cleanly to None if local model is offline.
    """
    if not quotes:
        return None

    sample_quotes = "\n".join(f"- \"{q}\"" for q in quotes[:4])
    prompt = (
        f"Problem Area: {problem_title}\n"
        f"Customer Quotes:\n{sample_quotes}\n\n"
        f"Write a single concise executive sentence summarizing the core customer friction."
    )
    return query_local_llm(prompt=prompt, endpoint=endpoint, model=model)
