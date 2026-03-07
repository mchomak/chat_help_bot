"""Tests for proxy manager rotation and health tracking."""

from __future__ import annotations

import asyncio

import pytest

from app.proxy.manager import ProxyManager, ProxyStats


@pytest.mark.asyncio
async def test_proxy_rotation() -> None:
    pm = ProxyManager()
    pm._proxies = [
        ProxyStats(url="http://proxy1:8080"),
        ProxyStats(url="http://proxy2:8080"),
        ProxyStats(url="http://proxy3:8080"),
    ]
    urls = []
    for _ in range(3):
        url = await pm.get_next_proxy()
        urls.append(url)
    assert len(set(urls)) >= 2  # at least two different proxies used


@pytest.mark.asyncio
async def test_proxy_failure_tracking() -> None:
    pm = ProxyManager()
    pm._proxies = [
        ProxyStats(url="http://proxy1:8080"),
        ProxyStats(url="http://proxy2:8080"),
    ]
    # Record failures for proxy1
    await pm.report_failure("http://proxy1:8080")
    await pm.report_failure("http://proxy1:8080")
    await pm.report_failure("http://proxy1:8080")

    # proxy1 should be on cooldown
    assert pm._proxies[0].cooldown_until > 0


@pytest.mark.asyncio
async def test_proxy_success_resets_counter() -> None:
    pm = ProxyManager()
    pm._proxies = [ProxyStats(url="http://proxy1:8080")]
    await pm.report_failure("http://proxy1:8080")
    await pm.report_failure("http://proxy1:8080")
    await pm.report_success("http://proxy1:8080")
    assert pm._proxies[0].fail_count == 0


@pytest.mark.asyncio
async def test_no_proxies_returns_none() -> None:
    pm = ProxyManager()
    pm._proxies = []
    result = await pm.get_next_proxy()
    assert result is None


@pytest.mark.asyncio
async def test_all_proxies_cooldown_reset() -> None:
    pm = ProxyManager()
    pm._proxies = [
        ProxyStats(url="http://proxy1:8080"),
        ProxyStats(url="http://proxy2:8080"),
    ]
    # Put all on cooldown
    for p in pm._proxies:
        p.cooldown_until = float("inf")

    # Should still return a proxy after reset
    url = await pm.get_next_proxy()
    assert url is not None
