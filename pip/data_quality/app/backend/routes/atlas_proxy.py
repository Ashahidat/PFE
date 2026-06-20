from __future__ import annotations

import logging
import os
import re
from typing import Iterable

import requests
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import MutableHeaders

from jwt_dependencies import get_current_user

router = APIRouter(prefix="/atlas", tags=["atlas"])
logger = logging.getLogger("atlas-proxy")

PUBLIC_PREFIX = "/api/atlas"
UPSTREAM_PREFIX = "/"
ATLAS_PUBLIC_URL = os.getenv("ATLAS_PUBLIC_URL", "http://127.0.0.1:21001").rstrip("/")

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


def _apply_upstream_headers(
    response: Response | StreamingResponse, *, upstream_resp: requests.Response
) -> None:
    headers = MutableHeaders(response.headers)
    for key, value in upstream_resp.headers.items():
        lower = key.lower()
        if lower in _HOP_BY_HOP_HEADERS:
            continue
        if lower in {"content-encoding", "content-length", "set-cookie"}:
            continue
        headers[key] = value


def _rewrite_html_for_subpath(html: str, subpath: str) -> str:
    prefix = subpath.rstrip("/")
    if not prefix:
        return html

    html = re.sub(r'<base\s+href="[^"]*"\s*/?>', f'<base href="{prefix}/">', html, count=1)
    html = re.sub(r'(\s(?:src|href|action)=)"/(?!api/atlas/)(?!/)', rf'\1"{prefix}/', html)
    return html


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def atlas_reverse_proxy(path: str, request: Request, user=Depends(get_current_user)):
    """
    Reverse-proxy Atlas UI through the backend so the frontend can use a same-origin link.

    The upstream public Atlas proxy still enforces its own read-only rules; this route only
    ensures the browser can reach it through the app origin and keeps the JWT gate in front.
    """

    upstream_path = f"{UPSTREAM_PREFIX}{path.lstrip('/')}"
    upstream_url = f"{ATLAS_PUBLIC_URL}{upstream_path}"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    upstream_headers: dict[str, str] = {}
    incoming_cookie = None
    for key, value in request.headers.items():
        lower = key.lower()
        if lower in _HOP_BY_HOP_HEADERS:
            continue
        if lower in {"host", "content-length", "authorization", "cookie"}:
            if lower == "cookie":
                incoming_cookie = value
            continue
        upstream_headers[key] = value

    if incoming_cookie:
        upstream_headers["Cookie"] = incoming_cookie

    upstream_headers["X-Forwarded-Prefix"] = PUBLIC_PREFIX
    upstream_headers.setdefault("X-Forwarded-Proto", request.url.scheme)
    upstream_headers.setdefault("X-Forwarded-Host", request.headers.get("host", "localhost"))

    data = await request.body() if request.method not in {"GET", "HEAD"} else None

    try:
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
    except requests.RequestException as exc:
        logger.exception("⚠️ [Atlas] upstream request failed url=%s", upstream_url)
        return Response(
            status_code=502,
            content=f"Atlas upstream unreachable: {exc}",
            media_type="text/plain; charset=utf-8",
        )

    location = upstream_resp.headers.get("location")
    if location and location.startswith("/"):
        if location.startswith(UPSTREAM_PREFIX):
            location = f"{PUBLIC_PREFIX}{location}"
        elif not location.startswith(f"{PUBLIC_PREFIX}/"):
            location = f"{PUBLIC_PREFIX}{location}"
    elif location and location.startswith(ATLAS_PUBLIC_URL):
        location = f"{PUBLIC_PREFIX}{location[len(ATLAS_PUBLIC_URL):]}"

    media_type = upstream_resp.headers.get("content-type")
    if media_type and "text/html" in media_type.lower():
        text = await run_in_threadpool(lambda: upstream_resp.text)
        rewritten = _rewrite_html_for_subpath(text, PUBLIC_PREFIX)
        resp = Response(content=rewritten, status_code=upstream_resp.status_code, media_type=media_type)
        _apply_upstream_headers(resp, upstream_resp=upstream_resp)
        if location:
            resp.headers["Location"] = location
        return resp

    resp = StreamingResponse(
        _iter_content(upstream_resp),
        status_code=upstream_resp.status_code,
        media_type=media_type,
        background=None,
    )
    _apply_upstream_headers(resp, upstream_resp=upstream_resp)
    if location:
        resp.headers["Location"] = location
    return resp
