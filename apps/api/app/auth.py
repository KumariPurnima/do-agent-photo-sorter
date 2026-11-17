from __future__ import annotations

import secrets
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings

PUBLIC_PATHS = {"/api/health"}


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        if not settings.app_password:
            return await call_next(request)

        path = request.url.path
        if path in PUBLIC_PATHS:
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Basic "):
            import base64

            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                username, _, password = decoded.partition(":")
            except Exception:  # noqa: BLE001
                username, password = "", ""
            user_ok = secrets.compare_digest(username, settings.app_username)
            pass_ok = secrets.compare_digest(password, settings.app_password)
            if user_ok and pass_ok:
                return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required"},
            headers={"WWW-Authenticate": 'Basic realm="Agent Photo Sorter"'},
        )
