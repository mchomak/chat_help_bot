"""Tests for AI response parser."""

from __future__ import annotations

import pytest

from app.ai.response_parser import (
    parse_first_message_response,
    parse_profile_review_response,
    parse_reply_response,
)


def test_parse_reply_valid_json() -> None:
    raw = '{"replies": ["Привет!", "Как дела?", "Ну привет"]}'
    result = parse_reply_response(raw)
    assert len(result) == 3
    assert result[0] == "Привет!"


def test_parse_reply_with_code_fences() -> None:
    raw = '```json\n{"replies": ["One", "Two"]}\n```'
    result = parse_reply_response(raw)
    assert len(result) == 2


def test_parse_reply_fallback() -> None:
    raw = "1. Привет\n2. Как дела\n3. Окей"
    result = parse_reply_response(raw)
    assert len(result) == 3


def test_parse_first_message() -> None:
    raw = '{"messages": ["Привет!", "Интересный профиль"]}'
    result = parse_first_message_response(raw)
    assert len(result) == 2


def test_parse_profile_review() -> None:
    raw = '{"strengths": ["Good"], "weaknesses": ["Bad"], "improvements": ["Fix"], "recommendations": ["Do"]}'
    result = parse_profile_review_response(raw)
    assert len(result["strengths"]) == 1
    assert result["recommendations"][0] == "Do"


def test_parse_profile_review_fallback() -> None:
    raw = "Some freeform text with no JSON"
    result = parse_profile_review_response(raw)
    assert "recommendations" in result
    assert len(result["recommendations"]) > 0


def test_sanitize_strips_html() -> None:
    raw = '{"replies": ["<b>Bold</b>", "<script>alert(1)</script>Hello"]}'
    result = parse_reply_response(raw)
    assert "<b>" not in result[0]
    assert "<script>" not in result[1]
