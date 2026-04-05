from sqlalchemy.orm import Session
from sqlalchemy import and_
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
