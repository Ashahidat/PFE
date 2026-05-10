from __future__ import annotations

from typing import Iterable

import requests
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from grafana.settings import get_grafana_settings
from jwt_dependencies import get_current_user

router = APIRouter(prefix="/grafana", tags=["grafana"])


_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


def _iter_content(resp: requests.Response) -> Iterable[bytes]:
    for chunk in resp.iter_content(chunk_size=65536):
        if chunk:
            yield chunk


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def grafana_reverse_proxy(path: str, request: Request, user=Depends(get_current_user)):
    """
    Minimal reverse-proxy to access Grafana through this FastAPI backend.

    Browser flow:
    - user logs in via `/login` (JWT stored in httpOnly cookie `access_token`)
    - user navigates to `/grafana/...`
    - backend validates JWT then forwards the request to Grafana with `X-WEBAUTH-*` headers
    """

    settings = get_grafana_settings()
    upstream_base = settings.url.rstrip("/")

    upstream_url = f"{upstream_base}/{path.lstrip('/')}"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    employee_id = user.get("employee_id") or user.get("sub") or ""
    username = user.get("username") or employee_id
    role = user.get("role") or "VIEWER"

    upstream_headers: dict[str, str] = {}
    for key, value in request.headers.items():
        lower = key.lower()
        if lower in _HOP_BY_HOP_HEADERS:
            continue
        if lower in {"host", "content-length", "authorization", "cookie"}:
            continue
        upstream_headers[key] = value

    upstream_headers["X-WEBAUTH-USER"] = employee_id
    upstream_headers["X-WEBAUTH-NAME"] = username
    upstream_headers["X-WEBAUTH-ROLE"] = role
    upstream_headers["X-Forwarded-Prefix"] = "/grafana"
    upstream_headers.setdefault("X-Forwarded-Proto", request.url.scheme)
    upstream_headers.setdefault("X-Forwarded-Host", request.headers.get("host", "localhost"))

    data = await request.body() if request.method not in {"GET", "HEAD"} else None

    upstream_resp: requests.Response = await run_in_threadpool(
        requests.request,
        method=request.method,
        url=upstream_url,
        headers=upstream_headers,
        data=data,
        allow_redirects=False,
        stream=True,
        timeout=30,
    )

    response_headers: dict[str, str] = {}
    for key, value in upstream_resp.headers.items():
        lower = key.lower()
        if lower in _HOP_BY_HOP_HEADERS:
            continue
        if lower in {"content-encoding", "content-length"}:
            # Let Starlette compute these
            continue
        if lower == "location":
            # Rewrite absolute paths so the browser stays under `/grafana/...`
            if value.startswith("/") and not value.startswith("/grafana/"):
                value = f"/grafana{value}"
            response_headers[key] = value
            continue
        response_headers[key] = value

    media_type = upstream_resp.headers.get("content-type")
    return StreamingResponse(
        _iter_content(upstream_resp),
        status_code=upstream_resp.status_code,
        headers=response_headers,
        media_type=media_type,
        background=None,
    )
