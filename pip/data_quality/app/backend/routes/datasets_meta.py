from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List, Optional

from db.connexion_db import get_db
from db.datasets import Dataset
from db.dataset_glossary_crud import (
    get_assignments_for_dataset,
    set_assignment_for_column
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
from atlas.metadata import sync_dataset_metadata_to_atlas
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
    atlas_guid: str | None = None
    atlas_synced: bool
    can_edit: bool


class ColumnUpdatePayload(BaseModel):
    description: str | None = None
    glossary_term_id: int | None = None


class DatasetClassificationPayload(BaseModel):
    glossary_term_id: int | None = None

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


def _build_column_payload(name: str, description_map: dict, assignments: dict) -> ColumnMetadata:
    assignment = assignments.get(name)
    return ColumnMetadata(
        name=name,
        description=description_map.get(name),
        classification=_assignment_data(assignment)
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
        result[key] = assignment
    return result


def _dataset_visibility(dataset: Dataset) -> str:
    return dataset.classification or (dataset.project.visibility if dataset.project else "DEPARTMENT")



def _ensure_atlas_synced(dataset: Dataset):
    if not dataset.atlas_guid:
        raise HTTPException(status_code=403, detail="Dataset non synchronisé avec Atlas")
    if not getattr(dataset, "atlas_synced", False):
        raise HTTPException(status_code=403, detail="Ce dataset est en cours de synchronisation Atlas")


def _build_my_dataset_item(dataset: Dataset, user: dict, db: Session) -> MyDatasetListItem:
    assignments = get_assignments_for_dataset(db, str(dataset.id))
    assignment_map = _get_assignments_map(assignments)
    dataset_assignment = assignment_map.get("__dataset__")

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
    dataset_assignment = assignment_map.get("__dataset__")

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
    previous_synced = bool(getattr(dataset, "atlas_synced", False))
    dataset.atlas_synced = False
    db.commit()

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

    assignments = get_assignments_for_dataset(db, dataset_id)
    current_assignment = next(
        (a for a in assignments if a.column_name == column_name),
        None
    )

    if payload.glossary_term_id is not None and payload.glossary_term_id != (current_assignment.glossary_term_id if current_assignment else None):
        term = db.query(GlossaryTerm).filter(GlossaryTerm.id == payload.glossary_term_id).first()
        if not term:
            raise HTTPException(status_code=404, detail="Terme introuvable")
        set_assignment_for_column(
            db,
            dataset_id,
            column_name,
            payload.glossary_term_id,
            user_id
        )
    elif payload.glossary_term_id is None and current_assignment:
        set_assignment_for_column(
            db,
            dataset_id,
            column_name,
            None,
            user_id
        )

    assignments = get_assignments_for_dataset(db, dataset_id)
    assignment_map = _get_assignments_map(assignments)
    descriptions = get_description_dict_by_version(db, str(version.id))

    column_to_sync = {column_name: descriptions.get(column_name)}
    try:
        sync_dataset_metadata_to_atlas(db, dataset, column_descriptions=column_to_sync)
    except Exception as exc:
        dataset.atlas_synced = previous_synced
        db.commit()
        raise HTTPException(status_code=500, detail=f"Erreur synchronisation Atlas: {exc}")

    dataset.atlas_synced = True
    db.commit()

    return _build_column_payload(column_name, descriptions, assignment_map)


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
    if payload.glossary_term_id is not None:
        term = db.query(GlossaryTerm).filter(GlossaryTerm.id == payload.glossary_term_id).first()
        if not term:
            raise HTTPException(status_code=404, detail="Terme introuvable")

    assignment = set_assignment_for_column(
        db,
        dataset_id,
        None,
        payload.glossary_term_id,
        user_id
    )

    try:
        sync_dataset_metadata_to_atlas(db, dataset)
    except Exception as exc:
        dataset.atlas_synced = previous_synced
        db.commit()
        raise HTTPException(status_code=500, detail=f"Erreur synchronisation Atlas: {exc}")

    dataset.atlas_synced = True
    db.commit()

    return _assignment_data(assignment)


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
