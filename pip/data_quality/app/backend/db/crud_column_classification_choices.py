from typing import Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from db.column_classification_choices import ColumnClassificationChoice
import uuid


ALLOWED_COLUMN_CLASSIFICATIONS = {"PII", "SENSITIVE"}


def _normalize_choice(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = str(value).strip().upper()
    if not cleaned or cleaned == "NONE":
        return None
    return cleaned


def get_choices_by_version(db: Session, dataset_version_id: str) -> List[ColumnClassificationChoice]:
    return (
        db.query(ColumnClassificationChoice)
        .filter(ColumnClassificationChoice.dataset_version_id == dataset_version_id)
        .all()
    )


def get_choice_dict_by_version(db: Session, dataset_version_id: str) -> Dict[str, str]:
    rows = get_choices_by_version(db, dataset_version_id)
    return {row.column_name: row.classification_name for row in rows}


def bulk_set_choices(
    db: Session,
    dataset_version_id: str,
    choices: Dict[str, Optional[str]],  # {column_name: 'PII'|'SENSITIVE'|None}
    user_id: str,
) -> int:
    """
    Upsert choices for PII/SENSITIVE; delete rows for None.
    Returns number of rows created/updated (not deleted).
    """
    changed = 0
    for column_name, raw_choice in choices.items():
        choice = _normalize_choice(raw_choice)

        existing = (
            db.query(ColumnClassificationChoice)
            .filter(
                ColumnClassificationChoice.dataset_version_id == dataset_version_id,
                ColumnClassificationChoice.column_name == column_name,
            )
            .first()
        )

        if choice is None:
            if existing:
                db.delete(existing)
                db.commit()
            continue

        if choice not in ALLOWED_COLUMN_CLASSIFICATIONS:
            # Ignore unknown values to stay permissive for older clients.
            continue

        if existing:
            existing.classification_name = choice
            existing.updated_at = func.now()
            existing.updated_by = user_id
            db.commit()
            db.refresh(existing)
            changed += 1
        else:
            new_row = ColumnClassificationChoice(
                id=uuid.uuid4(),
                dataset_version_id=dataset_version_id,
                column_name=column_name,
                classification_name=choice,
                created_by=user_id,
            )
            db.add(new_row)
            db.commit()
            db.refresh(new_row)
            changed += 1

    return changed


def copy_choices_from_previous_version(
    db: Session,
    new_version_id: str,
    previous_version_id: str,
    user_id: str,
) -> int:
    rows = get_choices_by_version(db, previous_version_id)
    count = 0
    for old in rows:
        new_row = ColumnClassificationChoice(
            id=uuid.uuid4(),
            dataset_version_id=new_version_id,
            column_name=old.column_name,
            classification_name=old.classification_name,
            created_by=old.created_by,
            created_at=old.created_at,
            updated_by=user_id,
            updated_at=func.now(),
        )
        db.add(new_row)
        count += 1
    db.commit()
    return count

