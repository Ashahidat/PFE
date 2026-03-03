from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List, Dict, Optional
import logging
from pydantic import BaseModel

from db.connexion_db import get_db
from db.datasets import Dataset
from db.dataset_versions import DatasetVersion
from db.column_descriptions import ColumnDescription
from db.crud_column_descriptions import (
    bulk_create_or_update_descriptions,
    get_descriptions_by_version,
    get_description_dict_by_version
)
from jwt_dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger("descriptions")

# ===================== MODÈLES PYDANTIC =====================

class ColumnDescriptionInput(BaseModel):
    column_name: str
    description: str

class SaveDescriptionsInput(BaseModel):
    descriptions: List[ColumnDescriptionInput]

class DatasetSimpleInfo(BaseModel):
    id: str
    name: str
    columns_list: List[str]
    description: Optional[str] = None

class DescriptionResponse(BaseModel):
    column_name: str
    description: str
    created_at: Optional[str] = None

# ===================== ROUTES =====================

@router.get("/api/datasets/{dataset_id}/simple-info", response_model=DatasetSimpleInfo)
async def get_dataset_simple_info(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Récupère les informations simples d'un dataset (pour la page de description)
    """
    logger.info(f"📋 Chargement infos dataset {dataset_id} pour utilisateur {user['sub']}")
    
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()

    if not dataset:
        logger.warning(f"❌ Dataset {dataset_id} introuvable ou non autorisé")
        raise HTTPException(status_code=404, detail="Dataset introuvable")

    return {
        "id": str(dataset.id),
        "name": dataset.name,
        "columns_list": dataset.columns_list,
        "description": dataset.description
    }


@router.post("/api/datasets/{dataset_id}/descriptions")
async def save_descriptions(
    dataset_id: str,
    input_data: SaveDescriptionsInput,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Sauvegarde les descriptions des colonnes pour la version courante du dataset
    """
    logger.info(f"💾 Sauvegarde descriptions pour dataset {dataset_id} par {user['sub']}")
    
    # 1️⃣ Vérifier que le dataset appartient à l'utilisateur
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")

    # 2️⃣ Récupérer ou créer la version en cours (celle qui n'a pas encore de GUID Atlas)
    dataset_version = db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id,
        DatasetVersion.atlas_guid.is_(None)  # Pas encore pushée
    ).first()  # Pas besoin de order_by, on veut une seule version non pushée

    if not dataset_version:
        # ✅ Récupérer la dernière version (peu importe son statut)
        last_version = db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset_id
        ).order_by(DatasetVersion.version_number.desc()).first()
        
        # Déterminer le prochain numéro de version
        if last_version:
            next_version = last_version.version_number + 1
        else:
            next_version = 1  # Première version
        
        # Créer une nouvelle version temporaire
        dataset_version = DatasetVersion(
            dataset_id=dataset_id,
            version_number=next_version,
            created_by=user["sub"],
            change_comment="Version créée pour la description des colonnes"
        )
        db.add(dataset_version)
        db.commit()
        db.refresh(dataset_version)
        logger.info(f"🆕 Nouvelle version temporaire créée: v{dataset_version.version_number}")
    else:
        logger.info(f"✅ Version temporaire existante réutilisée: v{dataset_version.version_number}")

    # 3️⃣ Convertir la liste en dictionnaire pour le bulk insert
    descriptions_dict = {
        desc.column_name: desc.description 
        for desc in input_data.descriptions 
        if desc.description and desc.description.strip()
    }

    # 4️⃣ Sauvegarder les descriptions
    saved_count = bulk_create_or_update_descriptions(
        db=db,
        dataset_version_id=str(dataset_version.id),
        descriptions=descriptions_dict,
        user_id=user["sub"]
    )

    logger.info(f"✅ {saved_count} descriptions sauvegardées pour version {dataset_version.id}")

    return {
        "message": f"{saved_count} descriptions sauvegardées",
        "saved_count": saved_count,
        "dataset_version_id": str(dataset_version.id),
        "dataset_version_number": dataset_version.version_number
    }


@router.get("/api/datasets/{dataset_id}/descriptions", response_model=List[DescriptionResponse])
async def get_descriptions(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Récupère les descriptions de la dernière version du dataset
    """
    logger.info(f"📖 Récupération descriptions pour dataset {dataset_id}")
    
    # Vérifier le dataset
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")

    # Récupérer la dernière version
    latest_version = db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id
    ).order_by(DatasetVersion.version_number.desc()).first()

    if not latest_version:
        return []

    # Récupérer les descriptions
    descriptions = get_descriptions_by_version(db, str(latest_version.id))
    
    return [
        {
            "column_name": d.column_name,
            "description": d.description,
            "created_at": d.created_at.isoformat() if d.created_at else None
        }
        for d in descriptions
    ]


@router.get("/api/datasets/{dataset_id}/descriptions/check")
async def check_descriptions_status(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Vérifie si des descriptions existent déjà (utile pour l'UI)
    """
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")

    # Compter les versions avec descriptions
    versions_with_descriptions = db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id
    ).join(
        ColumnDescription, 
        ColumnDescription.dataset_version_id == DatasetVersion.id
    ).distinct(DatasetVersion.id).count()

    total_descriptions = db.query(ColumnDescription).join(
        DatasetVersion, DatasetVersion.id == ColumnDescription.dataset_version_id
    ).filter(
        DatasetVersion.dataset_id == dataset_id
    ).count()

    return {
        "has_descriptions": total_descriptions > 0,
        "versions_count": versions_with_descriptions,
        "total_descriptions": total_descriptions
    }


@router.delete("/api/datasets/{dataset_id}/descriptions")
async def delete_all_descriptions(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Supprime toutes les descriptions d'un dataset (pour test/rollback)
    """
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")

    # Supprimer via la relation en cascade
    versions = db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id
    ).all()

    deleted_count = 0
    for version in versions:
        deleted = db.query(ColumnDescription).filter(
            ColumnDescription.dataset_version_id == version.id
        ).delete(synchronize_session=False)
        deleted_count += deleted

    db.commit()
    
    logger.warning(f"🗑️ {deleted_count} descriptions supprimées par {user['sub']}")
    
    return {
        "message": f"{deleted_count} descriptions supprimées",
        "deleted_count": deleted_count
    }