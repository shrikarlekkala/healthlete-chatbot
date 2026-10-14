"""
security.py - High-performance security middleware & dependencies
===================================================================
1. X-API-Key verification (timing-attack resistant via hmac)
2. In-memory sliding window IP rate limiter (5 req/min, zero external dependencies)
3. Payload length validation (max 500 chars)
"""

import hmac
import time
from collections import deque
from typing import Dict, Optional

from fastapi import Header, HTTPException, Request, Security, status

from app.core.config import CHAT_API_KEY, RATE_LIMIT_PER_MINUTE, MAX_QUERY_LENGTH


class IPRateLimiter:
    """Ultra-low-latency in-memory sliding window rate limiter.
    Zero external dependencies, sub-microsecond lookup.
    """
    def __init__(self, max_requests: int = 5, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._ip_history: Dict[str, deque] = {}
        self._last_cleanup = time.time()

    def _cleanup_old_records(self, now: float):
        """Periodically cleans up IPs that have been idle past the window."""
        if now - self._last_cleanup > 120.0:
            stale_ips = [
                ip for ip, timestamps in self._ip_history.items()
                if not timestamps or now - timestamps[-1] > self.window_seconds
            ]
            for ip in stale_ips:
                del self._ip_history[ip]
            self._last_cleanup = now

    def check_rate_limit(self, client_ip: str) -> None:
        now = time.time()
        self._cleanup_old_records(now)

        if client_ip not in self._ip_history:
            self._ip_history[client_ip] = deque()

        timestamps = self._ip_history[client_ip]
        cutoff = now - self.window_seconds

        # Remove requests older than the sliding window
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

        if len(timestamps) >= self.max_requests:
            retry_after = max(1, int(self.window_seconds - (now - timestamps[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: maximum {self.max_requests} requests per minute allowed. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )

        # Record this request timestamp
        timestamps.append(now)


# Global rate limiter instance
_rate_limiter = IPRateLimiter(max_requests=RATE_LIMIT_PER_MINUTE, window_seconds=60.0)


def get_client_ip(request: Request) -> str:
    """Extracts client IP address supporting proxy headers (X-Forwarded-For)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """Validates the private X-API-Key header against CHAT_API_KEY."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required security header: 'X-API-Key'",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if not hmac.compare_digest(x_api_key.strip(), CHAT_API_KEY.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 'X-API-Key' provided.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


def enforce_security(
    request: Request,
    x_api_key: str = Security(verify_api_key),
) -> None:
    """FastAPI dependency combining X-API-Key authentication and IP rate limiting."""
    client_ip = get_client_ip(request)
    _rate_limiter.check_rate_limit(client_ip)


def validate_payload_message(message: str) -> str:
    """Validates query message length to prevent prompt injection & token bloat."""
    cleaned = (message or "").strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'message' cannot be empty."
        )
    if len(cleaned) > MAX_QUERY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message exceeds maximum allowed length of {MAX_QUERY_LENGTH} characters (received {len(cleaned)})."
        )
    return cleaned
