from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Vocabulary:
    replacements: dict[str, str]
    prompt: str = ""


def load_vocabulary(path: Path) -> Vocabulary:
    """Load a flat phrase map or {"replacements", "prompt"}."""
    if not path.exists():
        return Vocabulary(replacements={})
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not read vocabulary file {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Vocabulary file {path} must be a JSON object")

    if "replacements" in raw:
        replacements = _string_map(raw.get("replacements"), path, "replacements")
        prompt = raw.get("prompt", "")
        if not isinstance(prompt, str):
            raise ValueError(f"{path}: \"prompt\" must be a string")
        return Vocabulary(replacements=replacements, prompt=prompt)

    return Vocabulary(replacements=_string_map(raw, path, "vocabulary"))


def _string_map(value: object, path: Path, label: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{path}: {label} must be an object of phrases to spellings")
    mapping: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise ValueError(f"{path}: every {label} entry must be a string")
        if key.strip():
            mapping[key] = item
    return mapping


def apply_vocabulary(text: str, replacements: dict[str, str]) -> str:
    """One left-to-right pass. Longer phrases win. Matching ignores case."""
    pairs = [(key.strip(), value) for key, value in replacements.items() if key.strip()]
    if not text or not pairs:
        return text
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    lookup: dict[str, str] = {}
    ordered: list[str] = []
    for key, value in pairs:
        folded = key.casefold()
        if folded in lookup:
            continue
        lookup[folded] = value
        ordered.append(key)
    pattern = "|".join(rf"\b{re.escape(key)}\b" for key in ordered)

    def replace(match: re.Match[str]) -> str:
        return lookup[match.group(0).casefold()]

    return re.sub(pattern, replace, text, flags=re.IGNORECASE)


def build_prompt(vocab: Vocabulary, extra: str, max_chars: int) -> str:
    """Initial prompt for the engine. Deterministic replacements still run afterwards."""
    parts: list[str] = []
    if extra.strip():
        parts.append(extra.strip())
    if vocab.prompt.strip():
        parts.append(vocab.prompt.strip())
    seen: set[str] = set()
    preferred: list[str] = []
    for value in vocab.replacements.values():
        cleaned = value.strip()
        folded = cleaned.casefold()
        if cleaned and folded not in seen:
            seen.add(folded)
            preferred.append(cleaned)
    if preferred:
        parts.append(", ".join(preferred))
    text = ". ".join(parts).strip()
    if max_chars <= 0 or len(text) <= max_chars:
        return text if max_chars > 0 else ""
    trimmed = text[:max_chars].rsplit(" ", 1)[0].strip()
    return trimmed or text[:max_chars].strip()
