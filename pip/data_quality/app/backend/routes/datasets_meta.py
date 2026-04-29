from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List, Optional

from db.connexion_db import get_db
from db.datasets import Dataset
from db.dataset_glossary_crud import (
    get_assignments_for_dataset,
    set_assignment_for_column,
    set_assignments_for_column,
)
from db.dataset_versions import DatasetVersion
from db.crud_column_descriptions import (
    create_or_update_description,
    get_description_dict_by_version
)
from db.glossary import Glossary, GlossaryCategory, GlossaryTerm
from jwt_dependencies import get_current_user
from core.permissions import (
    can_view_dataset,
    can_modify_dataset,
    _get_employee_identifier
)
from atlas.glossary import (
    DEFAULT_GLOSSARY_QUALIFIED_NAME,
    _get_atlas_category_by_guid,
    _get_atlas_term_by_guid,
    sync_glossary_terms,
    get_entity_assigned_term_guids,
)
from atlas.metadata import sync_dataset_metadata_to_atlas
from atlas.columns import get_existing_columns
router = APIRouter()


class AssignmentInfo(BaseModel):
    term_id: int
    term: str
    glossary_id: int | None = None
    glossary_name: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    assigned_by: str | None = None
    assigned_at: str | None = None


class ColumnMetadata(BaseModel):
    name: str
    description: str | None = None
    classification: AssignmentInfo | None = None
    classifications: List[AssignmentInfo] = []


class ProjectInfo(BaseModel):
    id: str
    name: str
    visibility: str


class DatasetMetadataResponse(BaseModel):
    id: str
    name: str
    file_name: str
    hash: str
    project: ProjectInfo | None = None
    uploaded_by: str | None = None
    description: str | None = None
    classification: str
    dataset_assignment: AssignmentInfo | None = None
    dataset_assignments: List[AssignmentInfo] = []
    columns: List[ColumnMetadata]
    can_edit: bool


class MyDatasetListItem(BaseModel):
    id: str
    name: str
    uploaded_by: str | None = None
    project: ProjectInfo | None = None
    description: str | None = None
    classification: str
    columns: List[str]
    columns_count: int
    created_at: str | None = None
    dataset_assignment: AssignmentInfo | None = None
    dataset_assignments: List[AssignmentInfo] = []
    atlas_guid: str | None = None
    atlas_synced: bool
    can_edit: bool


class ColumnUpdatePayload(BaseModel):
    description: str | None = None
    glossary_term_id: int | None = None
    glossary_term_ids: List[int] | None = None


class DatasetClassificationPayload(BaseModel):
    glossary_term_id: int | None = None
    glossary_term_ids: List[int] | None = None

class DatasetDescriptionPayload(BaseModel):
    description: str | None = None


def _get_or_create_db_glossary(db: Session, qualified_name: str, display_name: str | None = None) -> Glossary:
    qn = (qualified_name or "").strip() or DEFAULT_GLOSSARY_QUALIFIED_NAME
    glossary = db.query(Glossary).filter(Glossary.qualified_name == qn).first()
    if glossary:
        return glossary
    glossary = Glossary(
        name=(display_name or qn).strip() or qn,
        qualified_name=qn,
        description=None,
        department=None,
        created_by=None,
    )
    db.add(glossary)
    db.commit()
    db.refresh(glossary)
    return glossary


def _get_or_create_db_category(
    db: Session,
    glossary: Glossary,
    atlas_guid: str,
    fallback_name: str | None = None,
) -> GlossaryCategory | None:
    guid = (atlas_guid or "").strip()
    if not guid:
        return None

    existing = db.query(GlossaryCategory).filter(GlossaryCategory.atlas_guid == guid).first()
    if existing:
        return existing

    atlas_category = _get_atlas_category_by_guid(guid) or {}
    qualified_name = (atlas_category.get("qualifiedName") or "").strip() or None
    name = (atlas_category.get("name") or atlas_category.get("displayText") or fallback_name or "").strip() or None

    if qualified_name:
        by_qn = db.query(GlossaryCategory).filter(GlossaryCategory.qualified_name == qualified_name).first()
        if by_qn:
            if not by_qn.atlas_guid:
                by_qn.atlas_guid = guid
                db.commit()
                db.refresh(by_qn)
            return by_qn

    if not qualified_name:
        # DB constraint: qualified_name is required and unique.
        qualified_name = f"{guid}@{glossary.qualified_name}"

    category = GlossaryCategory(
        glossary_id=glossary.id,
        name=name or qualified_name,
        qualified_name=qualified_name,
        description=(atlas_category.get("shortDescription") or atlas_category.get("longDescription") or None),
        atlas_guid=guid,
        created_by=None,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def _ensure_atlas_terms_in_db(db: Session, term_guids: set[str]) -> dict[str, int]:
    """
    Ensure GlossaryTerm rows exist for the given Atlas term GUIDs.
    Returns a mapping atlas_guid -> glossary_terms.id
    """
    cleaned = {str(g).strip() for g in (term_guids or set()) if str(g).strip()}
    if not cleaned:
        return {}

    existing_terms = (
        db.query(GlossaryTerm)
        .filter(GlossaryTerm.atlas_guid.in_(list(cleaned)))
        .all()
    )
    term_id_by_guid: dict[str, int] = {}
    for term in existing_terms:
        if term.atlas_guid:
            term_id_by_guid[str(term.atlas_guid)] = int(term.id)

    missing = sorted(cleaned - set(term_id_by_guid.keys()))
    if not missing:
        return term_id_by_guid

    for guid in missing:
        atlas_term = _get_atlas_term_by_guid(guid) or {}
        term_name = (atlas_term.get("name") or atlas_term.get("displayText") or "").strip() or guid
        qualified_name = (atlas_term.get("qualifiedName") or "").strip() or None

        # Try to resolve the DB glossary from the Atlas qualifiedName suffix: "<slug>@<glossaryQN>"
        glossary_qn = None
        if qualified_name and "@" in qualified_name:
            glossary_qn = qualified_name.rsplit("@", 1)[-1].strip() or None
        glossary_qn = glossary_qn or DEFAULT_GLOSSARY_QUALIFIED_NAME

        anchor = atlas_term.get("anchor") or {}
        glossary_display = (anchor.get("displayText") or "").strip() or None
        glossary = _get_or_create_db_glossary(db, glossary_qn, display_name=glossary_display)

        # Category (optional).
        categories = atlas_term.get("categories") or []
        category_guid = None
        category_fallback_name = None
        if isinstance(categories, list) and categories:
            first = categories[0] if isinstance(categories[0], dict) else {}
            category_guid = (first.get("categoryGuid") or first.get("guid") or "").strip() or None
            category_fallback_name = (first.get("displayText") or first.get("name") or "").strip() or None
        category = _get_or_create_db_category(db, glossary, category_guid or "", fallback_name=category_fallback_name)

        # If a term already exists by qualifiedName, reuse and backfill atlas_guid.
        existing_by_qn = None
        if qualified_name:
            existing_by_qn = db.query(GlossaryTerm).filter(GlossaryTerm.qualified_name == qualified_name).first()
        if existing_by_qn:
            if not existing_by_qn.atlas_guid:
                existing_by_qn.atlas_guid = guid
            if category and not existing_by_qn.category_id:
                existing_by_qn.category_id = category.id
            if not existing_by_qn.glossary_id:
                existing_by_qn.glossary_id = glossary.id
            db.commit()
            db.refresh(existing_by_qn)
            term_id_by_guid[guid] = int(existing_by_qn.id)
            continue

        # DB constraint: glossary_id required; qualified_name unique but nullable.
        term_row = GlossaryTerm(
            glossary_id=glossary.id,
            category_id=category.id if category else None,
            term=term_name,
            qualified_name=qualified_name,
            description=(atlas_term.get("shortDescription") or atlas_term.get("longDescription") or None),
            atlas_guid=guid,
            created_by=None,
        )
        db.add(term_row)
        db.commit()
        db.refresh(term_row)
        term_id_by_guid[guid] = int(term_row.id)

    return term_id_by_guid


def _assignment_data(assignment) -> Optional[AssignmentInfo]:
    if not assignment or not assignment.term:
        return None
    term = assignment.term
    glossary = getattr(term, "glossary", None)
    category = getattr(term, "category", None)
    return AssignmentInfo(
        term_id=assignment.glossary_term_id,
        term=term.term,
        glossary_id=term.glossary_id,
        glossary_name=glossary.name if glossary else None,
        category_id=term.category_id,
        category_name=category.name if category else None,
        assigned_by=assignment.created_by,
        assigned_at=assignment.created_at.isoformat() if assignment.created_at else None
    )

def _assignments_data(assignments: list) -> List[AssignmentInfo]:
    items = [_assignment_data(a) for a in (assignments or [])]
    cleaned = [a for a in items if a]
    cleaned.sort(key=lambda a: (a.term or "").lower())
    return cleaned


def _build_column_payload(name: str, description_map: dict, assignments_by_col: dict) -> ColumnMetadata:
    assignments = assignments_by_col.get(name) or []
    return ColumnMetadata(
        name=name,
        description=description_map.get(name),
        classification=_assignment_data(assignments[0]) if assignments else None,
        classifications=_assignments_data(assignments),
    )


def _get_latest_version(db: Session, dataset_id: str) -> Optional[DatasetVersion]:
    return db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id
    ).order_by(DatasetVersion.version_number.desc()).first()

def _get_latest_published_version(db: Session, dataset_id: str) -> Optional[DatasetVersion]:
    return db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id,
        DatasetVersion.atlas_guid.isnot(None)
    ).order_by(DatasetVersion.version_number.desc()).first()


def _get_or_create_metadata_version(db: Session, dataset: Dataset, user_id: str) -> DatasetVersion:
    """
    Metadata edits (descriptions / assignments) should attach to the latest published version
    when the dataset has already been pushed to Atlas.

    Only before the first push, we create a draft version (atlas_guid=NULL).
    """
    dataset_id = str(dataset.id)
    published = _get_latest_published_version(db, dataset_id)
    if published:
        return published

    # Backfill: dataset has an Atlas GUID but no published version exists (partial push / legacy state).
    if dataset.atlas_guid:
        draft = db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.atlas_guid.is_(None)
        ).order_by(DatasetVersion.version_number.desc()).first()
        if draft:
            draft.atlas_guid = dataset.atlas_guid
            if not draft.change_comment:
                draft.change_comment = "Backfill: published version (from datasets.atlas_guid)"
            else:
                draft.change_comment = f"{draft.change_comment} | Backfill: published version"
            db.commit()
            db.refresh(draft)
            return draft

    version = db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id,
        DatasetVersion.atlas_guid.is_(None)
    ).first()

    if version:
        return version

    last_version = _get_latest_version(db, dataset_id)
    next_number = (last_version.version_number + 1) if last_version else 1

    version = DatasetVersion(
        dataset_id=dataset_id,
        version_number=next_number,
        created_by=user_id,
        change_comment="Metadata update"
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def _get_assignments_map(assignments):
    result = {}
    for assignment in assignments:
        key = assignment.column_name or "__dataset__"
        result.setdefault(key, []).append(assignment)
    return result


def _dataset_visibility(dataset: Dataset) -> str:
    return dataset.classification or (dataset.project.visibility if dataset.project else "DEPARTMENT")



def _ensure_atlas_synced(dataset: Dataset):
    if not dataset.atlas_guid:
        raise HTTPException(status_code=403, detail="Dataset non synchronisé avec Atlas")
    if not getattr(dataset, "atlas_synced", False):
        raise HTTPException(status_code=403, detail="Ce dataset est en cours de synchronisation Atlas")


def _ensure_term_synced_to_atlas(db: Session, term: GlossaryTerm) -> None:
    """
    Ensures a glossary term has an Atlas GUID before attempting to assign it to entities.
    This is required because dataset/column metadata sync only assigns terms that already
    exist in Atlas.
    """
    if not term or term.atlas_guid:
        return
    glossary = getattr(term, "glossary", None)
    if not glossary:
        raise HTTPException(status_code=500, detail="Terme sans glossaire (données invalides)")
    try:
        sync_glossary_terms([glossary], db)
        db.refresh(term)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur synchronisation Atlas (glossaire/terme): {exc}")
    if not term.atlas_guid:
        raise HTTPException(status_code=500, detail="Terme non synchronisé dans Atlas (atlas_guid manquant)")


def _build_my_dataset_item(dataset: Dataset, user: dict, db: Session) -> MyDatasetListItem:
    assignments = get_assignments_for_dataset(db, str(dataset.id))
    assignment_map = _get_assignments_map(assignments)
    dataset_assignments = assignment_map.get("__dataset__") or []
    dataset_assignment = dataset_assignments[0] if dataset_assignments else None

    project_info = None
    if dataset.project:
        project_info = ProjectInfo(
            id=str(dataset.project.id),
            name=dataset.project.name,
            visibility=dataset.project.visibility
        )

    can_edit = can_modify_dataset(user, dataset, db) and bool(dataset.atlas_synced)
    return MyDatasetListItem(
        id=str(dataset.id),
        name=dataset.name,
        uploaded_by=dataset.owner_employee_id,
        project=project_info,
        description=dataset.description,
        classification=_dataset_visibility(dataset),
        columns=dataset.columns_list or [],
        columns_count=len(dataset.columns_list or []),
        created_at=dataset.created_at.isoformat() if dataset.created_at else None,
        dataset_assignment=_assignment_data(dataset_assignment),
        dataset_assignments=_assignments_data(dataset_assignments),
        atlas_guid=dataset.atlas_guid,
        atlas_synced=bool(dataset.atlas_synced),
        can_edit=can_edit
    )

@router.get("/api/datasets/{dataset_id}/metadata", response_model=DatasetMetadataResponse)
async def get_dataset_metadata(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    dataset = db.query(Dataset).options(joinedload(Dataset.project)).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    if not can_view_dataset(user, dataset, db):
        raise HTTPException(status_code=403, detail="Accès refusé")

    assignments = get_assignments_for_dataset(db, dataset_id)
    assignment_map = _get_assignments_map(assignments)
    dataset_assignments = assignment_map.get("__dataset__") or []
    dataset_assignment = dataset_assignments[0] if dataset_assignments else None

    latest_version = _get_latest_version(db, dataset_id)
    descriptions = get_description_dict_by_version(db, str(latest_version.id)) if latest_version else {}

    columns = []
    for column in dataset.columns_list or []:
        columns.append(_build_column_payload(column, descriptions, assignment_map))

    project_info = None
    if dataset.project:
        project_info = ProjectInfo(
            id=str(dataset.project.id),
            name=dataset.project.name,
            visibility=dataset.project.visibility
        )

    user_id = _get_employee_identifier(user)
    can_edit = can_modify_dataset(user, dataset, db)

    return DatasetMetadataResponse(
        id=str(dataset.id),
        name=dataset.name,
        file_name=dataset.name,
        hash=dataset.hash,
        project=project_info,
        uploaded_by=dataset.owner_employee_id,
        description=dataset.description,
        classification=_dataset_visibility(dataset),
        dataset_assignment=_assignment_data(dataset_assignment),
        dataset_assignments=_assignments_data(dataset_assignments),
        columns=columns,
        can_edit=can_edit
    )




@router.get("/api/datasets/my-uploads", response_model=list[MyDatasetListItem])
async def list_my_datasets(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    datasets = db.query(Dataset).options(joinedload(Dataset.project)).all()
    visible = []
    for dataset in datasets:
        if can_view_dataset(user, dataset, db):
            visible.append(_build_my_dataset_item(dataset, user, db))
    return visible


@router.get("/api/datasets/{dataset_id}/atlas-columns")
async def get_dataset_atlas_columns(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    if not can_view_dataset(user, dataset, db):
        raise HTTPException(status_code=403, detail="Accès refusé")

    # Some datasets (not yet pushed) won't have Atlas info; return empty mapping for the UI.
    if not dataset.atlas_guid:
        return {"columns": {}}

    qualified = (getattr(dataset, "atlas_qualified_name", None) or "").strip() or None
    columns = get_existing_columns(dataset.atlas_guid, qualified)
    return {"columns": columns}


@router.get("/api/datasets/{dataset_id}/atlas-term-assignments")
async def get_dataset_atlas_term_assignments(
    dataset_id: str,
    include_columns: bool = True,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Returns Atlas glossary term assignments for the dataset entity and (optionally) its columns.

    Output uses local DB term ids (glossary_terms.id) so the frontend can pre-select terms
    even when assignments were made directly in Atlas.
    """
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    if not can_view_dataset(user, dataset, db):
        raise HTTPException(status_code=403, detail="Accès refusé")

    if not dataset.atlas_guid:
        return {"dataset_term_ids": [], "columns": {}}

    dataset_term_guids = get_entity_assigned_term_guids(dataset.atlas_guid)
    all_term_guids = set(dataset_term_guids)

    qualified = (getattr(dataset, "atlas_qualified_name", None) or "").strip() or None
    atlas_columns = get_existing_columns(dataset.atlas_guid, qualified) if include_columns else {}

    column_guid_by_name: dict[str, str] = {}
    if include_columns and atlas_columns:
        for name, info in atlas_columns.items():
            guid = (info or {}).get("guid")
            if guid:
                column_guid_by_name[str(name)] = str(guid)

    column_term_guids: dict[str, list[str]] = {}
    if include_columns and column_guid_by_name:
        for col_name, guid in column_guid_by_name.items():
            guids = get_entity_assigned_term_guids(guid) or []
            if guids:
                column_term_guids[col_name] = guids
                all_term_guids.update(guids)

    term_id_by_guid: dict[str, int] = _ensure_atlas_terms_in_db(db, set(all_term_guids or []))

    dataset_term_ids = sorted(
        {term_id_by_guid[g] for g in dataset_term_guids if g in term_id_by_guid}
    )

    columns: dict[str, list[int]] = {}
    for col_name, guids in column_term_guids.items():
        ids = sorted({term_id_by_guid[g] for g in guids if g in term_id_by_guid})
        if ids:
            columns[col_name] = ids

    # Provide term payloads so the frontend can show Atlas-only assignments
    # even when /glossary/terms was loaded before those terms were discovered.
    payload_terms = []
    if term_id_by_guid:
        used_ids = sorted({int(v) for v in term_id_by_guid.values()})
        rows = (
            db.query(GlossaryTerm)
            .options(joinedload(GlossaryTerm.category))
            .filter(GlossaryTerm.id.in_(used_ids))
            .all()
        )
        for t in rows:
            payload_terms.append({
                "id": int(t.id),
                "term": t.term,
                "category_name": t.category.name if t.category else None,
            })

    return {"dataset_term_ids": dataset_term_ids, "columns": columns, "terms": payload_terms}

@router.put("/api/datasets/{dataset_id}/columns/{column_name}")
async def update_column_metadata(
    dataset_id: str,
    column_name: str,
    payload: ColumnUpdatePayload,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    if not can_modify_dataset(user, dataset, db):
        raise HTTPException(status_code=403, detail="Droits insuffisants")

    _ensure_atlas_synced(dataset)

    previous_synced = bool(getattr(dataset, "atlas_synced", False))
    dataset.atlas_synced = False
    db.commit()

    try:
        if column_name not in (dataset.columns_list or []):
            raise HTTPException(status_code=404, detail="Colonne introuvable")

        user_id = _get_employee_identifier(user) or ""
        version = _get_or_create_metadata_version(db, dataset, user_id)

        if payload.description is not None and payload.description.strip():
            create_or_update_description(
                db,
                dataset_version_id=str(version.id),
                column_name=column_name,
                description=payload.description.strip(),
                user_id=user_id
            )

        fields_set = getattr(payload, "__fields_set__", None) or getattr(payload, "model_fields_set", None) or set()
        term_set_requested = False
        desired_ids: List[int] = []
        if "glossary_term_ids" in fields_set:
            term_set_requested = True
            desired_ids = list(payload.glossary_term_ids or [])
        elif "glossary_term_id" in fields_set:
            term_set_requested = True
            desired_ids = [] if payload.glossary_term_id is None else [payload.glossary_term_id]

        force_remove_column_term_guids: dict[str, list[str]] = {}
        if term_set_requested:
            # Validate and ensure all terms are synced to Atlas.
            existing_assignments = [
                a for a in get_assignments_for_dataset(db, dataset_id)
                if (a.column_name or None) == column_name
            ]
            existing_ids = {int(a.glossary_term_id) for a in existing_assignments}

            unique_ids = sorted({int(x) for x in desired_ids if x is not None})
            for term_id in unique_ids:
                term = db.query(GlossaryTerm).filter(GlossaryTerm.id == term_id).first()
                if not term:
                    raise HTTPException(status_code=404, detail="Terme introuvable")
                _ensure_term_synced_to_atlas(db, term)

            set_assignments_for_column(
                db,
                dataset_id,
                column_name,
                unique_ids,
                user_id,
            )

            removed_ids = sorted(existing_ids - set(unique_ids))
            if removed_ids:
                removed_guids: list[str] = []
                for term_id in removed_ids:
                    term = db.query(GlossaryTerm).filter(GlossaryTerm.id == term_id).first()
                    if term and getattr(term, "atlas_guid", None):
                        removed_guids.append(str(term.atlas_guid))
                if removed_guids:
                    force_remove_column_term_guids[column_name] = removed_guids

        assignments = get_assignments_for_dataset(db, dataset_id)
        assignment_map = _get_assignments_map(assignments)
        descriptions = get_description_dict_by_version(db, str(version.id))

        column_to_sync = {column_name: descriptions.get(column_name)}
        sync_dataset_metadata_to_atlas(
            db,
            dataset,
            column_descriptions=column_to_sync,
            columns_to_align_terms=[column_name],
            force_remove_column_term_guids=force_remove_column_term_guids or None,
        )

        dataset.atlas_synced = True
        db.commit()
        return _build_column_payload(column_name, descriptions, assignment_map)
    except HTTPException:
        dataset.atlas_synced = previous_synced
        db.commit()
        raise
    except Exception as exc:
        dataset.atlas_synced = previous_synced
        db.commit()
        raise HTTPException(status_code=500, detail=f"Erreur synchronisation Atlas: {exc}")


@router.put("/api/datasets/{dataset_id}/classification")
async def update_dataset_classification(
    dataset_id: str,
    payload: DatasetClassificationPayload,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    if not can_modify_dataset(user, dataset, db):
        raise HTTPException(status_code=403, detail="Droits insuffisants")

    _ensure_atlas_synced(dataset)

    previous_synced = bool(getattr(dataset, "atlas_synced", False))
    dataset.atlas_synced = False
    db.commit()

    user_id = _get_employee_identifier(user) or ""
    try:
        fields_set = getattr(payload, "__fields_set__", None) or getattr(payload, "model_fields_set", None) or set()
        if (
            "glossary_term_ids" not in fields_set
            and "glossary_term_id" not in fields_set
        ):
            raise HTTPException(status_code=400, detail="Aucun terme fourni")

        desired_ids: List[int] = []
        if "glossary_term_ids" in fields_set:
            desired_ids = list(payload.glossary_term_ids or [])
        elif "glossary_term_id" in fields_set:
            desired_ids = [] if payload.glossary_term_id is None else [payload.glossary_term_id]

        existing_assignments = [
            a for a in get_assignments_for_dataset(db, dataset_id)
            if (a.column_name or None) is None
        ]
        existing_ids = {int(a.glossary_term_id) for a in existing_assignments}

        unique_ids = sorted({int(x) for x in desired_ids if x is not None})
        for term_id in unique_ids:
            term = db.query(GlossaryTerm).filter(GlossaryTerm.id == term_id).first()
            if not term:
                raise HTTPException(status_code=404, detail="Terme introuvable")
            _ensure_term_synced_to_atlas(db, term)

        assignments = set_assignments_for_column(
            db,
            dataset_id,
            None,
            unique_ids,
            user_id,
        )

        removed_ids = sorted(existing_ids - set(unique_ids))
        removed_guids: list[str] = []
        for term_id in removed_ids:
            term = db.query(GlossaryTerm).filter(GlossaryTerm.id == term_id).first()
            if term and getattr(term, "atlas_guid", None):
                removed_guids.append(str(term.atlas_guid))

        sync_dataset_metadata_to_atlas(
            db,
            dataset,
            force_remove_dataset_term_guids=removed_guids or None,
        )
        dataset.atlas_synced = True
        db.commit()
        return {
            "dataset_assignment": _assignment_data(assignments[0]) if assignments else None,
            "dataset_assignments": _assignments_data(assignments),
        }
    except HTTPException:
        dataset.atlas_synced = previous_synced
        db.commit()
        raise
    except Exception as exc:
        dataset.atlas_synced = previous_synced
        db.commit()
        raise HTTPException(status_code=500, detail=f"Erreur synchronisation Atlas: {exc}")


@router.put("/api/datasets/{dataset_id}/description")
async def update_dataset_description(
    dataset_id: str,
    payload: DatasetDescriptionPayload,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    if not can_modify_dataset(user, dataset, db):
        raise HTTPException(status_code=403, detail="Droits insuffisants")

    _ensure_atlas_synced(dataset)

    previous_synced = bool(getattr(dataset, "atlas_synced", False))
    dataset.atlas_synced = False
    db.commit()

    dataset.description = (payload.description or "").strip() or None

    try:
        # This sync updates dataset description in Atlas and realigns glossary term assignments too.
        sync_dataset_metadata_to_atlas(db, dataset)
    except Exception as exc:
        dataset.atlas_synced = previous_synced
        db.commit()
        raise HTTPException(status_code=500, detail=f"Erreur synchronisation Atlas: {exc}")

    dataset.atlas_synced = True
    db.commit()

    return {"description": dataset.description}
