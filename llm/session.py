"""Session management for council workflows with step-based folders."""

import os
import json
from datetime import datetime
from typing import Optional, Dict

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def get_session_dir() -> str:
    """Get session directory, create if needed."""
    os.makedirs(config.SESSION_DIR, exist_ok=True)
    return config.SESSION_DIR


def new_session() -> str:
    """Create new session with step 1, return ID."""
    session_id = f"s_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    session_path = os.path.join(get_session_dir(), session_id)
    os.makedirs(session_path, exist_ok=True)

    # Create step 1 folder
    os.makedirs(os.path.join(session_path, "1"), exist_ok=True)

    # Mark as current
    with open(os.path.join(get_session_dir(), ".current"), "w") as f:
        f.write(session_id)

    # Write metadata
    metadata = {
        "created": datetime.now().isoformat(),
        "current_step": 1
    }
    with open(os.path.join(session_path, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return session_id


def get_current_session() -> Optional[str]:
    """Get current session ID."""
    current_file = os.path.join(get_session_dir(), ".current")
    if os.path.exists(current_file):
        with open(current_file) as f:
            return f.read().strip()
    return None


def get_session_path(session_id: Optional[str] = None) -> str:
    """Get path to session directory."""
    if session_id is None:
        session_id = get_current_session()
    if session_id is None:
        raise ValueError("No active session. Run init first.")
    
    path = os.path.join(get_session_dir(), session_id)
    if not os.path.isdir(path):
        raise ValueError(f"Session not found: {session_id}")
    return path


def clear_session(session_id: Optional[str] = None):
    """Delete session."""
    import shutil
    path = get_session_path(session_id)
    shutil.rmtree(path, ignore_errors=True)
    
    # Clear current marker if this was current
    current = get_current_session()
    if current == session_id or session_id is None:
        current_file = os.path.join(get_session_dir(), ".current")
        if os.path.exists(current_file):
            os.remove(current_file)


def get_current_step(session_id: Optional[str] = None) -> int:
    """Get current step number for session."""
    path = get_session_path(session_id)
    metadata_file = os.path.join(path, "metadata.json")
    if os.path.exists(metadata_file):
        with open(metadata_file) as f:
            metadata = json.load(f)
            return metadata.get("current_step", 1)
    return 1


def create_next_step(session_id: Optional[str] = None) -> int:
    """Create next step folder and return new step number."""
    path = get_session_path(session_id)
    current_step = get_current_step(session_id)
    next_step = current_step + 1

    # Create new step folder
    step_path = os.path.join(path, str(next_step))
    os.makedirs(step_path, exist_ok=True)

    # Update metadata
    metadata_file = os.path.join(path, "metadata.json")
    if os.path.exists(metadata_file):
        with open(metadata_file) as f:
            metadata = json.load(f)
    else:
        metadata = {"created": datetime.now().isoformat()}

    metadata["current_step"] = next_step
    metadata["last_updated"] = datetime.now().isoformat()

    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)

    return next_step


def save_step_data(step: int, data: Dict[str, str], session_id: Optional[str] = None):
    """
    Save data to step folder.
    data keys: query, draft, gpt, gemini, grok
    """
    path = get_session_path(session_id)
    step_path = os.path.join(path, str(step))
    os.makedirs(step_path, exist_ok=True)

    for key, content in data.items():
        if content:
            filename = f"{key}.md"
            with open(os.path.join(step_path, filename), "w", encoding="utf-8") as f:
                f.write(content)


def load_step_data(step: int, session_id: Optional[str] = None) -> Dict[str, str]:
    """Load all data from a step folder."""
    path = get_session_path(session_id)
    step_path = os.path.join(path, str(step))

    data = {}
    if os.path.isdir(step_path):
        for filename in os.listdir(step_path):
            if filename.endswith(".md"):
                key = filename[:-3]  # Remove .md
                with open(os.path.join(step_path, filename), encoding="utf-8") as f:
                    data[key] = f.read()

    return data


def get_session_context(session_id: Optional[str] = None) -> list:
    """Get all steps' data for building probe context."""
    path = get_session_path(session_id)
    steps = []

    # Find all step folders
    for item in sorted(os.listdir(path)):
        if item.isdigit() and os.path.isdir(os.path.join(path, item)):
            step_num = int(item)
            step_data = load_step_data(step_num, session_id)
            steps.append({"step": step_num, "data": step_data})

    return steps
