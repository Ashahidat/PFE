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
    # 🔥 DEBUG DÉTAILLÉ
    logger.info("=" * 60)
    logger.info(f"📥 POST /descriptions pour dataset {dataset_id}")
    logger.info(f"👤 Utilisateur: {user['sub']}")
    logger.info(f"📦 Nombre de descriptions reçues: {len(input_data.descriptions)}")
    
    # Afficher les 10 premières descriptions
    for i, desc in enumerate(input_data.descriptions[:10]):
        logger.info(f"  [{i}] column='{desc.column_name}', description='{desc.description[:50]}...' (len={len(desc.description)})")
    
    if len(input_data.descriptions) == 0:
        logger.warning("⚠️⚠️⚠️ AUCUNE DESCRIPTION REÇUE DANS LA REQUÊTE! ⚠️⚠️⚠️")
    
    # 1️⃣ Vérifier le dataset
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()

    if not dataset:
        logger.error(f"❌ Dataset {dataset_id} non trouvé")
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    
    logger.info(f"✅ Dataset trouvé: {dataset.name}")

    # 2️⃣ Gestion de la version
    dataset_version = db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id,
        DatasetVersion.atlas_guid.is_(None)
    ).first()

    if not dataset_version:
        last_version = db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset_id
        ).order_by(DatasetVersion.version_number.desc()).first()
        
        next_version = (last_version.version_number + 1) if last_version else 1
        
        dataset_version = DatasetVersion(
            dataset_id=dataset_id,
            version_number=next_version,
            created_by=user["sub"],
            change_comment="Version créée pour la description des colonnes"
        )
        db.add(dataset_version)
        db.commit()
        db.refresh(dataset_version)
        logger.info(f"🆕 Nouvelle version temporaire créée: v{dataset_version.version_number} (ID: {dataset_version.id})")
    else:
        logger.info(f"✅ Version temporaire existante: v{dataset_version.version_number} (ID: {dataset_version.id})")

    # 3️⃣ Convertir et filtrer
    descriptions_dict = {
        desc.column_name: desc.description 
        for desc in input_data.descriptions 
        if desc.description and desc.description.strip()
    }
    
    logger.info(f"📊 Après filtrage: {len(descriptions_dict)} descriptions non vides")
    
    if len(descriptions_dict) == 0 and len(input_data.descriptions) > 0:
        logger.warning(f"⚠️ Toutes les {len(input_data.descriptions)} descriptions étaient vides après trim!")
        for desc in input_data.descriptions:
            logger.warning(f"   - '{desc.column_name}': '{repr(desc.description)}'")

    # 4️⃣ Sauvegarde
    saved_count = bulk_create_or_update_descriptions(
        db=db,
        dataset_version_id=str(dataset_version.id),
        descriptions=descriptions_dict,
        user_id=user["sub"]
    )

    logger.info(f"✅ {saved_count} descriptions sauvegardées")
    logger.info("=" * 60)

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


# ===================== ROUTES D'HÉRITAGE =====================

@router.get("/api/datasets/{dataset_id}/inherited-descriptions")
async def get_inherited_descriptions(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    logger.info("=" * 80)
    logger.info(f"🔍 DEBUG get_inherited_descriptions")
    logger.info(f"Dataset ID reçu: {dataset_id}")
    
    # 1️⃣ Vérifier le dataset
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    
    logger.info(f"📊 Dataset trouvé:")
    logger.info(f"   - name: {dataset.name}")
    logger.info(f"   - project_id: {dataset.project_id}")
    logger.info(f"   - id: {dataset.id}")
    
    # 2️⃣ Récupérer TOUTES les versions (sans filtre pour voir)
    all_versions = db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id,
        DatasetVersion.atlas_guid.isnot(None)
    ).order_by(DatasetVersion.version_number.desc()).all()
    
    logger.info(f"📦 TOTAL des versions dans DB pour ce dataset_id: {len(all_versions)}")
    for v in all_versions:
        logger.info(f"   - Version {v.version_number}: guid={v.atlas_guid[:20] if v.atlas_guid else 'None'}...")
    
    # 3️⃣ Récupérer les versions du MÊME projet en joignant Dataset
    previous_versions = db.query(DatasetVersion).join(
        Dataset, Dataset.id == DatasetVersion.dataset_id
    ).filter(
        Dataset.id == dataset_id,
        Dataset.project_id == dataset.project_id,
        DatasetVersion.atlas_guid.isnot(None)
    ).order_by(DatasetVersion.version_number.desc()).limit(5).all()
    
    logger.info(f"📦 Versions filtrées par project_id={dataset.project_id}: {len(previous_versions)}")
    
    # 4️⃣ DEBUG CRUCIAL: Afficher les project_id des versions trouvées SANS filtre
    logger.info("🔍 Vérification des project_id des versions:")
    for v in all_versions:
        # Récupérer le dataset parent via la relation
        parent_dataset = db.query(Dataset).filter(Dataset.id == v.dataset_id).first()
        if parent_dataset:
            logger.info(f"   Version {v.version_number}: dataset_id={v.dataset_id}, project_id={parent_dataset.project_id}")
            if parent_dataset.project_id != dataset.project_id:
                logger.warning(f"   ⚠️⚠️⚠️ BUG DÉTECTÉ: Version d'un AUTRE projet ({parent_dataset.project_id}) attachée à ce dataset_id!")
    
    if not previous_versions:
        logger.info("ℹ️ Aucune version précédente trouvée dans le même projet")
        return {"versions": []}
    
    # 5️⃣ Récupérer les descriptions
    result = []
    for version in previous_versions:
        descriptions = db.query(ColumnDescription).filter(
            ColumnDescription.dataset_version_id == version.id
        ).all()
        
        logger.info(f"📝 Version {version.version_number}: {len(descriptions)} descriptions")
        
        if descriptions:
            result.append({
                "version_number": version.version_number,
                "created_at": version.created_at.isoformat() if version.created_at else None,
                "descriptions": [
                    {
                        "column_name": d.column_name,
                        "description": d.description
                    }
                    for d in descriptions
                ]
            })
    
    logger.info("=" * 80)
    return {"versions": result}


@router.get("/api/datasets/{dataset_id}/parent-suggestions")
async def get_parent_suggestions(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    logger.info("=" * 80)
    logger.info(f"🔍 DEBUG get_parent_suggestions")
    logger.info(f"Dataset ID reçu: {dataset_id}")
    
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    
    logger.info(f"📊 Dataset courant: {dataset.name}, project_id={dataset.project_id}")
    
    from db.dataset_signatures import DatasetSignature
    from db.dataset_versions import DatasetVersion
    
    current_sig = db.query(DatasetSignature).filter(
        DatasetSignature.dataset_id == dataset_id
    ).order_by(DatasetSignature.created_at.desc()).first()
    
    if not current_sig:
        logger.info("❌ Aucune signature trouvée")
        return {"has_parent": False, "suggestions": []}
    
    logger.info(f"📊 Signature courante: structure_hash={current_sig.structure_hash[:16]}...")
    
    # Chercher des datasets similaires
    similar_datasets = db.query(DatasetSignature).join(
        Dataset, Dataset.id == DatasetSignature.dataset_id
    ).filter(
        DatasetSignature.structure_hash == current_sig.structure_hash,
        DatasetSignature.dataset_id != dataset_id,
        Dataset.project_id == dataset.project_id
    ).order_by(DatasetSignature.created_at.desc()).limit(3).all()
    
    logger.info(f"📊 Datasets similaires trouvés: {len(similar_datasets)}")
    
    suggestions = []
    seen_columns = set()
    
    for sig in similar_datasets:
        # Récupérer le dataset
        similar_dataset = db.query(Dataset).filter(Dataset.id == sig.dataset_id).first()
        logger.info(f"   - Dataset similaire: {similar_dataset.name if similar_dataset else 'N/A'}, project_id={similar_dataset.project_id if similar_dataset else 'N/A'}")
        
        version = db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == sig.dataset_id
        ).order_by(DatasetVersion.version_number.desc()).first()
        
        if version:
            descriptions = db.query(ColumnDescription).filter(
                ColumnDescription.dataset_version_id == version.id
            ).all()
            logger.info(f"      → {len(descriptions)} descriptions trouvées")
            
            for desc in descriptions:
                if desc.column_name not in seen_columns:
                    suggestions.append({
                        "column_name": desc.column_name,
                        "description": desc.description,
                        "source_dataset": version.dataset_id,
                        "source_version": version.version_number
                    })
                    seen_columns.add(desc.column_name)
    
    logger.info(f"📊 Suggestions finales: {len(suggestions)}")
    logger.info("=" * 80)
    
    return {
        "has_parent": len(suggestions) > 0,
        "suggestions": suggestions
    }