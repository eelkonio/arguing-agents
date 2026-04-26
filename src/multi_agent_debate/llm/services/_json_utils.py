"""Utilities for extracting JSON from LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str) -> Any:  # noqa: ANN401
    """Best-effort JSON extraction from an LLM response.

    Strategy:
    1. Try to parse the full response as JSON.
    2. If that fails, look for JSON within ```json ... ``` code blocks.
    3. If that fails, look for JSON within [ ] or { } brackets.

    Returns the parsed Python object, or raises ``ValueError`` if no valid
    JSON can be found.
    """
    # 1. Try full text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Try ```json ... ``` code blocks
    code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except (json.JSONDecodeError, TypeError):
            pass

    # 3. Try outermost [ ] or { } brackets
    for open_char, close_char in [("[", "]"), ("{", "}")]:
        start = text.find(open_char)
        if start == -1:
            continue
        # Find the matching closing bracket
        depth = 0
        for i in range(start, len(text)):
            if text[i] == open_char:
                depth += 1
            elif text[i] == close_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except (json.JSONDecodeError, TypeError):
                        break

    msg = "Could not extract valid JSON from LLM response"
    raise ValueError(msg)
