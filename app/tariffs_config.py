"""Static tariff and pack definitions — single source of truth for pricing.

All prices, periods, and screenshot counts live here in Python code.
No environment variables — changes require a code edit and redeploy,
which is intentional: pricing changes should go through version control.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TariffPlan:
    key: str
    label: str
    price: float          # RUB
    days: int
    base_screenshots: int


@dataclass(frozen=True)
class ScreenshotPack:
    key: str
    label: str
    price: float          # RUB
    screenshots: int


# ── Subscription plans ──────────────────────────────────────────────────────

TARIFFS: dict[str, TariffPlan] = {
    "week":    TariffPlan("week",    "1 неделя",   200.0,   7, 100),
    "month":   TariffPlan("month",   "1 месяц",    500.0,  30, 300),
    "quarter": TariffPlan("quarter", "3 месяца",  1000.0,  90, 900),
}

# ── Screenshot add-on packs ─────────────────────────────────────────────────

PACKS: dict[str, ScreenshotPack] = {
    "s": ScreenshotPack("s", "300 скриншотов",   500.0,   300),
    "m": ScreenshotPack("m", "1 000 скриншотов", 1000.0, 1000),
    "l": ScreenshotPack("l", "5 000 скриншотов", 4000.0, 5000),
}


def get_tariff(key: str) -> TariffPlan:
    try:
        return TARIFFS[key]
    except KeyError:
        raise KeyError(f"Unknown tariff key: {key!r}. Valid: {list(TARIFFS)}")


def get_pack(key: str) -> ScreenshotPack:
    try:
        return PACKS[key]
    except KeyError:
        raise KeyError(f"Unknown pack key: {key!r}. Valid: {list(PACKS)}")
