from fastapi import APIRouter, Depends, Response

from jwt_dependencies import get_current_user

router = APIRouter(prefix="/grafana", tags=["grafana"])


@router.get("/auth")
def grafana_auth(user=Depends(get_current_user)):
    """
    Endpoint intended for a reverse-proxy `auth_request`.

    If the JWT is valid, return 200 with headers that Grafana Auth Proxy will trust.
    """
    employee_id = user.get("employee_id") or user.get("sub") or ""
    username = user.get("username") or employee_id
    role = user.get("role") or "VIEWER"

    headers = {
        "X-WEBAUTH-USER": employee_id,
        "X-WEBAUTH-NAME": username,
        "X-WEBAUTH-ROLE": role,
    }
    return Response(status_code=200, headers=headers)

