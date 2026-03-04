# routes/versionning.py
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import logging

from db.connexion_db import get_db
from db.datasets import Dataset
from db.crud_dataset_signatures import create_dataset_signature
from db.crud_column_signatures import create_column_signature
from atlas.signatures import calculate_dataset_signature, find_smart_parent
from config import spark
from jwt_dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger("versionning")

@router.post("/api/datasets/{dataset_id}/compute-signature")
async def compute_dataset_signature(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Calcule et sauvegarde la signature du dataset
    À appeler juste après le preview
    """
    logger.info(f"🔍 Calcul signature pour dataset {dataset_id}")
    
    # 1️⃣ Vérifier que le dataset existe et appartient à l'utilisateur
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()
    
    if not dataset:
        logger.warning(f"❌ Dataset {dataset_id} introuvable ou non autorisé")
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    
    try:
        # 2️⃣ Lire le fichier Parquet
        logger.info(f"📖 Lecture du fichier: {dataset.file_path}")
        df = spark.read.parquet(dataset.file_path)
        logger.info(f"📊 {len(df.columns)} colonnes trouvées")
        
        # 3️⃣ Calculer la signature (fonction existante dans atlas.signatures)
        signature = calculate_dataset_signature(df, dataset.name)
        logger.info(f"✅ Signature calculée: {signature['structure_hash'][:16]}...")
        
        # 4️⃣ Sauvegarder la signature du dataset
        ds_sig = create_dataset_signature(
            db=db,
            dataset_id=dataset_id,
            structure_hash=signature["structure_hash"],
            signature=signature,
            columns_count=signature.get("columns_count"),
            rows_count=signature.get("rows_count"),
            algo_version="v1"
        )
        logger.info(f"💾 Signature dataset sauvegardée: {ds_sig.id}")
        
        # 5️⃣ Sauvegarder les signatures des colonnes
        for col_name, meta in signature["columns"].items():
            create_column_signature(
                db=db,
                dataset_signature_id=str(ds_sig.id),
                column_name=col_name,
                data_type=meta["dtype"],
                mean=meta.get("mean"),
                std=meta.get("std"),
                distinct_count=meta.get("ndist"),
                sample_hash=meta.get("sample_hash")
            )
        logger.info(f"📝 Signatures des {len(signature['columns'])} colonnes sauvegardées")
        
        return {
            "status": "success",
            "message": "Signature calculée et sauvegardée",
            "structure_hash": signature["structure_hash"][:16],
            "columns_count": len(signature["columns"]),
            "rows_count": signature.get("rows_count", 0)
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du calcul de signature: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur calcul signature: {str(e)}")


@router.post("/api/datasets/{dataset_id}/find-parent")
async def find_parent_dataset(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Recherche un parent pour ce dataset basé sur les signatures
    À appeler après le calcul de signature
    """
    logger.info(f"🔍 Recherche parent pour dataset {dataset_id}")
    
    # 1️⃣ Vérifier le dataset
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()
    
    if not dataset:
        logger.warning(f"❌ Dataset {dataset_id} introuvable ou non autorisé")
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    
    try:
        # 2️⃣ Lire le fichier
        df = spark.read.parquet(dataset.file_path)
        
        # 3️⃣ Chercher un parent (fonction existante dans atlas.signatures)
        parent_guid, parent_qn, parent_columns, parent_column_mapping = find_smart_parent(
            df, 
            dataset.name, 
            dataset_id, 
            db, 
            project_id=str(dataset.project_id) if dataset.project_id else None
        )
        
        if parent_guid:
            logger.info(f"✅ Parent trouvé: {parent_qn} (GUID: {parent_guid})")
            logger.info(f"📋 {len(parent_columns)} colonnes parent récupérées")
            
            # Optionnel: Sauvegarder les infos du parent dans le dataset
            # (si tu veux les réutiliser plus tard)
            
            return {
                "parent_found": True,
                "parent_guid": parent_guid,
                "parent_qualified_name": parent_qn,
                "parent_columns_count": len(parent_columns) if parent_columns else 0,
                "parent_column_mapping_count": len(parent_column_mapping) if parent_column_mapping else 0
            }
        else:
            logger.info("ℹ️ Aucun parent trouvé")
            return {
                "parent_found": False,
                "parent_guid": None,
                "parent_qualified_name": None,
                "parent_columns_count": 0,
                "parent_column_mapping_count": 0
            }
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la recherche parent: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur recherche parent: {str(e)}")


@router.get("/api/datasets/{dataset_id}/versionning-status")
async def get_versionning_status(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Vérifie si la signature et le parent ont déjà été calculés
    Utile pour l'UI
    """
    logger.info(f"🔍 Vérification statut versionning pour dataset {dataset_id}")
    
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    
    # Vérifier si une signature existe
    from db.dataset_signatures import DatasetSignature
    signature = db.query(DatasetSignature).filter(
        DatasetSignature.dataset_id == dataset_id
    ).order_by(DatasetSignature.created_at.desc()).first()
    
    # Vérifier si un parent a été trouvé (à adapter selon comment tu stockes)
    # Pour l'instant, on retourne juste le statut de la signature
    
    return {
        "has_signature": signature is not None,
        "signature_id": str(signature.id) if signature else None,
        "signature_hash": signature.structure_hash[:16] if signature else None,
        "signature_date": signature.created_at.isoformat() if signature else None
    }