"""Utilities for loading AI prompt templates."""

from __future__ import annotations

import os
from importlib import resources


def load_prompt_template() -> str:
    """Return the prompt template text.

    If the ``RAINDROP_PROMPT_FILE`` environment variable is set, the template is
    loaded from that file path. Otherwise the bundled ``default_prompt.txt`` is
    used.
    """
    env_path = os.getenv("RAINDROP_PROMPT_FILE")
    if env_path:
        try:
            with open(env_path, encoding="utf-8") as f:
                return f.read()
        except OSError:
            pass

    with (
        resources.files(__package__)
        .joinpath("default_prompt.txt")
        .open("r", encoding="utf-8") as f
    ):
        return f.read()
