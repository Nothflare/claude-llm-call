#!/usr/bin/env python3
"""LLM Call CLI - External LLM orchestration for Claude."""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm import models
from llm.caller import call, call_parallel
from llm.parse import parse_stdin
from llm.session import (
    new_session, get_current_session, get_session_path, clear_session,
    get_current_step, create_next_step, save_step_data, load_step_data, get_session_context
)


# ============================================================================
# Commands
# ============================================================================

def cmd_single(args):
    """Query single model."""
    if not args.model:
        print("ERROR: -M required (gpt|gemini|grok)")
        sys.exit(1)

    stdin = _require_stdin()
    data = parse_stdin(stdin)
    if not data["query"]:
        print("ERROR: No ===QUERY=== found")
        sys.exit(1)

    session_id, step = _get_or_create_session(args.session)
    result = call(args.model, data["query"])

    if not result["success"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    save_step_data(step, {
        "query": data["query"],
        args.model: result["content"],
        **({"draft": data["draft"]} if data["draft"] else {})
    }, session_id)

    _print_result(result)
    print(f"[{session_id} step {step}]")


def cmd_council(args):
    """Query all models in parallel."""
    stdin = _require_stdin()
    data = parse_stdin(stdin)
    if not data["query"]:
        print("ERROR: No ===QUERY=== found")
        sys.exit(1)

    session_id, step = _get_or_create_session(args.session)
    results = call_parallel(data["query"], add_confidence=args.confidence)

    # Save
    step_data = {"query": data["query"]}
    if data["draft"]:
        step_data["draft"] = data["draft"]
    for key, result in results.items():
        if result["success"]:
            step_data[key] = result["content"]
    save_step_data(step, step_data, session_id)

    # Output
    print()
    for result in results.values():
        _print_result(result)
    print(f"[{session_id} step {step}]")


def cmd_probe(args):
    """Follow-up question with session context."""
    stdin = _require_stdin()
    data = parse_stdin(stdin)
    if not data["query"]:
        print("ERROR: No ===QUERY=== found")
        sys.exit(1)

    target = args.model or data["probe_model"]
    if not target:
        print("ERROR: Specify model with -M or ===PROBE=== @model")
        sys.exit(1)

    session_id = args.session or get_current_session()
    if not session_id:
        print("ERROR: No session")
        sys.exit(1)

    # Build context from session history
    context = []
    for step_info in get_session_context(session_id):
        step_data = step_info["data"]
        context.append(f"--- Step {step_info['step']} ---")
        if "query" in step_data:
            context.append(f"Q: {step_data['query']}")
        for key in models.ALL_KEYS:
            if key in step_data:
                resp = step_data[key][:800] + "..." if len(step_data[key]) > 800 else step_data[key]
                context.append(f"{models.name(key)}: {resp}")
    context.append(f"\n--- New Q ---\n{data['query']}")

    result = call(target, "\n\n".join(context), label="Probe")
    if not result["success"]:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    step = create_next_step(session_id)
    save_step_data(step, {"query": data["query"], target: result["content"]}, session_id)

    _print_result(result, suffix="Probe")
    print(f"[{session_id} step {step}]")


def cmd_crossref(args):
    """Models critique each other's responses."""
    session_id = args.session or get_current_session()
    if not session_id:
        print("ERROR: No session")
        sys.exit(1)

    current_step = get_current_step(session_id)
    step_data = load_step_data(current_step, session_id)

    # Check for stdin draft
    if not sys.stdin.isatty():
        data = parse_stdin(sys.stdin.read())
        if data["draft"] and "draft" not in step_data:
            save_step_data(current_step, {"draft": data["draft"]}, session_id)
            step_data["draft"] = data["draft"]

    query = step_data.get("query", "")
    draft = step_data.get("draft", "")
    model_responses = {k: step_data.get(k) for k in models.ALL_KEYS}

    # Need at least 1 response
    if not any(model_responses.values()) and not draft:
        print("ERROR: Need at least 1 response. Run council first.")
        sys.exit(1)

    # Require draft for crossref - Claude's perspective is essential
    if not draft:
        print("ERROR: No draft found. Crossref requires Claude's draft to compare perspectives.")
        sys.exit(1)

    # Build prompts (each model sees others' responses)
    prompts = {}
    for key in models.ALL_KEYS:
        others = []
        if draft:
            others.append(f"Claude: {draft}")
        for k, v in model_responses.items():
            if k != key and v:
                others.append(f"{models.name(k)}: {v}")

        parts = []
        if query:
            parts.append(f"Original Q: {query}")
        if model_responses[key]:
            parts.append(f"\nYour previous answer:\n{model_responses[key]}")
        parts.append("\nOther responses:\n" + "\n".join(others))
        parts.append("\n---\nComment on others' responses. Agree/disagree? What insights or errors do you see?")
        prompts[key] = "\n".join(parts)

    results = call_parallel(prompts, label="Crossref")

    step = create_next_step(session_id)
    new_step_data = {"query": "Crossref"}
    print()
    for key, result in results.items():
        if result["success"]:
            new_step_data[f"{key}_crossref"] = result["content"]
        _print_result(result, suffix="Crossref")

    save_step_data(step, new_step_data, session_id)
    print(f"[{session_id} step {step}]")


def cmd_status(args):
    """Show session status."""
    session_id = args.session or get_current_session()
    if not session_id:
        print("ERROR: No session")
        sys.exit(1)

    path = get_session_path(session_id)
    steps = sorted([d for d in os.listdir(path) if d.isdigit()], key=int)
    print(f"{session_id}: {len(steps)} steps")
    for step in steps:
        files = [f.replace('.md', '') for f in os.listdir(os.path.join(path, step)) if f.endswith('.md')]
        print(f"  {step}/: {', '.join(files)}")


def cmd_clear(args):
    """Clear session."""
    session_id = args.session or get_current_session()
    if not session_id:
        print("ERROR: No session")
        sys.exit(1)
    clear_session(session_id)
    print(f"Cleared {session_id}")


# ============================================================================
# Helpers
# ============================================================================

def _require_stdin() -> str:
    """Require and return stdin content."""
    if sys.stdin.isatty():
        print("ERROR: Pipe stdin with ===QUERY===")
        sys.exit(1)
    return sys.stdin.read()


def _get_or_create_session(session_arg: str = None) -> tuple:
    """Get or create session, return (session_id, step)."""
    if session_arg == "new":
        # Force new session
        session_id = new_session()
        step = 1
    elif session_arg:
        # Use specified session
        session_id = session_arg
        step = create_next_step(session_id)
    else:
        # Use current or create new
        session_id = get_current_session() or new_session()
        step = 1 if get_current_step(session_id) == 1 else create_next_step(session_id)
    return session_id, step


def _print_result(result: dict, suffix: str = ""):
    """Print formatted result."""
    name = result["name"]
    if suffix:
        name = f"{name} ({suffix})"
    print(f"### {name}\n")
    if result["success"]:
        print(f"{result['content']}\n")
    else:
        # Show detailed error info so Claude knows what happened
        error = result.get('error', 'Unknown error')
        model = result.get('model', result.get('key', 'unknown'))
        print(f"[ERROR] Call to {model} failed: {error}\n")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="LLM Call - External LLM orchestration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  council   Query all models in parallel
  single    Query one model (-M required)
  probe     Follow-up with session context
  crossref  Models critique each other
  status    Show session
  clear     Delete session

Input format (stdin):
  ===QUERY===
  Your question

  ===DRAFT===  (optional)
  Claude's answer

  ===PROBE===  (probe mode)
  @gpt/@gemini/@grok/@qwen
"""
    )

    parser.add_argument("-m", "--mode", required=True,
                        choices=["council", "single", "probe", "crossref", "status", "clear"])
    parser.add_argument("-M", "--model", choices=models.ALL_KEYS)
    parser.add_argument("-S", "--session", help="Session ID")
    parser.add_argument("-c", "--confidence", action="store_true")

    args = parser.parse_args()

    commands = {
        "council": cmd_council,
        "single": cmd_single,
        "probe": cmd_probe,
        "crossref": cmd_crossref,
        "status": cmd_status,
        "clear": cmd_clear,
    }
    commands[args.mode](args)


if __name__ == "__main__":
    main()
