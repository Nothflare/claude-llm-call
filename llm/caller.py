"""Unified LLM caller - single and parallel execution."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Union

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

from llm.api import call_llm
from llm import models


def _log(msg: str):
    """Print debug message if enabled."""
    if config.DEBUG_OUTPUT:
        print(msg)


def call(key: str, prompt: str, label: str = "") -> dict:
    """
    Call a single model.

    Args:
        key: Model key (gpt, gemini, grok, qwen)
        prompt: The prompt
        label: Optional label for progress output (e.g., "Probe", "Crossref")

    Returns:
        {"success": bool, "content": str, "error": str, "key": str, "name": str}
    """
    display = f"{label}: " if label else ""
    _log(f"[llm-call] {display}Calling {models.name(key)}...")

    try:
        result = call_llm(models.resolve(key), prompt)
        result["key"] = key
        result["name"] = models.name(key)
    except Exception as e:
        result = {"success": False, "error": str(e), "key": key, "name": models.name(key)}

    status = "OK" if result.get("success") else "FAILED"
    _log(f"[llm-call] {display}{models.name(key)}: {status}")
    return result


def call_parallel(
    prompts: Union[str, Dict[str, str]],
    keys: Optional[List[str]] = None,
    label: str = "",
    add_confidence: bool = False
) -> Dict[str, dict]:
    """
    Call multiple models in parallel.

    Args:
        prompts: Either a single prompt string (same for all) or dict {key: prompt}
        keys: Model keys to call (default: all). Ignored if prompts is dict.
        label: Label for progress output
        add_confidence: Append confidence request to prompt

    Returns:
        Dict mapping key -> result dict
    """
    # Normalize to dict form
    if isinstance(prompts, str):
        keys = keys or models.ALL_KEYS
        prompt_dict = {k: prompts for k in keys}
    else:
        prompt_dict = prompts

    # Add confidence suffix if requested
    if add_confidence:
        suffix = "\n\n---\nAfter answering, rate your confidence (high/medium/low) for each claim."
        prompt_dict = {k: v + suffix for k, v in prompt_dict.items()}

    display = f"{label}: " if label else ""
    results = {}

    max_workers = min(config.MAX_WORKERS, len(prompt_dict))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for key, prompt in prompt_dict.items():
            _log(f"[llm-call] {display}Queuing {models.name(key)}...")
            futures[executor.submit(_call_single, key, prompt)] = key

        for future in as_completed(futures):
            key = futures[future]
            try:
                result = future.result()
            except Exception as e:
                result = {"success": False, "error": str(e), "key": key, "name": models.name(key)}

            results[key] = result
            status = "OK" if result.get("success") else "FAILED"
            _log(f"[llm-call] {display}{models.name(key)}: {status}")

    return results


def _call_single(key: str, prompt: str) -> dict:
    """Internal: call without progress output (for parallel use)."""
    try:
        result = call_llm(models.resolve(key), prompt)
        result["key"] = key
        result["name"] = models.name(key)
        return result
    except Exception as e:
        return {"success": False, "error": str(e), "key": key, "name": models.name(key)}
