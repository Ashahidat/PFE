import requests
import logging

ATLAS_ENTITY_BULK_URL = "http://localhost:21000/api/atlas/v2/entity/bulk"
ATLAS_TYPEDEF_URL = "http://localhost:21000/api/atlas/v2/types/typedefs"
ATLAS_RELATIONSHIP_URL = "http://localhost:21000/api/atlas/v2/relationship"
ATLAS_SEARCH_URL = "http://localhost:21000/api/atlas/v2/search/basic"
ATLAS_ENTITY_URL = "http://localhost:21000/api/atlas/v2/entity"
ATLAS_GLOSSARY_URL = "http://localhost:21000/api/atlas/v2/glossary"
ATLAS_GLOSSARY_TERM_URL = f"{ATLAS_GLOSSARY_URL}/term"

AUTH = ("admin", "admin")
HEADERS = {"Content-Type": "application/json"}

logger = logging.getLogger("atlas.client")

def atlas_post(url, payload):
    res = requests.post(url, json=payload, auth=AUTH, headers=HEADERS)
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
    res = requests.get(url, auth=AUTH, headers=HEADERS)
    if not res.ok:
        logger.error(
            f"[atlas_get] FAILED {url} "
            f"status={res.status_code} "
            f"text={res.text}"
        )
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

def get_typedef_by_name(name: str):
    """
    Récupère un typedef par son nom en utilisant l'API correcte
    """
    url = f"{ATLAS_TYPEDEF_URL}?name={name}&type=entity"
    logger.info(f"➡️ GET {url}")
    res = requests.get(url, auth=AUTH, headers=HEADERS)
    if res.status_code == 404:
        logger.info(f"  ℹ️ Typedef {name} non trouvé (404)")
        return None
    res.raise_for_status()
    data = res.json()
    if data and "entityDefs" in data and len(data["entityDefs"]) > 0:
        logger.info(f"  ✅ Typedef {name} récupéré avec {len(data['entityDefs'][0].get('attributeDefs', []))} attributs")
        return data["entityDefs"][0]
    logger.info(f"  ℹ️ Typedef {name} trouvé mais vide")
    return None
