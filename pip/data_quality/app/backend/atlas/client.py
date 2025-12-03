import requests
import logging

ATLAS_ENTITY_BULK_URL = "http://localhost:21000/api/atlas/v2/entity/bulk"
ATLAS_TYPEDEF_URL = "http://localhost:21000/api/atlas/v2/types/typedefs"
ATLAS_RELATIONSHIP_URL = "http://localhost:21000/api/atlas/v2/relationship"
ATLAS_SEARCH_URL = "http://localhost:21000/api/atlas/v2/search/basic"

AUTH = ("admin", "admin")
HEADERS = {"Content-Type": "application/json"}

logger = logging.getLogger("atlas.client")


def atlas_post(url, payload):
    res = requests.post(url, json=payload, auth=AUTH, headers=HEADERS)
    if not res.ok:
        # ⛔ Log détaillé et utile
        logger.error(
            f"[atlas_post] FAILED {url} "
            f"status={res.status_code} "
            f"text={res.text}"
        )
        try:
            res.raise_for_status()
        except Exception as e:
            # Remonter une erreur compréhensible côté FastAPI
            raise Exception(f"Atlas POST error {res.status_code}: {res.text}") from e
    return res


def atlas_get(url: str):
    logger.info(f"➡️ GET {url}")
    res = requests.get(url, auth=AUTH, headers=HEADERS)
    res.raise_for_status()
    return res

def atlas_put(url, payload):
    res = requests.put(url, json=payload, auth=AUTH, headers=HEADERS)
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

