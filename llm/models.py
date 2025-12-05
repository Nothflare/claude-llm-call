"""Model configuration helpers."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

# All available model keys
ALL_KEYS = list(config.MODELS.keys())


def resolve(key: str) -> str:
    """Resolve model key to full model string."""
    return config.MODELS.get(key.lower(), key)


def name(key: str) -> str:
    """Get display name for model key."""
    return config.MODEL_NAMES.get(key.lower(), key)
