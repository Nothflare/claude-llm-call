#!/usr/bin/env python3
"""LLM Call CLI - External LLM orchestration for Claude."""

import sys
import os
import argparse

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from llm.api import call_llm, resolve_model, model_name
from llm.session import (
    new_session, get_current_session, get_session_path,
    write_session_file, read_session_file, session_file_exists,
    clear_session, list_sessions
)
from llm.council import run_council_workflow, get_context, call_single_model


def cmd_single(args):
    """Query single model."""
    if not args.model:
        print("[ERROR] Model required (-M gpt|gemini|grok)")
        sys.exit(1)
    
    content = read_input(args)
    if not content:
        print("[ERROR] No input. Use -f <file> or pipe stdin.")
        sys.exit(1)
    
    print(f"[llm-call] Querying {model_name(args.model)}...")
    result = call_single_model(args.model, content)
    
    if result["success"]:
        print(result["content"])
    else:
        print(f"[ERROR] {result['error']}")
        sys.exit(1)


def cmd_init(args):
    """Initialize new session."""
    content = read_input(args)
    if not content:
        print("[ERROR] No query. Use -f <file> or pipe stdin.")
        sys.exit(1)
    
    session_id = new_session()
    write_session_file("query.txt", content, session_id)
    
    # Clean up staging file
    if args.file and args.file.startswith("/tmp/") and os.path.exists(args.file):
        os.remove(args.file)
    
    print(session_id)


def cmd_draft(args):
    """Store Claude's draft."""
    content = read_input(args)
    if not content:
        print("[ERROR] No draft content. Use -f <file> or pipe stdin.")
        sys.exit(1)
    
    session_id = args.session or get_current_session()
    if not session_id:
        print("[ERROR] No active session. Run init first.")
        sys.exit(1)
    
    write_session_file("draft.txt", content, session_id)
    
    # Clean up staging file
    if args.file and args.file.startswith("/tmp/") and os.path.exists(args.file):
        os.remove(args.file)
    
    print("[llm-call] Draft stored")


def cmd_council(args):
    """Run council on session query."""
    session_id = args.session or get_current_session()
    if not session_id:
        print("[ERROR] No active session. Run init first.")
        sys.exit(1)
    
    try:
        run_council_workflow(session_id, args.confidence)
        print()
        print("Run: llm-call -m context")
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


def cmd_context(args):
    """Display full session context."""
    session_id = args.session or get_current_session()
    if not session_id:
        print("[ERROR] No active session. Run init first.")
        sys.exit(1)
    
    try:
        print(get_context(session_id))
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


def cmd_probe(args):
    """Follow-up question to specific model."""
    if not args.model:
        print("[ERROR] Model required (-M gpt|gemini|grok)")
        sys.exit(1)
    
    content = read_input(args)
    if not content:
        print("[ERROR] No probe query. Use -f <file> or pipe stdin.")
        sys.exit(1)
    
    session_id = args.session or get_current_session()
    if not session_id:
        print("[ERROR] No active session. Run init first.")
        sys.exit(1)
    
    # Build context
    ctx_parts = []
    
    query = read_session_file("query.txt", session_id)
    if query:
        ctx_parts.append(f"Original question: {query}")
    
    # Previous response from this model
    prev = read_session_file(f"council/{args.model}.txt", session_id)
    if prev and not prev.startswith("[[FAILED]]"):
        ctx_parts.append(f"Your previous answer:\n{prev}")
    
    # Other models' responses
    ctx_parts.append("Other models said:")
    for key in config.MODELS.keys():
        if key == args.model:
            continue
        other = read_session_file(f"council/{key}.txt", session_id)
        if other and not other.startswith("[[FAILED]]"):
            name = model_name(key)
            # Truncate if too long
            if len(other) > 1500:
                other = other[:1500] + "..."
            ctx_parts.append(f"\n--- {name} ---\n{other}")
    
    ctx_parts.append(f"\n---\nFollow-up question:\n{content}")
    
    full_prompt = "\n\n".join(ctx_parts)
    
    print(f"[llm-call] Probing {model_name(args.model)}...")
    result = call_single_model(args.model, full_prompt)
    
    if result["success"]:
        # Save probe
        probe_dir = os.path.join(get_session_path(session_id), "probes")
        os.makedirs(probe_dir, exist_ok=True)
        n = 1
        while os.path.exists(os.path.join(probe_dir, f"{args.model}_{n}.txt")):
            n += 1
        with open(os.path.join(probe_dir, f"{args.model}_{n}.txt"), "w") as f:
            f.write(result["content"])
        with open(os.path.join(probe_dir, f"{args.model}_{n}_q.txt"), "w") as f:
            f.write(content)
        
        print(f"\n=== {result['name']} (probe {n}) ===")
        print(result["content"])
    else:
        print(f"[ERROR] {result['error']}")
        sys.exit(1)


def cmd_clear(args):
    """Clear session."""
    session_id = args.session or get_current_session()
    if not session_id:
        print("[ERROR] No active session.")
        sys.exit(1)
    
    clear_session(session_id)
    print(f"[llm-call] Cleared: {session_id}")


def cmd_status(args):
    """Show session status."""
    session_id = args.session or get_current_session()
    if not session_id:
        print("[ERROR] No active session.")
        sys.exit(1)
    
    try:
        path = get_session_path(session_id)
        print(f"Session: {session_id}")
        print(f"Path: {path}")
        print()
        
        if session_file_exists("query.txt", session_id):
            print("✓ query.txt")
        if session_file_exists("draft.txt", session_id):
            print("✓ draft.txt")
        
        council_dir = os.path.join(path, "council")
        if os.path.isdir(council_dir):
            files = [f for f in os.listdir(council_dir) if f.endswith(".txt")]
            print(f"✓ council/ ({len(files)} files)")
        
        probes_dir = os.path.join(path, "probes")
        if os.path.isdir(probes_dir):
            files = [f for f in os.listdir(probes_dir) if f.endswith(".txt") and "_q" not in f]
            print(f"✓ probes/ ({len(files)} probes)")
            
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


def read_input(args) -> str:
    """Read input from file or stdin."""
    if args.file:
        if not os.path.exists(args.file):
            print(f"[ERROR] File not found: {args.file}")
            sys.exit(1)
        with open(args.file) as f:
            return f.read()
    elif not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="LLM Call - External LLM orchestration for Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  single    Query one model (requires -M)
  init      Start new session with query
  draft     Store Claude's draft in session
  council   Query all models in parallel
  context   Display session (query + draft + responses)
  probe     Follow-up to specific model (requires -M)
  status    Show session files
  clear     Delete session

Examples:
  echo "Question" | llm-call -m single -M gpt
  llm-call -m init -f /tmp/query.txt
  llm-call -m draft -f /tmp/draft.txt
  llm-call -m council -c
  llm-call -m context
"""
    )
    
    parser.add_argument("-m", "--mode", required=True,
                        choices=["single", "init", "draft", "council", "context", "probe", "status", "clear"],
                        help="Operation mode")
    parser.add_argument("-M", "--model", choices=["gpt", "gemini", "grok"],
                        help="Target model")
    parser.add_argument("-f", "--file", help="Read input from file")
    parser.add_argument("-S", "--session", help="Use specific session ID")
    parser.add_argument("-c", "--confidence", action="store_true",
                        help="Request confidence ratings")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Quiet mode")
    
    args = parser.parse_args()
    
    # Dispatch to command
    commands = {
        "single": cmd_single,
        "init": cmd_init,
        "draft": cmd_draft,
        "council": cmd_council,
        "context": cmd_context,
        "probe": cmd_probe,
        "status": cmd_status,
        "clear": cmd_clear,
    }
    
    commands[args.mode](args)


if __name__ == "__main__":
    main()
