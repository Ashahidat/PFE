import requests
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

ATLAS_ENTITY_BULK_URL = "http://localhost:21000/api/atlas/v2/entity/bulk"
ATLAS_TYPEDEF_URL = "http://localhost:21000/api/atlas/v2/types/typedefs"
ATLAS_RELATIONSHIP_URL = "http://localhost:21000/api/atlas/v2/relationship"
ATLAS_SEARCH_URL = "http://localhost:21000/api/atlas/v2/search/basic"
ATLAS_ENTITY_URL = "http://localhost:21000/api/atlas/v2/entity"
ATLAS_GLOSSARY_URL = "http://localhost:21000/api/atlas/v2/glossary"
ATLAS_GLOSSARY_TERM_URL = f"{ATLAS_GLOSSARY_URL}/term"
ATLAS_GLOSSARY_TERMS_URL = f"{ATLAS_GLOSSARY_URL}/terms"

AUTH = ("admin", "admin")
HEADERS = {"Content-Type": "application/json"}

logger = logging.getLogger("atlas.client")

_DEFAULT_CONNECT_TIMEOUT = float(os.getenv("ATLAS_CONNECT_TIMEOUT", "3.05"))
_DEFAULT_READ_TIMEOUT = float(os.getenv("ATLAS_READ_TIMEOUT", "120"))
_DEFAULT_MAX_RETRIES = int(os.getenv("ATLAS_HTTP_MAX_RETRIES", "3"))
_DEFAULT_BACKOFF_SECONDS = float(os.getenv("ATLAS_HTTP_BACKOFF_SECONDS", "0.8"))


def _default_timeout() -> Tuple[float, float]:
    return (_DEFAULT_CONNECT_TIMEOUT, _DEFAULT_READ_TIMEOUT)


def atlas_request(
    method: str,
    url: str,
    *,
    json: Any = None,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    auth=AUTH,
    timeout: Optional[Tuple[float, float]] = None,
    verify: bool = True,
    max_retries: Optional[int] = None,
    backoff_seconds: Optional[float] = None,
) -> requests.Response:
    timeout = timeout or _default_timeout()
    max_retries = _DEFAULT_MAX_RETRIES if max_retries is None else max_retries
    backoff_seconds = _DEFAULT_BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds

    merged_headers = dict(HEADERS)
    if headers:
        merged_headers.update(headers)

    last_exc: Optional[BaseException] = None
    for attempt in range(max_retries):
        try:
            res = requests.request(
                method=method,
                url=url,
                json=json,
                params=params,
                auth=auth,
                headers=merged_headers,
                timeout=timeout,
                verify=verify,
            )
            if res.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait = backoff_seconds * (2**attempt)
                logger.warning(
                    f"[atlas_request] RETRY {method.upper()} {url} "
                    f"status={res.status_code} wait={wait:.2f}s"
                )
                time.sleep(wait)
                continue
            return res
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt >= max_retries - 1:
                raise
            wait = backoff_seconds * (2**attempt)
            logger.warning(
                f"[atlas_request] RETRY {method.upper()} {url} "
                f"error={type(exc).__name__} wait={wait:.2f}s"
            )
            time.sleep(wait)

    if last_exc:
        raise last_exc
    raise RuntimeError("atlas_request: unreachable")


def atlas_post(url, payload):
    res = atlas_request("POST", url, json=payload)
    if not res.ok:
        logger.error(
            f"[atlas_post] FAILED {url} "
            f"status={res.status_code} "
            f"text={res.text}"
        )
        try:
            res.raise_for_status()
        except Exception as e:
            raise Exception(f"Atlas POST error {res.status_code}: {res.text}") from e
    return res

def atlas_get(url: str):
    logger.info(f"➡️ GET {url}")
    res = atlas_request("GET", url)
    if not res.ok:
        logger.error(
            f"[atlas_get] FAILED {url} "
            f"status={res.status_code} "
            f"text={res.text}"
        )
    res.raise_for_status()
    return res

def atlas_put(url, payload):
    res = atlas_request("PUT", url, json=payload)
    if not res.ok:
        logger.error(
            f"[atlas_put] FAILED {url} "
            f"status={res.status_code} "
            f"text={res.text}"
        )
        try:
            res.raise_for_status()
        except Exception as e:
            raise Exception(f"Atlas PUT error {res.status_code}: {res.text}") from e
    return res

def atlas_delete(url: str):
    res = atlas_request("DELETE", url)
    if not res.ok and res.status_code != 404:
        logger.error(
            f"[atlas_delete] FAILED {url} "
            f"status={res.status_code} "
            f"text={res.text}"
        )
        try:
            res.raise_for_status()
        except Exception as e:
            raise Exception(f"Atlas DELETE error {res.status_code}: {res.text}") from e
    return res


def get_typedef_by_name(name: str, typedef_type: str = "entity"):
    """
    Récupère un typedef par son nom en utilisant l'API correcte.
    typedef_type: entity | relationship | classification | enum | struct | business_metadata
    """
    url = f"{ATLAS_TYPEDEF_URL}?name={name}&type={typedef_type}"
    logger.info(f"➡️ GET {url}")
    res = atlas_request("GET", url)
    if res.status_code == 404:
        logger.info(f"  ℹ️ Typedef {name} non trouvé (404)")
        return None
    res.raise_for_status()
    data = res.json()

    defs_key = {
        "entity": "entityDefs",
        "relationship": "relationshipDefs",
        "classification": "classificationDefs",
        "enum": "enumDefs",
        "struct": "structDefs",
        "business_metadata": "businessMetadataDefs",
    }.get(typedef_type, "entityDefs")

    defs = (data or {}).get(defs_key) or []
    if defs:
        first = defs[0]
        logger.info(f"  ✅ Typedef {name} récupéré ({defs_key})")
        return first
    logger.info(f"  ℹ️ Typedef {name} trouvé mais vide")
    return None
