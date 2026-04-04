from sqlalchemy.orm import Session
from db.glossary import GlossaryTerm
from typing import Optional, List


def get_all_terms(db: Session) -> List[GlossaryTerm]:
    """Récupère tous les termes du glossaire"""
    return db.query(GlossaryTerm).order_by(GlossaryTerm.term.asc()).all()


def get_term_by_id(db: Session, term_id: int) -> Optional[GlossaryTerm]:
    """Récupère un terme par son ID"""
    return db.query(GlossaryTerm).filter(GlossaryTerm.id == term_id).first()


def get_term_by_name(db: Session, term: str) -> Optional[GlossaryTerm]:
    """Récupère un terme par son nom"""
    return db.query(GlossaryTerm).filter(GlossaryTerm.term == term).first()


def create_term(db: Session, term: str, description: str, category: str, created_by: str) -> GlossaryTerm:
    """Crée un nouveau terme"""
    db_term = GlossaryTerm(
        term=term,
        description=description,
        category=category,
        created_by=created_by
    )
    db.add(db_term)
    db.commit()
    db.refresh(db_term)
    return db_term


def update_term(db: Session, term_id: int, term: str = None, description: str = None, category: str = None) -> Optional[GlossaryTerm]:
    """Met à jour un terme existant"""
    db_term = get_term_by_id(db, term_id)
    if not db_term:
        return None
    
    if term is not None:
        db_term.term = term
    if description is not None:
        db_term.description = description
    if category is not None:
        db_term.category = category
    
    db.commit()
    db.refresh(db_term)
    return db_term


def delete_term(db: Session, term_id: int) -> bool:
    """Supprime un terme"""
    db_term = get_term_by_id(db, term_id)
    if not db_term:
        return False
    
    db.delete(db_term)
    db.commit()
    return True