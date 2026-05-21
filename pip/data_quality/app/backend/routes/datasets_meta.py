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
from db.glossary import GlossaryTerm
from jwt_dependencies import get_current_user
from core.permissions import (
    can_view_dataset,
    can_modify_dataset,
    _get_employee_identifier
)
from atlas.glossary import sync_glossary_terms
from atlas.metadata import sync_dataset_metadata_to_atlas
from atlas.columns import get_existing_columns
import logging
router = APIRouter()
logger = logging.getLogger(__name__)


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

    can_edit = can_modify_dataset(user, dataset, db)
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

    atlas_ready = bool(getattr(dataset, "atlas_guid", None)) and bool(getattr(dataset, "atlas_synced", False))
    previous_synced = bool(getattr(dataset, "atlas_synced", False))
    if atlas_ready:
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

        if term_set_requested:
            unique_ids = sorted({int(x) for x in desired_ids if x is not None})
            for term_id in unique_ids:
                term = db.query(GlossaryTerm).filter(GlossaryTerm.id == term_id).first()
                if not term:
                    raise HTTPException(status_code=404, detail="Terme introuvable")
                if atlas_ready:
                    _ensure_term_synced_to_atlas(db, term)

            set_assignments_for_column(
                db,
                dataset_id,
                column_name,
                unique_ids,
                user_id,
            )

        assignments = get_assignments_for_dataset(db, dataset_id)
        assignment_map = _get_assignments_map(assignments)
        descriptions = get_description_dict_by_version(db, str(version.id))

        atlas_error = None
        if atlas_ready:
            try:
                column_to_sync = {column_name: descriptions.get(column_name)}
                sync_dataset_metadata_to_atlas(
                    db,
                    dataset,
                    column_descriptions=column_to_sync,
                    columns_to_align_terms=[column_name],
                )
                dataset.atlas_synced = True
                db.commit()
            except Exception as exc:
                atlas_error = str(exc)
                logger.warning(
                    "Atlas sync failed for dataset_id=%s column=%s: %s",
                    dataset_id,
                    column_name,
                    atlas_error,
                )
                # Keep atlas_synced=False so UI can show "à synchroniser" and avoid further edits if desired.
                dataset.atlas_synced = False
                db.commit()

        payload = _build_column_payload(column_name, descriptions, assignment_map)
        # Non-breaking additional metadata for clients wanting to surface Atlas sync issues.
        return {
            **payload.model_dump(),
            "pending_atlas_sync": bool(atlas_error) or (not atlas_ready),
            "atlas_error": atlas_error,
        }
    except HTTPException:
        if atlas_ready:
            dataset.atlas_synced = previous_synced
            db.commit()
        raise
    except Exception as exc:
        if atlas_ready:
            dataset.atlas_synced = previous_synced
            db.commit()
        raise HTTPException(status_code=500, detail=f"Erreur interne: {exc}")


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

    atlas_ready = bool(getattr(dataset, "atlas_guid", None)) and bool(getattr(dataset, "atlas_synced", False))
    previous_synced = bool(getattr(dataset, "atlas_synced", False))
    if atlas_ready:
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

        unique_ids = sorted({int(x) for x in desired_ids if x is not None})
        for term_id in unique_ids:
            term = db.query(GlossaryTerm).filter(GlossaryTerm.id == term_id).first()
            if not term:
                raise HTTPException(status_code=404, detail="Terme introuvable")
            if atlas_ready:
                _ensure_term_synced_to_atlas(db, term)

        assignments = set_assignments_for_column(
            db,
            dataset_id,
            None,
            unique_ids,
            user_id,
        )

        atlas_error = None
        if atlas_ready:
            try:
                sync_dataset_metadata_to_atlas(db, dataset)
                dataset.atlas_synced = True
                db.commit()
            except Exception as exc:
                atlas_error = str(exc)
                logger.warning(
                    "Atlas sync failed for dataset_id=%s (classification update): %s",
                    dataset_id,
                    atlas_error,
                )
                dataset.atlas_synced = False
                db.commit()
        return {
            "dataset_assignment": _assignment_data(assignments[0]) if assignments else None,
            "dataset_assignments": _assignments_data(assignments),
            "pending_atlas_sync": bool(atlas_error) or (not atlas_ready),
            "atlas_error": atlas_error,
        }
    except HTTPException:
        if atlas_ready:
            dataset.atlas_synced = previous_synced
            db.commit()
        raise
    except Exception as exc:
        if atlas_ready:
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

    dataset.description = (payload.description or "").strip() or None
    db.commit()
    db.refresh(dataset)

    atlas_ready = bool(getattr(dataset, "atlas_guid", None)) and bool(getattr(dataset, "atlas_synced", False))
    previous_synced = bool(getattr(dataset, "atlas_synced", False))
    atlas_error = None

    try:
        if atlas_ready:
            dataset.atlas_synced = False
            db.commit()
            # This sync updates dataset description in Atlas and realigns glossary term assignments too.
            sync_dataset_metadata_to_atlas(db, dataset)
            dataset.atlas_synced = True
            db.commit()
    except Exception as exc:
        atlas_error = str(exc)
        dataset.atlas_synced = previous_synced
        db.commit()
        raise HTTPException(status_code=500, detail=f"Erreur synchronisation Atlas: {exc}")

    return {
        "description": dataset.description,
        "pending_atlas_sync": not atlas_ready,
        "atlas_error": atlas_error,
    }
