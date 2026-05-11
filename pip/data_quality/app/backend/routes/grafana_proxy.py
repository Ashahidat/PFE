from __future__ import annotations

from typing import Iterable

import logging
import re
import requests
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import String, cast, func
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import MutableHeaders

from core.roles import ADMINISTRATORS
from db.connexion_db import get_db
from db.projects import Project
from grafana.provisioning import provision_project_dashboards
from grafana.settings import get_grafana_settings
from jwt_dependencies import get_current_user

router = APIRouter(prefix="/grafana", tags=["grafana"])
logger = logging.getLogger("grafana-proxy")


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


def _filter_cookie_header(cookie_header: str, *, drop_names: set[str]) -> str:
    """
    Keep Grafana cookies (e.g. `grafana_session`) but drop app cookies (e.g. JWT `access_token`)
    so we don't leak them to the Grafana upstream.
    """
    kept: list[str] = []
    for part in cookie_header.split(";"):
        part = part.strip()
        if not part:
            continue
        name = part.split("=", 1)[0].strip()
        if name in drop_names:
            continue
        kept.append(part)
    return "; ".join(kept)


def _rewrite_html_for_subpath(html: str, subpath: str) -> str:
    """
    Grafana needs to know when it's served under a subpath (e.g. `/grafana/`).
    If the upstream Grafana isn't configured with `root_url` + `serve_from_sub_path`,
    it will emit absolute asset URLs like `/public/build/...` which break behind our proxy.

    We apply a minimal rewrite for HTML responses so assets are requested under the proxy prefix.
    """
    prefix = subpath.rstrip("/")
    if not prefix:
        return html

    # base href is the most important for Grafana's frontend router.
    # Be tolerant to formatting differences across Grafana versions.
    html = re.sub(r'<base\s+href="[^"]*"\s*/?>', f'<base href="{prefix}/">', html, count=1)

    # Grafana also embeds runtime settings in the HTML bootstrap payload.
    # If Grafana isn't configured with `serve_from_sub_path`, it will ship:
    #   "appSubUrl":""
    # which makes the client-side router treat `/grafana/...` as an unknown route.
    # Keep this rewrite conservative (exact empty value only) to avoid clobbering
    # already-correct subpath setups.
    html = re.sub(r'("appSubUrl"\s*:\s*)""', rf'\1"{prefix}"', html)
    # Some Grafana builds embed unquoted keys in bootstrapped JS.
    html = re.sub(r'(\bappSubUrl\s*:\s*)""', rf'\1"{prefix}"', html)

    # Rewrite only attribute values that start at the root.
    # Keep it conservative to avoid mangling protocol-relative URLs (//...).
    html = re.sub(r'(\s(?:src|href)=)"/(?!grafana/)(?!/)', rf'\1"{prefix}/', html)
    return html


def _get_set_cookie_values(upstream_resp: requests.Response) -> list[str]:
    raw_headers = getattr(upstream_resp, "raw", None)
    raw = getattr(raw_headers, "headers", None)
    if raw is None:
        return []

    for method in ("get_all", "getlist"):
        getter = getattr(raw, method, None)
        if getter is None:
            continue
        try:
            values = getter("Set-Cookie")
        except TypeError:
            # Some implementations require lower-case key or different signature.
            try:
                values = getter("set-cookie")
            except Exception:
                continue
        except Exception:
            continue
        if not values:
            return []
        if isinstance(values, (list, tuple)):
            return [str(v) for v in values if v]
        return [str(values)]

    try:
        single = raw.get("Set-Cookie")
    except Exception:
        single = None
    return [str(single)] if single else []


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

    for cookie in _get_set_cookie_values(upstream_resp):
        headers.append("Set-Cookie", cookie)


def _project_id_prefix_from_folder_uid(folder_uid: str) -> str | None:
    """
    Folder UIDs are generated as: `pfe-project-{compact_uuid[:24]}`.
    We can map back to a project by prefix-matching the compact uuid.
    """
    value = (folder_uid or "").strip().lower()
    if not value.startswith("pfe-project-"):
        return None
    prefix = value[len("pfe-project-") :].strip()
    if not prefix:
        return None
    if not re.fullmatch(r"[a-z0-9]+", prefix):
        return None
    return prefix


def _maybe_autoprovision_folder(
    *,
    settings,
    folder_uid: str,
    db: Session,
    project_department: str,
    identity_headers: dict[str, str] | None,
) -> bool:
    """
    Best-effort: if a request hits a missing project folder in Grafana, try provisioning it on-demand.
    Returns True when a provisioning attempt was made (success or failure), False when not eligible.
    """
    if not settings.enabled:
        return False
    if not (settings.service_token or (settings.admin_user and settings.admin_password) or identity_headers):
        return False

    prefix = _project_id_prefix_from_folder_uid(folder_uid)
    if not prefix:
        return False

    compact_expr = func.replace(cast(Project.id, String), "-", "")
    project = db.query(Project).filter(compact_expr.ilike(f"{prefix}%")).first()
    if not project:
        return False

    logger.warning(
        "🛠️ [Grafana] folder uid=%s missing; auto-provisioning for project_id=%s",
        folder_uid,
        project.id,
    )
    try:
        provision_project_dashboards(
            settings,
            project_id=str(project.id),
            project_name=project.name,
            project_visibility=project.visibility,
            owner_department=project_department or "UNKNOWN",
            identity_headers=identity_headers,
        )
    except Exception:
        logger.exception("⚠️ [Grafana] auto-provisioning failed for folder_uid=%s", folder_uid)
        return True

    logger.info("✅ [Grafana] auto-provisioning done for folder_uid=%s", folder_uid)
    return True


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def grafana_reverse_proxy(
    path: str,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Minimal reverse-proxy to access Grafana through this FastAPI backend.

    Browser flow:
    - user logs in via `/login` (JWT stored in httpOnly cookie `access_token`)
    - user navigates to `/grafana/...`
    - backend validates JWT then forwards the request to Grafana with `X-WEBAUTH-*` headers
    """

    settings = get_grafana_settings()
    upstream_base = settings.url.rstrip("/")

    # Grafana front-end periodically calls this endpoint to rotate its session token.
    # When Grafana is accessed through an auth proxy (we authenticate users ourselves via JWT
    # and forward identity via `X-WEBAUTH-*` headers), this rotation endpoint is not required
    # and may return 401, causing the UI to retry indefinitely.
    #
    # We short-circuit it to avoid an infinite loop and unnecessary load.
    normalized_path = path.lstrip("/")
    if request.method == "POST" and normalized_path == "api/user/auth-tokens/rotate":
        return Response(status_code=204)

    # Grafana is configured to be served under `/grafana/` (see grafana/AUTH_PROXY_SETUP.md),
    # so the upstream expects requests to include that prefix.
    #
    # If we proxy `/grafana/login` to upstream `/login`, Grafana will redirect to `/grafana/login`
    # (because `serve_from_sub_path = true`), causing an infinite 301/302 loop through this proxy.
    upstream_path = f"/grafana/{path.lstrip('/')}"
    upstream_url = f"{upstream_base}{upstream_path}"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    employee_id = user.get("employee_id") or user.get("sub") or ""
    username = user.get("username") or employee_id
    app_role = user.get("role") or "UNKNOWN"
    department = user.get("department") or ""

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

    # Forward Grafana's own session cookies back to Grafana so endpoints like
    # `/api/user/auth-tokens/rotate` work, but drop our JWT cookie to avoid leaking it upstream.
    if incoming_cookie:
        filtered = _filter_cookie_header(incoming_cookie, drop_names={"access_token"})
        if filtered:
            upstream_headers["Cookie"] = filtered

    grafana_role = "Admin" if str(app_role).upper() in ADMINISTRATORS else "Viewer"

    upstream_headers["X-WEBAUTH-USER"] = employee_id
    upstream_headers["X-WEBAUTH-NAME"] = username
    # Grafana expects org role values like "Viewer"/"Editor"/"Admin".
    # Default to Viewer; allow app administrators to become Grafana org Admin
    # to avoid "can't see folders" when team sync isn't configured.
    upstream_headers["X-WEBAUTH-ROLE"] = grafana_role
    # Extra context (not interpreted by Grafana core, but useful for logs/proxies/plugins).
    upstream_headers["X-PFE-ROLE"] = str(app_role)
    if department:
        upstream_headers["X-PFE-DEPARTMENT"] = str(department)
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

    # If a project folder does not exist yet (provisioning skipped/failed),
    # Grafana returns 404 for its folder API and the UI shows "folders not found".
    # Auto-provision on-demand and retry once so the user gets a working folder view.
    if upstream_resp.status_code == 404 and request.method == "GET":
        normalized_path = path.lstrip("/")
        folder_uid = None

        # Newer Grafana path.
        match = re.fullmatch(r"api/folders/uid/([^/?#]+)", normalized_path)
        if match:
            folder_uid = match.group(1)

        # Legacy Grafana path used by the UI: `/api/folders/{uid}`.
        if folder_uid is None:
            match = re.fullmatch(r"api/folders/([^/?#]+)", normalized_path)
            if match:
                candidate = match.group(1)
                if candidate not in {"general"}:
                    folder_uid = candidate

        # Nested folders / listings: `/api/folders?parentUid=...` (returns 404 when parentUid is unknown).
        if folder_uid is None and normalized_path == "api/folders":
            query = request.url.query or ""
            m = re.search(r"(?:^|&)parentUid=([^&]+)", query)
            if m:
                folder_uid = requests.utils.unquote(m.group(1))

        if folder_uid:
            identity_headers = None
            # If no Grafana API creds are configured, we can still provision using Grafana auth-proxy
            # (trusted X-WEBAUTH-* headers) but only for app administrators.
            if str(user.get("role") or "").upper() in ADMINISTRATORS:
                identity_headers = {
                    "X-WEBAUTH-USER": str(employee_id),
                    "X-WEBAUTH-NAME": str(username),
                    "X-WEBAUTH-ROLE": "Admin",
                }
            attempted = await run_in_threadpool(
                _maybe_autoprovision_folder,
                settings=settings,
                folder_uid=folder_uid,
                db=db,
                project_department=(user.get("department") or ""),
                identity_headers=identity_headers,
            )
            if attempted:
                upstream_resp = await run_in_threadpool(
                    requests.request,
                    method=request.method,
                    url=upstream_url,
                    headers=upstream_headers,
                    data=data,
                    allow_redirects=False,
                    stream=True,
                    timeout=30,
                )
            else:
                auth_mode = "none"
                if settings.service_token:
                    auth_mode = "bearer"
                elif settings.admin_user and settings.admin_password:
                    auth_mode = "basic"
                logger.warning(
                    "ℹ️ [Grafana] folder uid=%s missing but auto-provision skipped (enabled=%s auth=%s)",
                    folder_uid,
                    settings.enabled,
                    auth_mode,
                )

    location = upstream_resp.headers.get("location")
    if location and location.startswith("/") and not location.startswith("/grafana/"):
        location = f"/grafana{location}"

    media_type = upstream_resp.headers.get("content-type")

    # If Grafana isn't configured for subpath serving, rewrite the HTML entrypoint.
    if media_type and "text/html" in media_type.lower():
        text = await run_in_threadpool(lambda: upstream_resp.text)
        rewritten = _rewrite_html_for_subpath(text, "/grafana")
        resp = Response(
            content=rewritten,
            status_code=upstream_resp.status_code,
            media_type=media_type,
        )
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
