"""Session management for council workflows."""

import os
import json
from datetime import datetime
from typing import Optional

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


def get_session_dir() -> str:
    """Get session directory, create if needed."""
    os.makedirs(config.SESSION_DIR, exist_ok=True)
    return config.SESSION_DIR


def new_session() -> str:
    """Create new session, return ID."""
    session_id = f"s_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    session_path = os.path.join(get_session_dir(), session_id)
    os.makedirs(session_path, exist_ok=True)
    os.makedirs(os.path.join(session_path, "council"), exist_ok=True)
    
    # Mark as current
    with open(os.path.join(get_session_dir(), ".current"), "w") as f:
        f.write(session_id)
    
    # Write timestamp
    with open(os.path.join(session_path, "timestamp.txt"), "w") as f:
        f.write(datetime.now().isoformat())
    
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


def write_session_file(filename: str, content: str, session_id: Optional[str] = None):
    """Write content to session file."""
    path = os.path.join(get_session_path(session_id), filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def read_session_file(filename: str, session_id: Optional[str] = None) -> Optional[str]:
    """Read content from session file."""
    path = os.path.join(get_session_path(session_id), filename)
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return None


def session_file_exists(filename: str, session_id: Optional[str] = None) -> bool:
    """Check if session file exists."""
    path = os.path.join(get_session_path(session_id), filename)
    return os.path.exists(path)


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


def list_sessions() -> list:
    """List all sessions."""
    session_dir = get_session_dir()
    sessions = []
    for name in os.listdir(session_dir):
        if name.startswith("s_") and os.path.isdir(os.path.join(session_dir, name)):
            sessions.append(name)
    return sorted(sessions, reverse=True)
