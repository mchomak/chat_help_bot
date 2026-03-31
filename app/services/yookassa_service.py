"""Async wrapper around the synchronous YooKassa SDK.

All network calls are run in a thread executor so they don't block the
asyncio event loop.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class YKPaymentResult:
    yookassa_id: str
    confirmation_url: str
    status: str


def _get_sdk():
    """Return (Configuration, Payment) from the yookassa package."""
    import yookassa  # noqa: PLC0415
    return yookassa.Configuration, yookassa.Payment


def _configure(shop_id: str, api_key: str) -> None:
    Configuration, _ = _get_sdk()
    Configuration.account_id = shop_id
    Configuration.secret_key = api_key


async def create_payment(
    *,
    shop_id: str,
    api_key: str,
    amount: float,
    description: str,
    return_url: str,
    idempotency_key: str,
    metadata: dict,
    customer_email: str,
    vat_code: int = 1,
) -> YKPaymentResult:
    """Create a YooKassa payment and return id + redirect URL.

    Raises ``RuntimeError`` on API failure (caller should catch and mark api_error).
    """
    # Truncate description to 128 chars as required by YooKassa receipt items
    item_description = description[:128]
    amount_value = f"{amount:.2f}"

    payload = {
        "amount": {"value": amount_value, "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": return_url},
        "capture": True,
        "description": description,
        "metadata": metadata,
        "receipt": {
            "customer": {"email": customer_email},
            "items": [
                {
                    "description": item_description,
                    "amount": {"value": amount_value, "currency": "RUB"},
                    "vat_code": vat_code,
                    "quantity": "1.00",
                    "payment_mode": "full_payment",
                    "payment_subject": "service",
                }
            ],
        },
    }

    logger.info(
        "Creating YooKassa payment: amount=%s description=%r idempotency_key=%s email=%s",
        amount_value,
        description,
        idempotency_key,
        customer_email[:3] + "***" if len(customer_email) > 3 else "***",
    )

    def _sync() -> YKPaymentResult:
        _configure(shop_id, api_key)
        _, YKPayment = _get_sdk()
        try:
            response = YKPayment.create(payload, idempotency_key)
        except Exception as exc:
            logger.error(
                "YooKassa Payment.create failed: %s | idempotency_key=%s",
                exc,
                idempotency_key,
            )
            raise
        logger.info(
            "YooKassa payment created: yookassa_id=%s status=%s",
            response.id,
            response.status,
        )
        return YKPaymentResult(
            yookassa_id=response.id,
            confirmation_url=response.confirmation.confirmation_url,
            status=response.status,
        )

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        raise RuntimeError(f"YooKassa API error: {exc}") from exc


async def fetch_payment_status(
    *,
    shop_id: str,
    api_key: str,
    yookassa_payment_id: str,
) -> str:
    """Return the current YooKassa status string for a payment.

    Possible values: pending / waiting_for_capture / succeeded / canceled.
    Raises ``RuntimeError`` on API failure.
    """
    def _sync() -> str:
        _configure(shop_id, api_key)
        _, YKPayment = _get_sdk()
        response = YKPayment.find_one(yookassa_payment_id)
        logger.info(
            "YooKassa.find_one(%s) → status=%s", yookassa_payment_id, response.status,
        )
        return response.status

    try:
        return await asyncio.to_thread(_sync)
    except Exception as exc:
        logger.error(
            "fetch_payment_status failed for yk_id=%s: %s", yookassa_payment_id, exc,
        )
        raise RuntimeError(f"YooKassa API error: {exc}") from exc
