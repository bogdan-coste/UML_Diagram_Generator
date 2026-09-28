"""
Low-level HTTP client for the local Ollama REST API.
"""

from typing import Optional

import requests

from src.config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT, OLLAMA_TEMPERATURE


def query_ollama(prompt: str, system: str = "") -> Optional[str]:

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": OLLAMA_TEMPERATURE},
    }
    if system:
        payload["system"] = system

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except Exception:
        return None
