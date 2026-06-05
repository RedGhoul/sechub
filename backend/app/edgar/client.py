"""A single, process-wide rate-limited HTTP client for SEC EDGAR.

The SEC enforces a hard limit of 10 requests/second per IP and requires a
descriptive ``User-Agent`` carrying real contact info. Every EDGAR request in
SecHub goes through :data:`edgar_client` so that limit is honored centrally —
nothing else in the app should construct its own HTTP client for SEC hosts.
"""

from __future__ import annotations

import threading
import time

import httpx

from app.config import settings


class _RateLimiter:
    """Simple thread-safe token-bucket-ish limiter: at most ``rps`` per second.

    We serialize on a lock and space requests at least ``1/rps`` apart. That is
    conservative (it caps instantaneous concurrency) but guarantees we never
    trip the SEC's 10 rps ceiling regardless of how many worker threads call in.
    """

    def __init__(self, rps: float) -> None:
        self._min_interval = 1.0 / rps if rps > 0 else 0.0
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next_allowed = now + self._min_interval


class EdgarClient:
    """Thin wrapper over ``httpx.Client`` that throttles and retries."""

    def __init__(self, user_agent: str | None = None, max_rps: float | None = None) -> None:
        self._limiter = _RateLimiter(max_rps or settings.sechub_max_rps)
        self._client = httpx.Client(
            headers={
                "User-Agent": user_agent or settings.sechub_user_agent,
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=30.0,
            follow_redirects=True,
        )

    def get(self, url: str, *, retries: int = 4) -> httpx.Response:
        """GET ``url`` honoring the rate limit, retrying transient failures.

        Retries on 429/5xx and network errors with exponential backoff. Raises
        for status on the final attempt.
        """
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            self._limiter.acquire()
            try:
                resp = self._client.get(url)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"retryable {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                return resp
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                if attempt == retries:
                    break
                time.sleep(2**attempt)  # 1, 2, 4, 8s
        assert last_exc is not None
        raise last_exc

    def get_text(self, url: str) -> str:
        return self.get(url).text

    def get_bytes(self, url: str) -> bytes:
        return self.get(url).content

    def get_json(self, url: str) -> dict:
        return self.get(url).json()

    def close(self) -> None:
        self._client.close()


# Process-wide singleton. Import this, don't instantiate your own.
edgar_client = EdgarClient()
