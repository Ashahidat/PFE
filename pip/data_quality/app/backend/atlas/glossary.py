import logging
import re
from typing import List, Dict, Optional
from urllib.parse import quote

from sqlalchemy.orm import Session

from atlas.client import (
    atlas_get,
    atlas_post,
    atlas_put,
    atlas_request,
    ATLAS_GLOSSARY_URL,
    ATLAS_GLOSSARY_TERM_URL,
    ATLAS_GLOSSARY_TERMS_URL,
    AUTH,
    HEADERS,
)
from db.glossary import Glossary, GlossaryTerm, GlossaryCategory

logger = logging.getLogger("atlas.glossary")
logger.setLevel(logging.DEBUG)

ATLAS_GLOSSARY_CATEGORY_URL = f"{ATLAS_GLOSSARY_URL}/category"

DEFAULT_GLOSSARY_QUALIFIED_NAME = "pfe_glossary"
DEFAULT_GLOSSARY_DISPLAY_NAME = "Glossaire PFE"
DEFAULT_GLOSSARY_SHORT_DESCRIPTION = "Glossaire partagé synchronisé depuis l’application PFE."
DEFAULT_GLOSSARY_LONG_DESCRIPTION = "Conteneur principal des termes métier qui décrivent les datasets poussés vers Atlas."
DEFAULT_GLOSSARY_LANGUAGE = "fr-FR"


def _slugify(text: str, default: str = "item") -> str:
    candidate = re.sub(r"[^\w]+", "_", (text or "").lower())
    candidate = re.sub(r"_+", "_", candidate).strip("_")
    return candidate or default


def _build_category_payload(category: GlossaryCategory, glossary: Dict[str, str]) -> Dict:
    payload = {
        "name": category.name,
        "qualifiedName": category.qualified_name,
        "shortDescription": category.description or category.name,
        "longDescription": category.description or category.name,
        "anchor": {
            "glossaryGuid": glossary["guid"],
            "displayText": glossary.get("name", DEFAULT_GLOSSARY_DISPLAY_NAME),
        },
    }
    return payload


def _build_term_payload(term: GlossaryTerm, glossary: Dict[str, str], category_guid: Optional[str]) -> Dict:
    qualified_name = term.qualified_name or f"{_slugify(term.term)}@{glossary['qualifiedName']}"
    payload = {
        "name": term.term,
        "qualifiedName": qualified_name,
        "shortDescription": term.description or term.term,
        "longDescription": term.description or term.term,
        "anchor": {
            "glossaryGuid": glossary["guid"],
            "displayText": glossary.get("name", DEFAULT_GLOSSARY_DISPLAY_NAME),
        },
    }
    if category_guid:
        payload["categories"] = [
            {
                "categoryGuid": category_guid,
                "description": term.category.description if term.category and term.category.description else term.description or term.term,
                "displayText": term.category.name if term.category else glossary.get("name"),
                "status": "ACTIVE",
            }
        ]
    return payload


def _fetch_existing_terms(glossary_guid: str) -> Dict[str, Dict]:
    try:
        res = atlas_get(f"{ATLAS_GLOSSARY_URL}/{glossary_guid}/terms")
        data = res.json() or {}
        terms = data.get("terms") or data.get("elements") or []
        existing = {term.get("qualifiedName"): term for term in terms if term.get("qualifiedName")}
        return existing
    except Exception as exc:
        logger.warning(f"Impossible de récupérer les termes pour le glossaire {glossary_guid}: {exc}")
        return {}


def _fetch_existing_categories(glossary_guid: str) -> Dict[str, Dict]:
    try:
        res = atlas_get(f"{ATLAS_GLOSSARY_URL}/{glossary_guid}")
        data = res.json() or {}
        categories = data.get("categories") or []
        existing = {}
        for category in categories:
            qn = category.get("qualifiedName")
            display = category.get("displayText")
            if qn:
                existing[qn] = category
            if display:
                existing.setdefault(display, category)
        return existing
    except Exception as exc:
        logger.warning(f"Impossible de récupérer les catégories pour le glossaire {glossary_guid}: {exc}")
        return {}


def _extract_guid(payload: Dict) -> Optional[str]:
    return payload.get("categoryGuid") or payload.get("guid")


def get_or_create_glossary(
    qualified_name: str = DEFAULT_GLOSSARY_QUALIFIED_NAME,
    display_name: str = DEFAULT_GLOSSARY_DISPLAY_NAME,
) -> Dict:
    try:
        encoded = quote(qualified_name, safe="")
        res = atlas_get(f"{ATLAS_GLOSSARY_URL}?name={encoded}")
        glossaries = res.json() or []
        if glossaries:
            glossary = glossaries[0]
            # Best-effort: keep Atlas display name aligned with DB renames.
            # Even if this fails (API differences), term/category sync should still work.
            try:
                glossary_guid = glossary.get("guid")
                current_name = glossary.get("name")
                if glossary_guid and display_name and current_name and current_name != display_name:
                    update_payload = {
                        "guid": glossary_guid,
                        "qualifiedName": glossary.get("qualifiedName") or qualified_name,
                        "name": display_name,
                        "shortDescription": glossary.get("shortDescription") or DEFAULT_GLOSSARY_SHORT_DESCRIPTION,
                        "longDescription": glossary.get("longDescription") or DEFAULT_GLOSSARY_LONG_DESCRIPTION,
                        "language": glossary.get("language") or DEFAULT_GLOSSARY_LANGUAGE,
                    }
                    updated = atlas_put(f"{ATLAS_GLOSSARY_URL}/{glossary_guid}", update_payload).json() or {}
                    glossary = updated or glossary
            except Exception as exc:
                logger.debug(f"Mise à jour du nom du glossaire Atlas ignorée: {exc}")
            logger.debug(f"Glossaire trouvé dans Atlas: {glossary['name']} ({glossary['guid']})")
            return glossary
    except Exception as exc:
        logger.debug(f"Recherche du glossaire {qualified_name} échouée: {exc}")

    payload = {
        "name": display_name,
        "qualifiedName": qualified_name,
        "shortDescription": DEFAULT_GLOSSARY_SHORT_DESCRIPTION,
        "longDescription": DEFAULT_GLOSSARY_LONG_DESCRIPTION,
        "language": DEFAULT_GLOSSARY_LANGUAGE,
    }
    res = atlas_post(ATLAS_GLOSSARY_URL, payload)
    glossary = res.json()
    logger.info(f"Glossaire créé dans Atlas: {glossary.get('name')} ({glossary.get('guid')})")
    return glossary


def sync_glossary_terms(glossaries: List[Glossary], db: Session | None = None) -> Dict[str, int]:
    stats = {
        "created_terms": 0,
        "existing_terms": 0,
        "total_terms": 0,
        "created_categories": 0,
        "existing_categories": 0,
        "total_categories": 0,
        "glossaries_synced": 0,
        "glossary_guids": [],
        "term_guids": []
    }

    if not glossaries:
        logger.debug("Aucun glossaire à synchroniser.")
        return stats

    for glossary in glossaries:
        if not glossary or not glossary.qualified_name:
            continue

        atlas_glossary = get_or_create_glossary(
            qualified_name=glossary.qualified_name,
            display_name=glossary.name
        )
        atlas_glossary_qn = atlas_glossary.get("qualifiedName") or glossary.qualified_name
        glossary_guid = atlas_glossary.get("guid")
        if not glossary_guid:
            continue

        stats["glossaries_synced"] += 1
        stats["glossary_guids"].append(glossary_guid)
        existing_terms = _fetch_existing_terms(glossary_guid)
        existing_categories = _fetch_existing_categories(glossary_guid)
        category_guid_map: Dict[int, str] = {}

        for category in glossary.categories:
            stats["total_categories"] += 1
            qn = category.qualified_name or category.name
            existing = existing_categories.get(qn)
            if existing:
                stats["existing_categories"] += 1
                guid = _extract_guid(existing)
                if guid:
                    category_guid_map[category.id] = guid
                    if db and category.atlas_guid != guid:
                        category.atlas_guid = guid
                continue

            payload = _build_category_payload(category, atlas_glossary)
            try:
                response = atlas_post(ATLAS_GLOSSARY_CATEGORY_URL, payload)
                stats["created_categories"] += 1
                data = response.json() or {}
                guid = _extract_guid(data)
                if guid:
                    category_guid_map[category.id] = guid
                    if db and category.atlas_guid != guid:
                        category.atlas_guid = guid
                cat_key = data.get("qualifiedName") or payload.get("qualifiedName")
                if cat_key:
                    existing_categories[cat_key] = data
                logger.debug(f"Catégorie Atlas créée: {category.name} ({qn})")
            except Exception as exc:
                logger.warning(f"Impossible de créer la catégorie '{category.name}': {exc}")

        terms = glossary.terms or []
        stats["total_terms"] += len(terms)
        for term in terms:
            if db and term and not term.qualified_name:
                # If the term already exists in Atlas (atlas_guid set), keep the historical qualifiedName
                # pattern so we can look it up reliably.
                base = _slugify(term.term, "term")
                if term.atlas_guid:
                    term.qualified_name = f"{base}@{atlas_glossary_qn}"
                else:
                    # For unsynced terms, include the DB id to prevent slug collisions.
                    term.qualified_name = f"{base}_{term.id}@{atlas_glossary_qn}"
            payload = _build_term_payload(term, atlas_glossary, category_guid_map.get(term.category_id))
            qn = payload["qualifiedName"]
            if qn in existing_terms:
                stats["existing_terms"] += 1
                guid = existing_terms[qn].get("guid")
                if guid:
                    stats["term_guids"].append(guid)
                if db and term and term.atlas_guid != guid:
                    term.atlas_guid = guid
                # Best-effort: align display fields on rename/description change.
                if guid:
                    try:
                        existing = existing_terms.get(qn) or {}
                        if (
                            existing.get("name") != payload.get("name")
                            or existing.get("shortDescription") != payload.get("shortDescription")
                            or existing.get("longDescription") != payload.get("longDescription")
                        ):
                            update_payload = dict(payload)
                            update_payload["guid"] = guid
                            atlas_put(f"{ATLAS_GLOSSARY_TERM_URL}/{guid}", update_payload)
                    except Exception as exc:
                        logger.debug(f"Mise à jour du terme Atlas ignorée ({qn}): {exc}")
                continue
            try:
                response = atlas_post(ATLAS_GLOSSARY_TERM_URL, payload)
                stats["created_terms"] += 1
                term_guid = response.json().get("guid")
                if term_guid:
                    stats["term_guids"].append(term_guid)
                if db and term_guid:
                    term.atlas_guid = term_guid
                logger.debug(f"Terme Atlas créé: {term.term} ({qn})")
            except Exception as exc:
                logger.warning(f"Impossible de créer le terme '{term.term}' dans Atlas: {exc}")
        if db:
            try:
                db.commit()
            except Exception:
                db.rollback()


    logger.info(
        f"{stats['created_terms']} termes créés ({stats['existing_terms']} déjà existants) "
        f"et {stats['created_categories']} catégories créées "
        f"sur {stats['total_categories']} catégories totales."
    )

    return stats


def _get_assigned_entities(term_guid: str) -> List[Dict]:
    try:
        res = atlas_get(f"{ATLAS_GLOSSARY_TERMS_URL}/{term_guid}/assignedEntities")
        data = res.json() if res and res.ok else {}
    except Exception as exc:
        logger.warning(f"Impossible de récupérer assignedEntities pour {term_guid}: {exc}")
        return []

    if isinstance(data, list):
        return data

    candidates = (
        data.get("entities") or
        data.get("assignedEntities") or
        data.get("elements") or
        data.get("results") or
        []
    )
    if isinstance(candidates, dict):
        return [candidates]
    return candidates


def _entity_already_assigned(term_guid: str, entity_guid: str) -> bool:
    for entry in _get_assigned_entities(term_guid):
        for key in ("entityGuid", "guid", "assignedEntityGuid"):
            if entry.get(key) == entity_guid:
                return True
    return False


def assign_terms_to_entity(
    term_guids: List[str],
    entity_guid: str,
    entity_type: str,
    entity_display: str,
):
    if not term_guids:
        return False

    success = True
    payload = [
        {
            "displayText": entity_display,
            "entityStatus": "ACTIVE",
            "qualifiedName": entity_display,
            "typeName": entity_type,
            "guid": entity_guid,
        }
    ]

    for term_guid in term_guids:
        if _entity_already_assigned(term_guid, entity_guid):
            logger.debug(f"Terme {term_guid} déjà assigné à {entity_guid}, skip")
            continue
        try:
            # L'endpoint Atlas attendu pour l'assignation est au pluriel `/terms/{guid}/assignedEntities`
            # (voir application.log: NotFound sur /term/.../assignedEntities).
            url = f"{ATLAS_GLOSSARY_TERMS_URL}/{term_guid}/assignedEntities"
            res = atlas_request("POST", url, json=payload, auth=AUTH, headers=HEADERS)
            if res.status_code not in (200, 204):
                logger.warning(
                    f"Échec assignation terme {term_guid} à {entity_guid}: {res.status_code} {res.text}"
                )
                success = False
        except Exception as exc:
            logger.error(f"Erreur assignation terme {term_guid}: {exc}")
            success = False

    return success
