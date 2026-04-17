from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.sql import func
from db.dataset_glossary_assignment import DatasetGlossaryAssignment
from typing import List


def get_assignments_for_dataset(db: Session, dataset_id: str) -> List[DatasetGlossaryAssignment]:
    return db.query(DatasetGlossaryAssignment).filter(
        DatasetGlossaryAssignment.dataset_id == dataset_id
    ).all()


def assign_term_to_dataset(db: Session, dataset_id: str, glossary_term_id: int, created_by: str, column_name: str | None = None):
    existing = db.query(DatasetGlossaryAssignment).filter(
        and_(
            DatasetGlossaryAssignment.dataset_id == dataset_id,
            DatasetGlossaryAssignment.glossary_term_id == glossary_term_id
        ,
            DatasetGlossaryAssignment.column_name == column_name
        )
    ).first()
    if existing:
        return existing
    assignment = DatasetGlossaryAssignment(
        dataset_id=dataset_id,
        glossary_term_id=glossary_term_id,
        column_name=column_name,
        created_by=created_by
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def remove_assignment(db: Session, dataset_id: str, glossary_term_id: int, column_name: str | None = None) -> bool:
    assignment = db.query(DatasetGlossaryAssignment).filter(
        and_(
            DatasetGlossaryAssignment.dataset_id == dataset_id,
            DatasetGlossaryAssignment.glossary_term_id == glossary_term_id,
            DatasetGlossaryAssignment.column_name == column_name
        )
    ).first()
    if not assignment:
        return False
    db.delete(assignment)
    db.commit()
    return True


def set_assignment_for_column(
    db: Session,
    dataset_id: str,
    column_name: str | None,
    glossary_term_id: int | None,
    created_by: str
) -> DatasetGlossaryAssignment | None:
    """
    Définit un terme pour une colonne (ou le dataset si column_name None).
    Si glossary_term_id est None, l'affectation est supprimée.
    """
    existing = db.query(DatasetGlossaryAssignment).filter(
        and_(
            DatasetGlossaryAssignment.dataset_id == dataset_id,
            DatasetGlossaryAssignment.column_name == column_name
        )
    ).first()

    if glossary_term_id is None:
        if existing:
            db.delete(existing)
            db.commit()
        return None

    if existing:
        if existing.glossary_term_id == glossary_term_id:
            return existing
        existing.glossary_term_id = glossary_term_id
        existing.updated_at = func.now()
        existing.created_by = created_by
        db.commit()
        db.refresh(existing)
        return existing

    assignment = DatasetGlossaryAssignment(
        dataset_id=dataset_id,
        glossary_term_id=glossary_term_id,
        column_name=column_name,
        created_by=created_by
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment
