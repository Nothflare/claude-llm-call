"""Core API call logic using urllib (built-in)."""

import json
import re
import urllib.request
import urllib.error
import ssl
from typing import Optional

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def strip_think_tags(content: str) -> str:
    """Remove <think>...</think> CoT blocks from response."""
    return re.sub(r'<think>.*?</think>\s*', '', content, flags=re.DOTALL)


def call_llm(model: str, prompt: str, system_prompt: str = "") -> dict:
    """
    Call LLM API and return response dict.
    
    Returns:
        {"success": True, "content": "...", "model": "..."}
        {"success": False, "error": "...", "model": "..."}
    """
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": config.TEMPERATURE,
        "max_tokens": config.MAX_TOKENS,
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.API_KEY}",
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(config.ENDPOINT, data=data, headers=headers, method="POST")
    
    # Create SSL context
    ctx = ssl.create_default_context()
    
    try:
        with urllib.request.urlopen(req, timeout=config.TIMEOUT, context=ctx) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            if "choices" in result and result["choices"]:
                content = result["choices"][0]["message"]["content"]
                content = strip_think_tags(content)
                return {"success": True, "content": content, "model": model}
            elif "error" in result:
                return {"success": False, "error": str(result["error"]), "model": model}
            else:
                return {"success": False, "error": "Unexpected response format", "model": model}
                
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"success": False, "error": f"HTTP {e.code}: {body[:200]}", "model": model}
    except urllib.error.URLError as e:
        return {"success": False, "error": f"URL Error: {e.reason}", "model": model}
    except TimeoutError:
        return {"success": False, "error": "Request timed out", "model": model}
    except Exception as e:
        return {"success": False, "error": str(e), "model": model}


def resolve_model(key: str) -> str:
    """Resolve model key (gpt/gemini/grok) to full model string."""
    return config.MODELS.get(key.lower(), key)


def model_name(key: str) -> str:
    """Get display name for model key."""
    return config.MODEL_NAMES.get(key.lower(), key)
