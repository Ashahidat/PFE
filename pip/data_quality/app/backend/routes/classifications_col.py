from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.connexion_db import get_db
from db.datasets import Dataset
from db.classifications import EntityClassification
from atlas.classifications_validations import get_allowed_column_classifications
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def _normalize_dataset_classification(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().upper()
    if v == "DEPARTMENT":
        return "RESTRICTED"
    return v

@router.get("/dataset/{dataset_id}/allowed-classifications")
def get_allowed_classifications(
    dataset_id: str,
    db: Session = Depends(get_db)
):
    """
    Retourne les classifications de colonnes autorisées pour ce dataset
    Utile pour l'interface utilisateur
    """
    dataset_classification: str | None = None

    # 1) Prefer explicit active classification records (Atlas-style)
    dataset_class = db.query(EntityClassification).filter(
        EntityClassification.entity_type == "DATASET",
        EntityClassification.entity_id == dataset_id,
        EntityClassification.is_active.is_(True)
    ).first()
    if dataset_class and dataset_class.classification_name:
        dataset_classification = _normalize_dataset_classification(dataset_class.classification_name)

    # 2) Fallback to Dataset.classification (set at upload: PUBLIC/DEPARTMENT)
    if not dataset_classification:
        ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if ds and ds.classification:
            dataset_classification = _normalize_dataset_classification(ds.classification)

    if not dataset_classification:
        dataset_classification = "RESTRICTED"

    allowed = get_allowed_column_classifications(dataset_classification)
    return {"allowed": allowed, "dataset_classification": dataset_classification, "message": None}

@router.get("/dataset/{dataset_id}/column-classifications")
def get_column_classifications(
    dataset_id: str,
    db: Session = Depends(get_db)
):
    """
    Retourne toutes les classifications actives des colonnes d'un dataset
    """
    column_classes = db.query(EntityClassification).filter(
        EntityClassification.entity_type == "COLUMN",
        EntityClassification.entity_id == dataset_id,
        EntityClassification.is_active.is_(True)
    ).all()
    
    result = {}
    for cc in column_classes:
        result[cc.column_name] = {
            "classification": cc.classification_name,
            "atlas_guid": cc.atlas_guid,
            "applied_at": cc.applied_at,
            "applied_by": cc.applied_by
        }
    
    return {"columns": result}
