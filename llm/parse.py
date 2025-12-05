"""Input parsing utilities."""

from typing import Optional
from llm import models


def parse_stdin(content: str) -> dict:
    """
    Parse stdin content with section markers.

    Supported markers:
        ===QUERY=== - The question/prompt (required for most modes)
        ===DRAFT=== - Claude's draft answer (optional)
        ===PROBE=== - Target model for probe (optional)

    Returns:
        {"query": str|None, "draft": str|None, "probe_model": str|None}
    """
    result = {"query": None, "draft": None, "probe_model": None}

    # Parse QUERY
    if "===QUERY===" in content:
        remaining = content.split("===QUERY===", 1)[1]

        # Check for DRAFT section
        if "===DRAFT===" in remaining:
            query_part, draft_part = remaining.split("===DRAFT===", 1)
            result["query"] = query_part.strip()
            # Draft might have PROBE after it
            if "===PROBE===" in draft_part:
                draft_part, probe_part = draft_part.split("===PROBE===", 1)
                result["probe_model"] = _parse_probe_target(probe_part)
            result["draft"] = draft_part.strip()
        elif "===PROBE===" in remaining:
            query_part, probe_part = remaining.split("===PROBE===", 1)
            result["query"] = query_part.strip()
            result["probe_model"] = _parse_probe_target(probe_part)
        else:
            result["query"] = remaining.strip()

    # Parse standalone DRAFT (for crossref)
    elif "===DRAFT===" in content:
        result["draft"] = content.split("===DRAFT===", 1)[1].strip()

    # Parse PROBE target
    if "===PROBE===" in content and result["probe_model"] is None:
        probe_part = content.split("===PROBE===", 1)[1]
        result["probe_model"] = _parse_probe_target(probe_part)

    return result


def _parse_probe_target(probe_content: str) -> Optional[str]:
    """Extract model key from probe section (e.g., @gpt)."""
    first_line = probe_content.strip().split('\n')[0].lower()
    for key in models.ALL_KEYS:
        if f"@{key}" in first_line:
            return key
    return None
