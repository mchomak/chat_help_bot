"""Parse and validate AI API responses."""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

# Characters / patterns we want to strip from AI output for safety
_UNSAFE_PATTERNS = [
    re.compile(r"<script[^>]*>.*?</script>", re.I | re.S),
    re.compile(r"<[^>]+>"),  # HTML tags
]


def _sanitize(text: str) -> str:
    """Remove potentially unsafe markup from a single text value."""
    for pat in _UNSAFE_PATTERNS:
        text = pat.sub("", text)
    return text.strip()


def _extract_json(raw: str) -> dict | None:
    """Attempt to extract a JSON object from raw response text."""
    # Try direct parse
    raw = raw.strip()
    if raw.startswith("```"):
        # Remove markdown code fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object within the text
    match = re.search(r"\{[\s\S]*\}", raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def parse_reply_response(raw: str) -> list[str]:
    """Parse reply-message scenario response into list of reply options."""
    data = _extract_json(raw)
    if data and "replies" in data and isinstance(data["replies"], list):
        return [_sanitize(r) for r in data["replies"] if isinstance(r, str) and r.strip()]
    logger.warning("Failed to parse reply response, attempting line split")
    return _fallback_line_split(raw)


def parse_first_message_response(raw: str) -> list[str]:
    """Parse first-message scenario response into list of message options."""
    data = _extract_json(raw)
    if data and "messages" in data and isinstance(data["messages"], list):
        return [_sanitize(m) for m in data["messages"] if isinstance(m, str) and m.strip()]
    logger.warning("Failed to parse first_message response, attempting line split")
    return _fallback_line_split(raw)


def parse_profile_review_response(raw: str) -> dict:
    """Parse profile-review response into structured dict."""
    data = _extract_json(raw)
    if data:
        result = {}
        for key in ("strengths", "weaknesses", "improvements", "recommendations"):
            items = data.get(key, [])
            if isinstance(items, list):
                result[key] = [_sanitize(i) for i in items if isinstance(i, str)]
            else:
                result[key] = []
        return result
    logger.warning("Failed to parse profile_review response")
    return {
        "strengths": [],
        "weaknesses": [],
        "improvements": [],
        "recommendations": [_sanitize(raw)],
    }


def _fallback_line_split(raw: str) -> list[str]:
    """Fallback: split raw text by numbered lines or newlines."""
    lines = re.split(r"\n+", raw.strip())
    results = []
    for line in lines:
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", line).strip()
        cleaned = _sanitize(cleaned)
        if cleaned and len(cleaned) > 2:
            results.append(cleaned)
    return results[:5] if results else [_sanitize(raw.strip())]
