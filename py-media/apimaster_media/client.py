"""Shared helpers: credentials, retries, polling, download.

Works against any OpenAI-compatible gateway — only the values in .env change.
"""

from __future__ import annotations

import os
import random
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, TypeVar

import requests

BASE_URL = os.environ.get("APIMASTER_BASE_URL", "https://apimaster.ai/v1").rstrip("/")

# Image generation is slow. These are the documented client-side read timeouts; a
# shorter one aborts healthy jobs you have already been charged for.
SYNC_TIMEOUT = {"1k": 200, "2k": 320, "4k": 620}

T = TypeVar("T")


class ApiError(RuntimeError):
    def __init__(self, status: int, body: Any):
        detail = ""
        if isinstance(body, dict):
            detail = str(body.get("error", {}).get("message", ""))
        elif body:
            detail = str(body)[:200]
        super().__init__(f"HTTP {status}" + (f": {detail}" if detail else ""))
        self.status = status
        self.body = body

    @property
    def retryable(self) -> bool:
        """429 and 5xx are transient. 400/401/402 never become valid by retrying."""
        return self.status == 429 or self.status >= 500


def api_key() -> str:
    key = os.environ.get("APIMASTER_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "APIMASTER_API_KEY is not set.\n"
            "  cp .env.example .env  and fill it in, or export the variable.\n"
            "  Get a key: https://apimaster.ai/docs/getting-started/api-key"
        )
    return key


def headers() -> Dict[str, str]:
    return {"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"}


def api(
    path: str,
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
    retries: int = 2,
) -> Any:
    url = path if path.startswith("http") else f"{BASE_URL}{path}"
    last: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            response = requests.request(method, url, headers=headers(), json=body, timeout=timeout)
            try:
                parsed = response.json() if response.content else None
            except ValueError:
                parsed = response.text
            if not response.ok:
                raise ApiError(response.status_code, parsed)
            return parsed
        except (ApiError, requests.Timeout, requests.ConnectionError) as exc:
            last = exc
            retryable = exc.retryable if isinstance(exc, ApiError) else True
            if not retryable or attempt == retries:
                raise
            backoff = 0.5 * 2**attempt + random.random() * 0.25
            print(f"  retrying in {backoff:.1f}s ({exc})")
            time.sleep(backoff)
    raise last  # pragma: no cover


def poll(
    read: Callable[[], T],
    is_done: Callable[[T], bool],
    is_failed: Callable[[T], bool],
    initial_delay: float = 12.0,
    interval: float = 4.0,
    timeout: float = 900.0,
    label: str = "job",
) -> T:
    """Poll until a terminal state. The first read is delayed on purpose."""
    deadline = time.time() + timeout
    time.sleep(initial_delay)
    ticks = 0
    while time.time() < deadline:
        value = read()
        if is_done(value):
            return value
        if is_failed(value):
            raise RuntimeError(f"{label} failed: {str(value)[:300]}")
        if ticks % 5 == 0:
            print(f"  waiting for {label}… {int(timeout - (deadline - time.time()))}s")
        ticks += 1
        time.sleep(interval)
    raise TimeoutError(f"{label} did not finish within {int(timeout)}s")


def download(url: str, path: str | Path) -> int:
    request_headers = {"Authorization": f"Bearer {api_key()}"} if url.startswith(BASE_URL) else {}
    response = requests.get(url, headers=request_headers, timeout=600, allow_redirects=True)
    if not response.ok:
        raise ApiError(response.status_code, response.text)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return len(response.content)
