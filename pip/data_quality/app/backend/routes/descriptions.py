from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from typing import List, Dict, Optional
import logging
from pydantic import BaseModel

from db.connexion_db import get_db
from db.datasets import Dataset
from db.dataset_versions import DatasetVersion
from db.dataset_signatures import DatasetSignature
from db.crud_dataset_signatures import create_dataset_signature
from db.crud_column_signatures import create_column_signature
from db.column_descriptions import ColumnDescription
from db.crud_column_descriptions import (
    bulk_create_or_update_descriptions,
    get_descriptions_by_version,
    get_description_dict_by_version,
    copy_descriptions_from_previous_version,
    delete_descriptions_for_columns,
)
from db.crud_column_classification_choices import (
    bulk_set_choices as bulk_set_column_classification_choices,
    get_choices_by_version as get_column_classification_choices_by_version,
)
from jwt_dependencies import get_current_user
from atlas.metadata import sync_dataset_metadata_to_atlas
from atlas.signatures import calculate_dataset_signature
from config import spark

router = APIRouter()
logger = logging.getLogger("descriptions")

def _get_latest_published_version(db: Session, dataset_id: str) -> Optional[DatasetVersion]:
    return db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id,
        DatasetVersion.atlas_guid.isnot(None)
    ).order_by(DatasetVersion.version_number.desc()).first()


def _get_latest_descriptions_by_column(db: Session, dataset_id: str) -> Dict[str, Dict]:
    """
    Returns the freshest description per column for a dataset across all versions.
    Newer versions win; inside the same version, the latest update wins.
    """
    rows = db.query(
        ColumnDescription.column_name,
        ColumnDescription.description,
        DatasetVersion.version_number,
        DatasetVersion.created_at,
        func.coalesce(ColumnDescription.updated_at, ColumnDescription.created_at).label("last_update")
    ).join(
        DatasetVersion,
        DatasetVersion.id == ColumnDescription.dataset_version_id
    ).filter(
        DatasetVersion.dataset_id == dataset_id
    ).order_by(
        DatasetVersion.version_number.desc(),
        func.coalesce(ColumnDescription.updated_at, ColumnDescription.created_at).desc()
    ).all()

    latest_by_column: Dict[str, Dict] = {}
    for row in rows:
        if row.column_name not in latest_by_column:
            latest_by_column[row.column_name] = {
                "description": row.description,
                "source_version": row.version_number,
                "source_created_at": row.created_at.isoformat() if row.created_at else None,
                "last_update": row.last_update.isoformat() if row.last_update else None
            }
    return latest_by_column


def _ensure_dataset_signature(db: Session, dataset: Dataset) -> DatasetSignature | None:
    """
    Retourne la signature la plus récente du dataset.
    Si elle n'existe pas encore, la calcule et la persiste.
    """
    signature = db.query(DatasetSignature).filter(
        DatasetSignature.dataset_id == dataset.id
    ).order_by(DatasetSignature.created_at.desc()).first()

    if signature and signature.signature:
        return signature

    if not dataset.file_path:
        logger.warning(f"⚠️ Dataset {dataset.id} sans file_path, impossible de calculer la signature")
        return None

    logger.info(f"🔄 Signature absente pour {dataset.id}, calcul en cours...")
    df = spark.read.parquet(dataset.file_path)
    computed = calculate_dataset_signature(df, dataset.name)
    signature = create_dataset_signature(
        db=db,
        dataset_id=str(dataset.id),
        structure_hash=computed["structure_hash"],
        signature=computed,
        columns_count=computed.get("columns_count"),
        rows_count=computed.get("rows_count"),
        algo_version="v1",
    )

    for col_name, meta in computed["columns"].items():
        create_column_signature(
            db=db,
            dataset_signature_id=str(signature.id),
            column_name=col_name,
            data_type=meta["dtype"],
            mean=meta.get("mean"),
            std=meta.get("std"),
            distinct_count=meta.get("ndist"),
            sample_hash=meta.get("sample_hash"),
        )

    logger.info(f"✅ Signature calculée et persistée pour {dataset.id}: {signature.structure_hash[:16]}...")
    return signature

# ===================== MODÈLES PYDANTIC =====================

class ColumnDescriptionInput(BaseModel):
    column_name: str
    description: str

class SaveDescriptionsInput(BaseModel):
    descriptions: List[ColumnDescriptionInput]
    classifications: Optional[List["ColumnClassificationInput"]] = None

class DatasetSimpleInfo(BaseModel):
    id: str
    name: str
    columns_list: List[str]
    description: Optional[str] = None

class DescriptionResponse(BaseModel):
    column_name: str
    description: str
    created_at: Optional[str] = None


class ColumnClassificationInput(BaseModel):
    column_name: str
    classification_name: Optional[str] = None  # 'PII' | 'SENSITIVE' | 'NONE'/null


class ColumnClassificationResponse(BaseModel):
    column_name: str
    classification_name: str


SaveDescriptionsInput.model_rebuild()

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
    # If the dataset was already pushed, metadata edits must attach to the latest published version.
    dataset_version = _get_latest_published_version(db, dataset_id)

    # Backfill: dataset has an Atlas GUID but no published version row exists (partial push / legacy state).
    if not dataset_version and dataset.atlas_guid:
        draft = db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.atlas_guid.is_(None)
        ).order_by(DatasetVersion.version_number.desc()).first()

        if draft:
            draft.atlas_guid = dataset.atlas_guid
            if not draft.change_comment:
                draft.change_comment = "Backfill: published version (from datasets.atlas_guid)"
            else:
                draft.change_comment = f"{draft.change_comment} | Backfill: published version"
            db.commit()
            db.refresh(draft)
            dataset_version = draft
            logger.warning(
                f"🛠️ Backfill version publiée: v{dataset_version.version_number} "
                f"(ID: {dataset_version.id}) guid={dataset_version.atlas_guid}"
            )

    if not dataset_version:
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
        logger.info(f"🆕 Nouvelle version brouillon créée (pre-push): v{dataset_version.version_number} (ID: {dataset_version.id})")
    else:
        logger.info(f"✅ Version cible pour metadata: v{dataset_version.version_number} (ID: {dataset_version.id}) guid={dataset_version.atlas_guid or 'NULL'}")

    # Si on vient d'ouvrir une nouvelle version brouillon vide, on hérite automatiquement
    # des descriptions de la dernière version disponible pour garder le formulaire prérempli.
    if not get_descriptions_by_version(db, str(dataset_version.id)):
        previous_version = db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset_id,
            DatasetVersion.id != dataset_version.id
        ).order_by(DatasetVersion.version_number.desc()).first()
        if previous_version:
            inherited_count = copy_descriptions_from_previous_version(
                db=db,
                new_version_id=str(dataset_version.id),
                previous_version_id=str(previous_version.id),
                user_id=user["sub"],
            )
            if inherited_count:
                logger.info(
                    f"📋 {inherited_count} description(s) héritée(s) de v{previous_version.version_number} "
                    f"vers v{dataset_version.version_number}"
                )

    # 3️⃣ Convertir en dict (on garde aussi les descriptions vides pour pouvoir effacer)
    input_by_column: Dict[str, str] = {}
    for desc in input_data.descriptions or []:
        col = (desc.column_name or "").strip()
        if not col:
            continue
        input_by_column[col] = (desc.description or "").strip()

    descriptions_dict = {c: d for c, d in input_by_column.items() if d}
    empty_columns = [c for c, d in input_by_column.items() if not d]

    logger.info(
        f"📊 Input colonnes: {len(input_by_column)} (non vides: {len(descriptions_dict)}, vides: {len(empty_columns)})"
    )
    
    if len(input_by_column) == 0 and len(input_data.descriptions) > 0:
        logger.warning("⚠️ Toutes les lignes reçues étaient invalides (column_name vide)")

    # 4️⃣ Sauvegarde
    saved_count = 0
    if descriptions_dict:
        saved_count = bulk_create_or_update_descriptions(
            db=db,
            dataset_version_id=str(dataset_version.id),
            descriptions=descriptions_dict,
            user_id=user["sub"]
        )

    deleted_count = 0
    if empty_columns:
        deleted_count = delete_descriptions_for_columns(
            db=db,
            dataset_version_id=str(dataset_version.id),
            columns=empty_columns,
        )

    logger.info(f"✅ {saved_count} descriptions sauvegardées")
    if deleted_count:
        logger.info(f"🗑️ {deleted_count} descriptions supprimées (vides)")
    logger.info("=" * 60)

    saved_classifications_count = 0
    if input_data.classifications is not None:
        try:
            choices_dict = {
                item.column_name: item.classification_name
                for item in input_data.classifications
                if item and item.column_name
            }
            saved_classifications_count = bulk_set_column_classification_choices(
                db=db,
                dataset_version_id=str(dataset_version.id),
                choices=choices_dict,
                user_id=user["sub"],
            )
        except Exception as exc:
            logger.warning(f"⚠️ Impossible de sauvegarder les classifications colonnes: {exc}")

    # 5️⃣ Synchroniser Atlas si le dataset est déjà publié
    atlas_synced = False
    atlas_error: str | None = None
    if dataset.atlas_guid:
        try:
            # On pousse toutes les colonnes présentes dans la requête (y compris vides => effacement).
            sync_dataset_metadata_to_atlas(
                db=db,
                dataset=dataset,
                column_descriptions=input_by_column,
            )
            atlas_synced = True
        except Exception as exc:
            atlas_error = str(exc)
            logger.warning(f"⚠️ Échec synchro Atlas (descriptions): {exc}", exc_info=True)

    message = f"{saved_count} description(s) sauvegardée(s)"
    if deleted_count:
        message += f", {deleted_count} effacée(s)"
    if dataset.atlas_guid:
        message += " — Atlas synchronisé" if atlas_synced else " — ⚠️ Atlas non synchronisé"

    return {
        "message": message if not atlas_error else f"{message} ({atlas_error})",
        "saved_count": saved_count,
        "deleted_count": deleted_count,
        "saved_classifications_count": saved_classifications_count,
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
    latest_version = _get_latest_published_version(db, dataset_id) or db.query(DatasetVersion).filter(
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


@router.get(
    "/api/datasets/{dataset_id}/column-classifications",
    response_model=List[ColumnClassificationResponse],
)
async def get_column_classifications(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Récupère les classifications colonnes (PII/SENSITIVE) enregistrées
    pour la dernière version (brouillon ou publiée).
    """
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"],
    ).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")

    latest_version = _get_latest_published_version(db, dataset_id) or db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id
    ).order_by(DatasetVersion.version_number.desc()).first()

    if not latest_version:
        return []

    rows = get_column_classification_choices_by_version(db, str(latest_version.id))
    return [{"column_name": r.column_name, "classification_name": r.classification_name} for r in rows]


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
    
    # 2️⃣ Récupérer TOUTES les versions (y compris temporaires atlas_guid=None)
    all_versions = db.query(DatasetVersion).filter(
        DatasetVersion.dataset_id == dataset_id
    ).order_by(DatasetVersion.version_number.desc()).all()
    
    logger.info(f"📦 TOTAL des versions dans DB pour ce dataset_id: {len(all_versions)}")
    for v in all_versions:
        logger.info(f"   - Version {v.version_number}: guid={v.atlas_guid[:20] if v.atlas_guid else 'None'}...")
    
    # 3️⃣ Récupérer les versions du MÊME projet en joignant Dataset
    previous_versions = db.query(DatasetVersion).join(
        Dataset, Dataset.id == DatasetVersion.dataset_id
    ).filter(
        Dataset.id == dataset_id,
        Dataset.project_id == dataset.project_id
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
    """
    Suggère des descriptions depuis des datasets similaires dans le même projet
    Utilise le même scoring que find_smart_parent
    """
    logger.info("=" * 80)
    logger.info(f"🔍 DEBUG get_parent_suggestions")
    logger.info(f"Dataset ID reçu: {dataset_id}")
    
    # 1️⃣ Vérifier le dataset
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()
    
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")
    
    logger.info(f"📊 Dataset courant: {dataset.name}, project_id={dataset.project_id}")
    
    # 2️⃣ Importer compute_similarity_score
    from atlas.signatures import compute_similarity_score
    from db.dataset_versions import DatasetVersion

    # 3️⃣ Récupérer la signature courante
    current_sig = _ensure_dataset_signature(db, dataset)

    if not current_sig:
        logger.info("❌ Aucune signature trouvée pour le dataset courant")
        return {"has_parent": False, "suggestions": []}
    
    logger.info(f"📊 Signature courante: structure_hash={current_sig.structure_hash[:16]}...")
    
    # 4️⃣ Récupérer TOUS les datasets du même projet (sauf le courant)
    all_datasets_in_project = db.query(Dataset).filter(
        Dataset.project_id == dataset.project_id,
        Dataset.id != dataset_id
    ).all()
    
    logger.info(f"📦 {len(all_datasets_in_project)} datasets trouvés dans le projet (hors courant)")
    
    # 5️⃣ Calculer le score pour chaque dataset
    candidates = []
    
    for ds in all_datasets_in_project:
        # Récupérer la dernière signature
        sig = db.query(DatasetSignature).filter(
            DatasetSignature.dataset_id == ds.id
        ).order_by(DatasetSignature.created_at.desc()).first()
        
        if not sig or not sig.signature:
            logger.debug(f"   ⚠️ Dataset {ds.name}: pas de signature")
            continue
        
        # Calculer le score de similarité
        score = compute_similarity_score(current_sig.signature, sig.signature)
        
        logger.info(f"   📊 {ds.name}: score={score:.3f}")
        
        # Récupérer la version la plus récente qui porte des descriptions
        latest_by_column = _get_latest_descriptions_by_column(db, str(ds.id))
        if not latest_by_column:
            logger.debug(f"   ⚠️ Dataset {ds.name}: aucune description disponible")
            continue

        # Garder une version de référence pour l'affichage (max des versions utilisées)
        latest_source_version = max(v["source_version"] for v in latest_by_column.values())
        
        # Seuil adaptatif basé sur la similarité des colonnes
        cols_current = set(current_sig.signature.get("columns", {}).keys())
        cols_parent = set(ds.columns_list) if ds.columns_list else set()
        jaccard = len(cols_current & cols_parent) / len(cols_current | cols_parent) if (cols_current | cols_parent) else 0
        
        # Ajuster le seuil
        if cols_parent.issubset(cols_current):
            # Le dataset courant a TOUTES les colonnes du parent → c'est une extension
            threshold = 0.45
            logger.debug(f"   → Extension détectée (jaccard={jaccard:.2f}), seuil={threshold}")
        elif jaccard > 0.8:
            threshold = 0.55
        else:
            threshold = 0.60
        
        if score >= threshold:
            candidates.append({
                "dataset": ds,
                "source_version": latest_source_version,
                "score": score,
                "signature": sig,
                "latest_by_column": latest_by_column
            })
            logger.info(f"   ✅ Accepté (score={score:.3f} >= {threshold})")
        else:
            logger.debug(f"   ❌ Rejeté (score={score:.3f} < {threshold})")
    
    # 6️⃣ Trier par score décroissant
    candidates.sort(key=lambda x: x["score"], reverse=True)
    logger.info(f"🏆 {len(candidates)} candidats retenus après scoring")
    
    # 7️⃣ Récupérer les descriptions des meilleurs candidats
    suggestions = []
    seen_columns = set()
    
    for candidate in candidates[:5]:  # Top 5
        latest_by_column = candidate["latest_by_column"]
        logger.info(
            f"   📝 {candidate['dataset'].name} "
            f"(latest v{candidate['source_version']}, score={candidate['score']:.3f}): "
            f"{len(latest_by_column)} descriptions fusionnées"
        )

        for column_name, meta in latest_by_column.items():
            if column_name not in seen_columns:
                suggestions.append({
                    "column_name": column_name,
                    "description": meta["description"],
                    "source_dataset": candidate["dataset"].name,
                    "source_version": meta["source_version"],
                    "similarity_score": round(candidate["score"], 3)
                })
                seen_columns.add(column_name)
    
    logger.info(f"📊 Suggestions finales: {len(suggestions)} colonnes uniques")
    logger.info("=" * 80)
    
    return {
        "has_parent": len(suggestions) > 0,
        "suggestions": suggestions
    }
