"""Parallel council execution using ThreadPoolExecutor (built-in)."""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from llm.api import call_llm, resolve_model, model_name
from llm.session import (
    get_session_path, read_session_file, write_session_file, session_file_exists
)


def call_single_model(key: str, prompt: str, session_id: Optional[str] = None) -> dict:
    """Call a single model and optionally save to session."""
    model = resolve_model(key)
    result = call_llm(model, prompt)
    result["key"] = key
    result["name"] = model_name(key)
    return result


def call_council(prompt: str, session_id: Optional[str] = None, 
                 add_confidence: bool = False) -> Dict[str, dict]:
    """
    Call all council models in parallel.
    
    Returns dict: {key: result_dict}
    """
    if add_confidence:
        prompt += "\n\n---\nAfter answering, rate your confidence (high/medium/low) for each claim."
    
    models = list(config.MODELS.keys())
    results = {}
    
    def call_model(key: str) -> tuple:
        model = resolve_model(key)
        result = call_llm(model, prompt)
        result["key"] = key
        result["name"] = model_name(key)
        return key, result
    
    # Run all calls in parallel
    with ThreadPoolExecutor(max_workers=len(models)) as executor:
        futures = {executor.submit(call_model, key): key for key in models}
        
        for future in as_completed(futures):
            key, result = future.result()
            results[key] = result
            
            # Save to session if active
            if session_id:
                try:
                    session_path = get_session_path(session_id)
                    council_dir = os.path.join(session_path, "council")
                    os.makedirs(council_dir, exist_ok=True)
                    
                    if result["success"]:
                        with open(os.path.join(council_dir, f"{key}.txt"), "w") as f:
                            f.write(result["content"])
                    else:
                        with open(os.path.join(council_dir, f"{key}.txt"), "w") as f:
                            f.write(f"[[FAILED]] {result.get('error', 'Unknown error')}")
                except Exception:
                    pass  # Don't fail council if session write fails
    
    return results


def run_council_workflow(session_id: Optional[str] = None, 
                         add_confidence: bool = False) -> Dict[str, dict]:
    """
    Run council on the query stored in session.
    
    Raises ValueError if no query in session.
    """
    query = read_session_file("query.txt", session_id)
    if not query:
        raise ValueError("No query in session. Run init first.")
    
    # Warn if no draft (but continue)
    if not session_file_exists("draft.txt", session_id):
        print("[llm-call] Warning: No draft stored. Store draft first for meaningful comparison.")
    
    print("[llm-call] Dispatching to council in parallel...")
    results = call_council(query, session_id, add_confidence)
    
    print("[llm-call] Council complete")
    for key, result in results.items():
        name = result["name"]
        if result["success"]:
            words = len(result["content"].split())
            print(f"[llm-call] {name}: ✓ {words} words")
        else:
            print(f"[llm-call] {name}: ✗ {result.get('error', 'failed')}")
    
    return results


def get_context(session_id: Optional[str] = None) -> str:
    """Get full session context as formatted string."""
    lines = ["# Session Context\n"]
    # Council responses
    lines.append("## Council Responses\n")
    for key in config.MODELS.keys():
        name = model_name(key)
        content = read_session_file(f"council/{key}.txt", session_id)
        lines.append(f"### {name}\n")
        if content:
            if content.startswith("[[FAILED]]"):
                lines.append(f"_{content}_\n")
            else:
                lines.append(content)
        else:
            lines.append("_No response_")
        lines.append("")
    
    return "\n".join(lines)
