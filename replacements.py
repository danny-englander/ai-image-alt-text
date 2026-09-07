"""Load and apply word/phrase replacements from replacements.yaml."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REPLACEMENTS_PATH = SCRIPT_DIR / "replacements.yaml"


@lru_cache(maxsize=4)
def load_replacements(path: Optional[str] = None) -> dict[str, str]:
    """Load replacements.yaml as {find: replace}. Keys/values are stripped strings."""
    config_path = Path(path) if path else DEFAULT_REPLACEMENTS_PATH
    if not config_path.exists():
        return {}
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}
    if not isinstance(data, dict):
        return {}
    mapping = {}
    for key, value in data.items():
        find = str(key).strip()
        replace = str(value).strip()
        if find and replace:
            mapping[find] = replace
    return mapping


def _preserve_case(source: str, replacement: str) -> str:
    """Match the replacement's case to the matched source text."""
    if not source or not replacement:
        return replacement
    if source.isupper():
        return replacement.upper()
    if source.islower():
        return replacement.lower()
    # Title-style or mixed: capitalize first letter, keep the rest of the canonical form.
    return replacement[0].upper() + replacement[1:]


def apply_replacements(
    text: str, mapping: Optional[dict[str, str]] = None
) -> str:
    """Replace dictionary phrases in text (case-insensitive, whole-phrase)."""
    if not text:
        return text
    if mapping is None:
        mapping = load_replacements()
    if not mapping:
        return text

    # Longer phrases first so "mid-century modern" wins over "mid-century".
    items = sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True)
    result = text
    for find, replace in items:
        pattern = re.compile(r"\b" + re.escape(find) + r"\b", re.IGNORECASE)

        def _sub(match: re.Match, *, _replace: str = replace) -> str:
            return _preserve_case(match.group(0), _replace)

        result = pattern.sub(_sub, result)
    return result


def replacement_prompt_notes(mapping: Optional[dict[str, str]] = None) -> str:
    """Short prompt addendum so the model uses preferred spellings up front."""
    if mapping is None:
        mapping = load_replacements()
    if not mapping:
        return ""
    lines = [
        "Use these preferred spellings (do not use the hyphenated or alternate forms):"
    ]
    for find, replace in sorted(mapping.items(), key=lambda kv: kv[0].lower()):
        lines.append(f'- "{replace}" not "{find}"')
    return "\n".join(lines) + "\n"
