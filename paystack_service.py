"""Small Paystack test-mode client using only Python's standard library.

The secret key belongs in a local .env file. This web approach is suitable
for an academic test demonstration, not for a production deployment.
"""

from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path


API_BASE = "https://api.paystack.co"


def load_environment() -> None:
    """Load simple KEY=VALUE pairs from .env without an external package."""
    env_path = Path(__file__).with_name(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def get_secret_key() -> str:
    load_environment()
    key = os.getenv("PAYSTACK_SECRET_KEY", "").strip()
    if not key.startswith("sk_test_"):
        raise ValueError(
            "Add a Paystack test secret key (sk_test_...) to the local .env file."
        )
    return key


def create_reference() -> str:
    return f"LIB-{secrets.token_hex(8).upper()}"


def _request(url: str, key: str, method: str = "GET", payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "DigitalLibraryWebSystem/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        message = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Paystack returned HTTP {error.code}: {message}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not connect to Paystack: {error.reason}") from error


def initialise_transaction(email: str, amount_naira: int, reference: str) -> dict:
    """Create a test transaction and return its checkout URL and reference."""
    key = get_secret_key()
    payload = {
        "email": email,
        "amount": amount_naira * 100,
        "currency": "NGN",
        "reference": reference,
        "metadata": {"purpose": "Digital library overdue fine"},
    }
    response = _request(
        f"{API_BASE}/transaction/initialize", key, method="POST", payload=payload
    )
    if not response.get("status"):
        raise RuntimeError(response.get("message", "Transaction initialisation failed."))
    return response["data"]


def verify_transaction(reference: str, expected_amount_naira: int) -> dict:
    """Verify status and amount before the application records a payment."""
    key = get_secret_key()
    response = _request(f"{API_BASE}/transaction/verify/{reference}", key)
    data = response.get("data", {})
    successful = data.get("status") == "success"
    correct_amount = data.get("amount") == expected_amount_naira * 100
    return {
        "successful": successful and correct_amount,
        "gateway_status": data.get("status", "unknown"),
        "correct_amount": correct_amount,
        "channel": data.get("channel"),
        "paid_at": data.get("paid_at"),
    }
