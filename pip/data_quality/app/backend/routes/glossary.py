from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from db.connexion_db import get_db
from db.glossary import GlossaryTerm
from db.glossary_crud import get_all_terms, get_term_by_id, create_term, update_term, delete_term
from jwt_dependencies import get_current_user
from core.permissions import require_role

router = APIRouter(tags=["glossary"])


from pydantic import BaseModel


class TermResponse(BaseModel):
    id: int
    term: str
    description: str | None
    category: str | None
    created_by: str | None
    created_at: str | None


class TermCreate(BaseModel):
    term: str
    description: str | None = None
    category: str | None = None


class TermUpdate(BaseModel):
    term: str | None = None
    description: str | None = None
    category: str | None = None


@router.get("/glossary/terms", response_model=List[TermResponse])
def get_terms(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    terms = get_all_terms(db)
    result = []
    for term in terms:
        result.append({
            "id": term.id,
            "term": term.term,
            "description": term.description,
            "category": term.category,
            "created_by": term.created_by,
            "created_at": term.created_at.isoformat() if term.created_at else None
        })
    return result


@router.post("/glossary/terms", response_model=TermResponse)
def create_term_route(
    payload: TermCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["ADMIN"]))
):
    existing = db.query(GlossaryTerm).filter(GlossaryTerm.term == payload.term).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ce terme existe déjà")
    
    new_term = create_term(
        db=db,
        term=payload.term,
        description=payload.description,
        category=payload.category,
        created_by=user.get("employee_id")
    )
    
    return {
        "id": new_term.id,
        "term": new_term.term,
        "description": new_term.description,
        "category": new_term.category,
        "created_by": new_term.created_by,
        "created_at": new_term.created_at.isoformat() if new_term.created_at else None
    }


@router.put("/glossary/terms/{term_id}", response_model=TermResponse)
def update_term_route(
    term_id: int,
    payload: TermUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role(["ADMIN"]))
):
    term = get_term_by_id(db, term_id)
    if not term:
        raise HTTPException(status_code=404, detail="Terme non trouvé")
    
    updated = update_term(
        db=db,
        term_id=term_id,
        term=payload.term,
        description=payload.description,
        category=payload.category
    )
    
    return {
        "id": updated.id,
        "term": updated.term,
        "description": updated.description,
        "category": updated.category,
        "created_by": updated.created_by,
        "created_at": updated.created_at.isoformat() if updated.created_at else None
    }


@router.delete("/glossary/terms/{term_id}")
def delete_term_route(
    term_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_role(["ADMIN"]))
):
    term = get_term_by_id(db, term_id)
    if not term:
        raise HTTPException(status_code=404, detail="Terme non trouvé")
    
    delete_term(db, term_id)
    return {"message": "Terme supprimé avec succès"}