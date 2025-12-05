"""Low-level LLM API call - HTTP only."""

import json
import re
import ssl
import urllib.request
import urllib.error

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def _strip_think_tags(content: str) -> str:
    """Remove <think>...</think> CoT blocks."""
    return re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL)


def call_llm(model: str, prompt: str) -> dict:
    """
    Make HTTP call to LLM API.

    Args:
        model: Full model string (e.g., "gpt-4-turbo")
        prompt: User prompt

    Returns:
        {"success": True, "content": "...", "model": "..."}
        {"success": False, "error": "...", "model": "..."}
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.TEMPERATURE,
        "max_tokens": config.MAX_TOKENS,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.API_KEY}",
    }

    req = urllib.request.Request(
        config.ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=config.TIMEOUT, context=ssl.create_default_context()) as resp:
            result = json.loads(resp.read().decode("utf-8"))

            if "choices" in result and result["choices"]:
                content = _strip_think_tags(result["choices"][0]["message"]["content"])
                return {"success": True, "content": content, "model": model}
            elif "error" in result:
                return {"success": False, "error": str(result["error"]), "model": model}
            else:
                return {"success": False, "error": "Unexpected response format", "model": model}

    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}", "model": model}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"URL Error: {e.reason}", "model": model}
    except TimeoutError:
        return {"success": False, "error": "Request timed out", "model": model}
    except Exception as e:
        return {"success": False, "error": str(e), "model": model}
