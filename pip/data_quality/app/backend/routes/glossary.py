import re

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from atlas.glossary import sync_glossary_terms

logger = logging.getLogger("routes.glossary")

from db.connexion_db import get_db
from db.departments import Department
from db.user_department_scopes import UserDepartmentScope
from db.datasets import Dataset
from db.glossary import GlossaryCategory
from db.glossary import Glossary, GlossaryTerm
from db.glossary_crud import (
    get_all_terms,
    get_term_by_id,
    create_term,
    update_term,
    delete_term,
    get_all_glossaries,
    get_glossary_by_id,
    create_glossary,
    update_glossary,
    delete_glossary,
    get_all_categories,
    create_category,
    update_category,
    delete_category,
    get_category_by_id
)
from db.dataset_glossary_crud import (
    get_assignments_for_dataset,
    assign_term_to_dataset,
    remove_assignment
)
from jwt_dependencies import get_current_user
from core.permissions import require_role
from core.roles import ADMIN, ADMIN_GLOSSAIRE, DATA_OWNER

router = APIRouter(tags=["glossary"])
GLOSSARY_MANAGERS = [ADMIN, ADMIN_GLOSSAIRE]
GLOSSARY_ASSIGNERS = [ADMIN, ADMIN_GLOSSAIRE, DATA_OWNER]


from pydantic import BaseModel


class GlossaryResponse(BaseModel):
    id: int
    name: str
    qualified_name: str
    description: str | None
    department: str | None
    created_by: str | None
    created_at: str | None


class GlossaryCreate(BaseModel):
    name: str
    qualified_name: str
    description: str | None = None
    department: str


class GlossaryUpdate(BaseModel):
    name: str | None = None
    qualified_name: str | None = None
    description: str | None = None
    department: str | None = None


class CategoryResponse(BaseModel):
    id: int
    glossary_id: int
    name: str
    description: str | None
    created_by: str | None
    created_at: str | None


class CategoryCreate(BaseModel):
    glossary_id: int
    name: str
    description: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class TermResponse(BaseModel):
    id: int
    glossary_id: int
    term: str
    description: str | None
    category_id: int | None
    category_name: str | None
    created_by: str | None
    created_at: str | None


class TermCreate(BaseModel):
    glossary_id: int
    category_id: int
    term: str
    description: str | None = None


class TermUpdate(BaseModel):
    glossary_id: int | None = None
    term: str | None = None
    description: str | None = None
    category_id: int | None = None


def _slugify(text: str, default: str = "item") -> str:
    candidate = re.sub(r"[^\w]+", "_", (text or "").lower())
    candidate = re.sub(r"_+", "_", candidate).strip("_")
    return candidate or default


def _normalize_department(value: str) -> str:
    return re.sub(r"\s+", "_", (value or "").strip()).upper()


def _assert_glossary_department_allowed(db: Session, dept_code: str, user: dict) -> str:
    dept_code = _normalize_department(dept_code)
    if not dept_code:
        raise HTTPException(status_code=400, detail="Département obligatoire")

    dept = db.query(Department).filter(Department.code == dept_code, Department.is_active == True).first()
    if not dept:
        raise HTTPException(status_code=400, detail="Département inconnu ou inactif")

    role = user.get("role")
    if role == ADMIN_GLOSSAIRE:
        emp_id = user.get("employee_id") or user.get("sub")
        allowed = (
            db.query(UserDepartmentScope)
            .filter(UserDepartmentScope.employee_id == emp_id, UserDepartmentScope.department_code == dept_code)
            .first()
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="Vous n'êtes pas autorisé à gérer ce département")

    return dept_code


def _sync_one_glossary(db: Session, glossary: Glossary) -> None:
    """
    Ensures the glossary/categories/terms exist in Atlas and backfills atlas_guid on terms/categories.

    Note: this does not try to "rename" existing Atlas objects. We keep stable qualified_names and
    treat Atlas as the controlled target.
    """
    try:
        sync_glossary_terms([glossary], db)
    except Exception as exc:
        logger.warning(f"Synchronisation Atlas glossaire échouée (non bloquant): {exc}")


class DatasetAssignmentCreate(BaseModel):
    term_id: int
    column_name: str | None = None


class DatasetListItem(BaseModel):
    id: str
    name: str


class DatasetAssignmentResponse(BaseModel):
    id: int
    dataset_id: str
    glossary_term_id: int
    term: str
    glossary_name: str | None
    category_id: int | None
    category_name: str | None
    created_by: str | None
    column_name: str | None

@router.get("/glossary/glossaries", response_model=List[GlossaryResponse])
def get_glossaries(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    glossaries = get_all_glossaries(db)
    return [
        {
            "id": glossary.id,
            "name": glossary.name,
            "qualified_name": glossary.qualified_name,
            "description": glossary.description,
            "department": glossary.department,
            "created_by": glossary.created_by,
            "created_at": glossary.created_at.isoformat() if glossary.created_at else None
        }
        for glossary in glossaries
    ]


@router.get("/glossary/categories", response_model=List[CategoryResponse])
def list_categories(
    glossary_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    categories = get_all_categories(db, glossary_id)
    return [
        {
            "id": category.id,
            "glossary_id": category.glossary_id,
            "name": category.name,
            "description": category.description,
            "created_by": category.created_by,
            "created_at": category.created_at.isoformat() if category.created_at else None
        }
        for category in categories
    ]


@router.post("/glossary/categories", response_model=CategoryResponse)
def create_category_route(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(GLOSSARY_MANAGERS))
):
    glossary = get_glossary_by_id(db, payload.glossary_id)
    if not glossary:
        raise HTTPException(status_code=404, detail="Glossaire non trouvé")

    qualified_name = f"{_slugify(payload.name, 'category')}@{glossary.qualified_name}"
    existing = db.query(GlossaryCategory).filter(
        GlossaryCategory.qualified_name == qualified_name
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Cette catégorie existe déjà")

    category = create_category(
        db=db,
        glossary_id=payload.glossary_id,
        name=payload.name,
        qualified_name=qualified_name,
        description=payload.description,
        created_by=user.get("employee_id")
    )

    # Keep Atlas in-sync as soon as taxonomy changes.
    glossary = get_glossary_by_id(db, payload.glossary_id)
    if glossary:
        _sync_one_glossary(db, glossary)

    return {
        "id": category.id,
        "glossary_id": category.glossary_id,
        "name": category.name,
        "description": category.description,
        "created_by": category.created_by,
        "created_at": category.created_at.isoformat() if category.created_at else None
    }


@router.put("/glossary/categories/{category_id}", response_model=CategoryResponse)
def update_category_route(
    category_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(GLOSSARY_MANAGERS))
):
    category = get_category_by_id(db, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Catégorie non trouvée")

    updated = update_category(
        db=db,
        category_id=category_id,
        name=payload.name,
        description=payload.description,
        # Keep qualified_name stable on rename: changing it would create duplicates in Atlas sync
        # and break stable references. Only creation sets qualified_name.
        qualified_name=None
    )

    glossary = get_glossary_by_id(db, updated.glossary_id)
    if glossary:
        _sync_one_glossary(db, glossary)

    return {
        "id": updated.id,
        "glossary_id": updated.glossary_id,
        "name": updated.name,
        "description": updated.description,
        "created_by": updated.created_by,
        "created_at": updated.created_at.isoformat() if updated.created_at else None
    }


@router.delete("/glossary/categories/{category_id}")
def delete_category_route(
    category_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(GLOSSARY_MANAGERS))
):
    if not delete_category(db, category_id):
        raise HTTPException(status_code=404, detail="Catégorie non trouvée")
    return {"message": "Catégorie supprimée"}


@router.post("/glossary/glossaries", response_model=GlossaryResponse)
def create_glossary_route(
    payload: GlossaryCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(GLOSSARY_MANAGERS))
):
    dept_code = _assert_glossary_department_allowed(db, payload.department, user)
    existing = db.query(Glossary).filter(Glossary.qualified_name == payload.qualified_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ce glossaire existe déjà")

    glossary = create_glossary(
        db=db,
        name=payload.name,
        qualified_name=payload.qualified_name,
        description=payload.description,
        department=dept_code,
        created_by=user.get("employee_id")
    )

    _sync_one_glossary(db, glossary)

    return {
        "id": glossary.id,
        "name": glossary.name,
        "qualified_name": glossary.qualified_name,
        "description": glossary.description,
        "department": glossary.department,
        "created_by": glossary.created_by,
        "created_at": glossary.created_at.isoformat() if glossary.created_at else None
    }


@router.put("/glossary/glossaries/{glossary_id}", response_model=GlossaryResponse)
def update_glossary_route(
    glossary_id: int,
    payload: GlossaryUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(GLOSSARY_MANAGERS))
):
    glossary = get_glossary_by_id(db, glossary_id)
    if not glossary:
        raise HTTPException(status_code=404, detail="Glossaire non trouvé")

    dept_value = payload.department if payload.department is not None else glossary.department
    if dept_value is None:
        raise HTTPException(status_code=400, detail="Département obligatoire")
    dept_code = _assert_glossary_department_allowed(db, dept_value, user)

    updated = update_glossary(
        db=db,
        glossary_id=glossary_id,
        name=payload.name,
        qualified_name=payload.qualified_name,
        description=payload.description,
        department=dept_code
    )

    if updated:
        _sync_one_glossary(db, updated)

    return {
        "id": updated.id,
        "name": updated.name,
        "qualified_name": updated.qualified_name,
        "description": updated.description,
        "department": updated.department,
        "created_by": updated.created_by,
        "created_at": updated.created_at.isoformat() if updated.created_at else None
    }


@router.delete("/glossary/glossaries/{glossary_id}")
def delete_glossary_route(
    glossary_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(GLOSSARY_MANAGERS))
):
    glossary = get_glossary_by_id(db, glossary_id)
    if not glossary:
        raise HTTPException(status_code=404, detail="Glossaire non trouvé")

    delete_glossary(db, glossary_id)
    return {"message": "Glossaire supprimé avec succès"}


@router.get("/glossary/datasets", response_model=List[DatasetListItem])
def list_datasets_for_glossary(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    datasets = db.query(Dataset).all()
    return [{"id": ds.id, "name": ds.name} for ds in datasets]


@router.get("/glossary/datasets/{dataset_id}/terms", response_model=List[DatasetAssignmentResponse])
def get_dataset_glossary_terms(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    assignments = get_assignments_for_dataset(db, dataset_id)
    result = []
    for assignment in assignments:
        term = assignment.term
        if not term:
            continue
        glossary = term.glossary
        result.append({
            "id": assignment.id,
            "dataset_id": dataset_id,
            "glossary_term_id": term.id,
            "term": term.term,
            "glossary_name": glossary.name if glossary else None,
            "category_id": term.category.id if term.category else None,
            "category_name": term.category.name if term.category else None,
            "created_by": assignment.created_by,
            "column_name": assignment.column_name
        })
    return result


@router.post("/glossary/datasets/{dataset_id}/terms", response_model=DatasetAssignmentResponse)
def assign_term_to_dataset_route(
    dataset_id: str,
    payload: DatasetAssignmentCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(GLOSSARY_ASSIGNERS))
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")

    term = get_term_by_id(db, payload.term_id)
    if not term:
        raise HTTPException(status_code=404, detail="Terme introuvable")

    assigned = assign_term_to_dataset(
        db=db,
        dataset_id=dataset_id,
        glossary_term_id=payload.term_id,
        created_by=user.get("employee_id"),
        column_name=payload.column_name
    )
    glossary = term.glossary

    if not term.atlas_guid:
        try:
            sync_glossary_terms([term.glossary], db)
            db.refresh(term)
        except Exception as exc:
            logger.warning(f"Erreur synchronisation terme lors de l'assignation : {exc}")

    return {
        "id": assigned.id,
        "dataset_id": dataset_id,
        "glossary_term_id": term.id,
        "term": term.term,
        "glossary_name": glossary.name if glossary else None,
        "category_id": term.category.id if term.category else None,
        "category_name": term.category.name if term.category else None,
        "created_by": assigned.created_by,
        "column_name": assigned.column_name
    }


@router.delete("/glossary/datasets/{dataset_id}/terms/{term_id}")
def remove_dataset_term_assignment(
    dataset_id: str,
    term_id: int,
    column_name: str | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_role(GLOSSARY_ASSIGNERS))
):
    success = remove_assignment(db, dataset_id, term_id, column_name=column_name)
    if not success:
        raise HTTPException(status_code=404, detail="Attribution introuvable")
    return {"message": "Terme détaché du dataset"}


@router.get("/glossary/terms", response_model=List[TermResponse])
def get_terms(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    terms = get_all_terms(db)
    result = []
    for term in terms:
        result.append({
            "glossary_id": term.glossary_id,
            "id": term.id,
            "term": term.term,
            "description": term.description,
            "category_id": term.category_id,
            "category_name": term.category.name if term.category else None,
            "created_by": term.created_by,
            "created_at": term.created_at.isoformat() if term.created_at else None
        })
    return result


@router.post("/glossary/terms", response_model=TermResponse)
def create_term_route(
    payload: TermCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(GLOSSARY_MANAGERS))
):
    glossary = get_glossary_by_id(db, payload.glossary_id)
    if not glossary:
        raise HTTPException(status_code=404, detail="Glossaire non trouvé")

    category = get_category_by_id(db, payload.category_id)
    if not category or category.glossary_id != payload.glossary_id:
        raise HTTPException(status_code=400, detail="Catégorie invalide pour ce glossaire")

    existing = db.query(GlossaryTerm).filter(
        GlossaryTerm.term == payload.term,
        GlossaryTerm.glossary_id == payload.glossary_id,
        GlossaryTerm.category_id == payload.category_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ce terme existe déjà")
    
    new_term = create_term(
        db=db,
        glossary_id=payload.glossary_id,
        category_id=payload.category_id,
        term=payload.term,
        description=payload.description,
        created_by=user.get("employee_id")
    )

    glossary = get_glossary_by_id(db, payload.glossary_id)
    if glossary:
        _sync_one_glossary(db, glossary)
    
    return {
        "glossary_id": new_term.glossary_id,
        "id": new_term.id,
        "term": new_term.term,
        "description": new_term.description,
        "category_id": new_term.category_id,
        "category_name": new_term.category.name if new_term.category else None,
        "created_by": new_term.created_by,
        "created_at": new_term.created_at.isoformat() if new_term.created_at else None
    }


@router.put("/glossary/terms/{term_id}", response_model=TermResponse)
def update_term_route(
    term_id: int,
    payload: TermUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(GLOSSARY_MANAGERS))
):
    term = get_term_by_id(db, term_id)
    if not term:
        raise HTTPException(status_code=404, detail="Terme non trouvé")

    # Ensure a synced term has a stable qualified_name before allowing rename.
    # Without this, the Atlas sync would derive a new qualifiedName from the new label and create duplicates.
    if (
        term.atlas_guid
        and payload.term is not None
        and payload.term != term.term
        and not getattr(term, "qualified_name", None)
    ):
        glossary = get_glossary_by_id(db, term.glossary_id)
        if not glossary or not glossary.qualified_name:
            raise HTTPException(status_code=500, detail="Glossaire introuvable pour ce terme")
        term.qualified_name = f"{_slugify(term.term, 'term')}@{glossary.qualified_name}"
        db.commit()

    # Moving a term to another glossary after it has been synced to Atlas would change its anchor and
    # qualifiedName namespace. Keep it stable.
    if payload.glossary_id is not None and payload.glossary_id != term.glossary_id and term.atlas_guid:
        raise HTTPException(status_code=400, detail="Déplacement du terme vers un autre glossaire interdit après synchronisation Atlas")

    if payload.category_id:
        category = get_category_by_id(db, payload.category_id)
        if not category:
            raise HTTPException(status_code=400, detail="Catégorie introuvable")
        if payload.glossary_id and category.glossary_id != payload.glossary_id:
            raise HTTPException(status_code=400, detail="Catégorie incompatible avec le glossaire")

    updated = update_term(
        db=db,
        term_id=term_id,
        glossary_id=payload.glossary_id,
        term=payload.term,
        description=payload.description,
        category_id=payload.category_id
    )

    glossary = get_glossary_by_id(db, updated.glossary_id)
    if glossary:
        _sync_one_glossary(db, glossary)
    
    return {
        "glossary_id": updated.glossary_id,
        "id": updated.id,
        "term": updated.term,
        "description": updated.description,
        "category_id": updated.category_id,
        "category_name": updated.category.name if updated.category else None,
        "created_by": updated.created_by,
        "created_at": updated.created_at.isoformat() if updated.created_at else None
    }


@router.delete("/glossary/terms/{term_id}")
def delete_term_route(
    term_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(GLOSSARY_MANAGERS))
):
    term = get_term_by_id(db, term_id)
    if not term:
        raise HTTPException(status_code=404, detail="Terme non trouvé")
    
    delete_term(db, term_id)
    return {"message": "Terme supprimé avec succès"}


@router.post("/glossary/sync")
def sync_glossary_to_atlas(
    glossary_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user=Depends(require_role(GLOSSARY_MANAGERS))
):
    """
    Force a taxonomy sync (glossaries/categories/terms) to Atlas.
    Useful when you want Atlas up-to-date without waiting for a dataset push.
    """
    if glossary_id is not None:
        glossary = get_glossary_by_id(db, glossary_id)
        if not glossary:
            raise HTTPException(status_code=404, detail="Glossaire non trouvé")
        return sync_glossary_terms([glossary], db)

    glossaries = get_all_glossaries(db)
    return sync_glossary_terms(glossaries, db)
