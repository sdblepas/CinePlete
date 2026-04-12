"""
web.py — FastAPI application entry point.

Registers middleware, lifespan, and mounts all feature routers.
Business logic lives in app/routers/*.
"""
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import load_config
from app.auth import COOKIE_NAME, get_client_ip, is_local_address, verify_token
from app import scheduler

from app.routers import auth, config, scan, overrides, letterboxd, integrations, cache, theaters

_BASE_DIR  = Path(__file__).resolve().parent.parent
STATIC_DIR = os.getenv("STATIC_DIR", str(_BASE_DIR / "static"))

# ---------------------------------------------------------------------------
# Lifespan (scheduler start/stop)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg      = load_config()
    interval = int(cfg.get("AUTOMATION", {}).get("LIBRARY_POLL_INTERVAL", 30))
    scheduler.start(interval)
    yield
    scheduler.stop()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ---------------------------------------------------------------------------
# Auth middleware
# ---------------------------------------------------------------------------

_PUBLIC_PATHS    = {"/login", "/api/auth/login", "/api/auth/status", "/api/version"}
_PUBLIC_PREFIXES = ("/static/",)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Always public
        if path in _PUBLIC_PATHS or any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        cfg      = load_config()
        auth_cfg = cfg.get("AUTH", {})
        method   = auth_cfg.get("AUTH_METHOD", "None")

        if method == "None":
            return await call_next(request)

        if method == "DisabledForLocalAddresses":
            if is_local_address(get_client_ip(request)):
                return await call_next(request)

        # Validate session cookie
        token  = request.cookies.get(COOKIE_NAME, "")
        secret = auth_cfg.get("AUTH_SECRET_KEY", "")
        if token and secret and verify_token(token, secret):
            return await call_next(request)

        # Not authenticated
        if path.startswith("/api/"):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=302)


app.add_middleware(AuthMiddleware)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(config.router)
app.include_router(scan.router)
app.include_router(overrides.router)
app.include_router(letterboxd.router)
app.include_router(integrations.router)
app.include_router(cache.router)
app.include_router(theaters.router)
