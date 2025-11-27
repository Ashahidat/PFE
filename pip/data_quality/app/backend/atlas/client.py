import requests
import logging

ATLAS_ENTITY_BULK_URL = "http://localhost:21000/api/atlas/v2/entity/bulk"
ATLAS_TYPEDEF_URL = "http://localhost:21000/api/atlas/v2/types/typedefs"
ATLAS_RELATIONSHIP_URL = "http://localhost:21000/api/atlas/v2/relationship"
ATLAS_SEARCH_URL = "http://localhost:21000/api/atlas/v2/search/basic"

AUTH = ("admin", "admin")
HEADERS = {"Content-Type": "application/json"}

logger = logging.getLogger("atlas.client")


def atlas_post(url: str, payload: dict):
    logger.info(f"➡️ POST {url}")
    res = requests.post(url, auth=AUTH, headers=HEADERS, json=payload)
    res.raise_for_status()
    logger.info(f"⬅️ Status: {res.status_code}")
    return res


def atlas_get(url: str):
    logger.info(f"➡️ GET {url}")
    res = requests.get(url, auth=AUTH, headers=HEADERS)
    res.raise_for_status()
    return res

def atlas_put(url: str, payload: dict):
    logger.info(f"➡️ PUT {url}")
    res = requests.put(url, auth=AUTH, headers=HEADERS, json=payload)
    res.raise_for_status()
    logger.info(f"⬅️ Status: {res.status_code}")
    return res
