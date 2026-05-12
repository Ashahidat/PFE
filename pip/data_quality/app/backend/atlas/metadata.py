import logging
from collections import defaultdict
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from atlas.client import atlas_post, atlas_get, ATLAS_ENTITY_URL, ATLAS_ENTITY_BULK_URL
from atlas.columns import get_existing_columns
from atlas.glossary import set_terms_for_entity
from db.dataset_glossary_crud import get_assignments_for_dataset
from db.datasets import Dataset

logger = logging.getLogger("atlas.metadata")


def _get_dataset_name_and_qualified_name(dataset: Dataset) -> Tuple[str, str]:
    """
    Atlas entities inheriting from Referenceable require `qualifiedName`.
    Our DB may not always have it; fetch it from Atlas when missing.
    """
    dataset_name = (getattr(dataset, "name", None) or "").strip()
    dataset_qualified_name = (getattr(dataset, "atlas_qualified_name", None) or "").strip()

    if dataset_name and dataset_qualified_name:
        return dataset_name, dataset_qualified_name

    url = f"{ATLAS_ENTITY_URL}/guid/{dataset.atlas_guid}"
    entity = (atlas_get(url).json() or {}).get("entity") or {}
    attrs = entity.get("attributes") or {}
    qualified_name = (attrs.get("qualifiedName") or "").strip()
    name = (attrs.get("name") or "").strip()

    if not dataset_name:
        dataset_name = name
    if not dataset_qualified_name:
        dataset_qualified_name = qualified_name

    if not dataset_qualified_name:
        raise ValueError("Atlas DataSet.qualifiedName introuvable (obligatoire pour update)")
    if not dataset_name:
        raise ValueError("Atlas DataSet.name introuvable (obligatoire pour update)")

    return dataset_name, dataset_qualified_name


def _update_dataset_description(dataset: Dataset, dataset_name: str, dataset_qualified_name: str) -> None:
    payload = {
        "entities": [
            {
                "typeName": "DataSet",
                "guid": dataset.atlas_guid,
                "attributes": {"description": dataset.description or ""},
            }
        ]
    }
    payload["entities"][0]["attributes"]["qualifiedName"] = dataset_qualified_name
    payload["entities"][0]["attributes"]["name"] = dataset_name
    # Atlas bulk endpoint supports createOrUpdate with the {"entities":[...]} shape.
    atlas_post(ATLAS_ENTITY_BULK_URL, payload)
    logger.debug(f"🔁 Description dataset {dataset.atlas_guid[:8]} synchronisée")


def _update_column_descriptions(
    dataset: Dataset,
    dataset_qualified_name: str,
    descriptions: Dict[str, str],
    column_info: Dict[str, Dict[str, str]],
) -> None:
    if not descriptions:
        return
    entities = []
    for column_name, description in descriptions.items():
        info = column_info.get(column_name)
        if not info:
            logger.debug(f"⚠️ Colonne {column_name} introuvable dans Atlas, skip description")
            continue
        guid = info.get("guid")
        if not guid:
            continue
        qualified_name: Optional[str] = info.get("qualified_name")
        if not qualified_name:
            qualified_name = f"{dataset_qualified_name}.{column_name}"
        entities.append({
            "typeName": "Column",
            "guid": guid,
            "attributes": {
                # Important: if the caller explicitly provides an empty string, we want to clear the description
                # in Atlas (not keep the existing one).
                "description": "" if description is None else str(description),
                "qualifiedName": qualified_name,
                "name": column_name,
                "dataset": {"typeName": "DataSet", "guid": dataset.atlas_guid},
            }
        })
    if not entities:
        return
    atlas_post(ATLAS_ENTITY_BULK_URL, {"entities": entities})
    logger.debug(f"🔁 {len(entities)} descriptions de colonnes synchronisées pour {dataset.atlas_guid[:8]}")


def _assign_glossary_terms(
    db: Session,
    dataset: Dataset,
    column_info: Dict[str, Dict[str, str]],
    columns_to_align: Iterable[str] | None = None,
) -> None:
    assignments = get_assignments_for_dataset(db, dataset.id)
    dataset_terms = []
    column_terms = defaultdict(set)
    for assignment in assignments:
        term = getattr(assignment, "term", None)
        if not term or not term.atlas_guid:
            continue
        if assignment.column_name:
            column_terms[assignment.column_name].add(term.atlas_guid)
        else:
            dataset_terms.append(term.atlas_guid)

    # Always align dataset-level terms (including removals).
    set_terms_for_entity(
        dataset_terms,
        dataset.atlas_guid,
        "DataSet",
        dataset.name or dataset.atlas_guid,
    )
    logger.debug(f"📌 {len(dataset_terms)} terme(s) aligné(s) sur l'entité dataset")

    columns_to_process = set(column_terms.keys())
    if columns_to_align:
        columns_to_process.update(columns_to_align)

    if not columns_to_process:
        return

    for column_name in sorted(columns_to_process):
        term_guids = list(column_terms.get(column_name) or [])
        info = column_info.get(column_name)
        if not info or not info.get("guid"):
            logger.debug(f"⚠️ Colonne {column_name} sans GUID Atlas, skip term assign")
            continue
        entity_display = info.get("qualified_name") or f"{dataset.name}.{column_name}"
        set_terms_for_entity(
            term_guids,
            info["guid"],
            "Column",
            entity_display,
        )
        logger.debug(f"📌 Terme(s) aligné(s) à la colonne {column_name}")


def _get_dataset_details(dataset: Dataset) -> Dict:
    url = f"{ATLAS_ENTITY_URL}/guid/{dataset.atlas_guid}"
    response = atlas_get(url)
    entity = response.json().get("entity") or {}
    return entity


def sync_dataset_metadata_to_atlas(
    db: Session,
    dataset: Dataset,
    column_descriptions: Dict[str, str] | None = None,
    columns_to_align_terms: Iterable[str] | None = None,
) -> None:
    if not dataset.atlas_guid:
        raise ValueError("Dataset sans atlas_guid")

    dataset_name, dataset_qualified_name = _get_dataset_name_and_qualified_name(dataset)

    column_info = get_existing_columns(dataset.atlas_guid, dataset_qualified_name)
    logger.debug("sync_metadata: dataset %s has %d columns_from_atlas", dataset.atlas_guid, len(column_info))
    for col, info in column_info.items():
        logger.debug("column_info[%s]=%s", col, {k: info.get(k) for k in ["guid", "qualified_name"]})
    _update_dataset_description(dataset, dataset_name, dataset_qualified_name)
    if column_descriptions:
        _update_column_descriptions(dataset, dataset_qualified_name, column_descriptions, column_info)
    _assign_glossary_terms(db, dataset, column_info, columns_to_align=columns_to_align_terms)
    logger.info(f"✅ Métadonnées Atlas synchronisées pour {dataset.atlas_guid[:8]}")
