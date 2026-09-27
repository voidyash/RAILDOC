import os
import ipaddress
import time
import logging
import json
from typing import Callable, Optional
from collections import defaultdict
from threading import Lock

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger("security.audit")


class RateLimiter:
    # Drop idle client keys periodically so spoofed/vanishing client ids
    # cannot grow the trackers without bound.
    MAX_TRACKED_CLIENTS = 10_000

    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.minute_windows: defaultdict[str, list] = defaultdict(list)
        self.hour_windows: defaultdict[str, list] = defaultdict(list)
        self.lock = Lock()
        self._calls = 0

    def _sweep(self, hour_ago: float) -> None:
        """Forget clients with no traffic in the last hour (their keys would
        otherwise live forever — unbounded memory under churned client ids)."""
        for store in (self.minute_windows, self.hour_windows):
            stale = [k for k, v in store.items() if not v or v[-1] <= hour_ago]
            for key in stale:
                del store[key]

    def is_allowed(self, client_id: str) -> tuple[bool, dict]:
        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600

        with self.lock:
            self._calls += 1
            if self._calls % 1000 == 0 or len(self.minute_windows) > self.MAX_TRACKED_CLIENTS:
                self._sweep(hour_ago)

            self.minute_windows[client_id] = [
                ts for ts in self.minute_windows[client_id] if ts > minute_ago
            ]
            self.hour_windows[client_id] = [
                ts for ts in self.hour_windows[client_id] if ts > hour_ago
            ]

            minute_count = len(self.minute_windows[client_id])
            hour_count = len(self.hour_windows[client_id])

            if minute_count >= self.requests_per_minute:
                return False, {
                    "limit": "minute",
                    "limit_value": self.requests_per_minute,
                    "current": minute_count,
                    "retry_after": 60,
                }

            if hour_count >= self.requests_per_hour:
                return False, {
                    "limit": "hour",
                    "limit_value": self.requests_per_hour,
                    "current": hour_count,
                    "retry_after": 3600,
                }

            self.minute_windows[client_id].append(now)
            self.hour_windows[client_id].append(now)

            return True, {
                "minute_remaining": self.requests_per_minute - minute_count - 1,
                "hour_remaining": self.requests_per_hour - hour_count - 1,
            }


rate_limiter = RateLimiter(
    requests_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
    requests_per_hour=int(os.getenv("RATE_LIMIT_PER_HOUR", "1000")),
)

# Tighter budget for credential endpoints: they used to be fully exempt,
# which meant unlimited password guessing plus unbounded CPU on hash verify.
login_rate_limiter = RateLimiter(
    requests_per_minute=int(os.getenv("RATE_LIMIT_LOGIN_PER_MINUTE", "10")),
    requests_per_hour=int(os.getenv("RATE_LIMIT_LOGIN_PER_HOUR", "100")),
)


def _rate_limit_key(request: Request) -> str:
    """Key the limiter on the direct peer, honouring X-Forwarded-For only
    when that peer is a private/loopback proxy (the docker/nginx setup).
    A public peer cannot spoof itself a fresh bucket by sending the header."""
    direct = request.client.host if request.client else "unknown"
    xff = request.headers.get("x-forwarded-for")
    if xff:
        try:
            addr = ipaddress.ip_address(direct)
        except ValueError:
            return direct  # non-IP peer (e.g. tests) — never trust the header
        if addr.is_private or addr.is_loopback:
            return xff.split(",")[0].strip()
    return direct


class RateLimitMiddleware(BaseHTTPMiddleware):

    def __init__(self, app: ASGIApp, exempt_paths: Optional[list[str]] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or ["/api/health", "/docs", "/openapi.json", "/redoc"]
        # Login/refresh are not exempt — they go through a tighter limiter.
        self.login_paths = {"/api/auth/login", "/api/auth/refresh"}
        self.login_limiter = login_rate_limiter

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        client_id = _rate_limit_key(request)
        limiter = self.login_limiter if request.url.path in self.login_paths else rate_limiter

        allowed, info = limiter.is_allowed(client_id)

        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_id}: {info}")
            # Return a real 429 instead of raising: this middleware runs
            # outside the app's exception handlers, so raising HTTPException
            # escaped to the server as an opaque 500.
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "limit": info["limit"],
                    "limit_value": info["limit_value"],
                    "retry_after": info["retry_after"],
                },
                headers={
                    "Retry-After": str(info["retry_after"]),
                    "X-RateLimit-Limit-Minute": str(limiter.requests_per_minute),
                    "X-RateLimit-Remaining-Minute": "0",
                    "X-RateLimit-Limit-Hour": str(limiter.requests_per_hour),
                    "X-RateLimit-Remaining-Hour": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit-Minute"] = str(limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining-Minute"] = str(info["minute_remaining"])
        response.headers["X-RateLimit-Limit-Hour"] = str(limiter.requests_per_hour)
        response.headers["X-RateLimit-Remaining-Hour"] = str(info["hour_remaining"])
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        self.exempt_paths = ["/docs", "/openapi.json", "/redoc"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = self.csp
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class AuditLogMiddleware(BaseHTTPMiddleware):

    SENSITIVE_PATHS = {
        "/api/plans/approve": "plan_approval",
        "/api/data/regenerate": "data_regeneration",
        "/api/priority/weights": "weight_modification",
        "/api/optimize": "optimization_run",
        "/api/simulate": "simulation_run",
        "/api/auth/login": "login",
        "/api/auth/refresh": "token_refresh",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        if request.headers.get("x-forwarded-for"):
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()

        user = getattr(request.state, "user", None)
        username = user.username if user else "anonymous"

        response = await call_next(request)

        duration_ms = (time.time() - start_time) * 1000
        path = request.url.path

        if path in self.SENSITIVE_PATHS or response.status_code >= 400:
            audit_entry = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "event_type": self.SENSITIVE_PATHS.get(path, "api_request"),
                "method": request.method,
                "path": path,
                "client_ip": client_ip,
                "username": username,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 2),
                "user_agent": request.headers.get("user-agent", ""),
            }
            logger.info(json.dumps(audit_entry))

        return response