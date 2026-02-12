# routes/push_atlas.py

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import logging
import os

from config import spark
from db.connexion_db import get_db
from db.datasets import Dataset
from atlas.client import atlas_post, atlas_put, atlas_get, ATLAS_TYPEDEF_URL, ATLAS_SEARCH_URL
from atlas.typedefs import typedefs_payload
from atlas.datasets import create_dataset, link_versioning
from atlas.columns import create_columns
from atlas.signatures import calculate_dataset_signature, persist_signature_to_db, find_smart_parent
from atlas.processes import create_import_process
from atlas.versioning import find_latest_version
from jwt_dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger("push-atlas")
logger.setLevel(logging.DEBUG)

TMP_DIR = "/home/ashahi/PFE/pip/data_quality/tmp"
os.makedirs(TMP_DIR, exist_ok=True)

@router.post("/push-atlas/{dataset_id}")
def push_atlas(dataset_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        # 1️⃣ Récupérer dataset
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset introuvable")

        file_path = dataset.file_path
        hash_value = dataset.hash
        original_name = dataset.name

        # 2️⃣ Lire le PARQUET
        df = spark.read.parquet(file_path)

        # 3️⃣ Déployer typedefs Atlas (inchangé)
        for idx, entityDef in enumerate(typedefs_payload["entityDefs"]):
            try:
                if idx == 0:
                    atlas_put(ATLAS_TYPEDEF_URL, {"entityDefs": [entityDef]})
                else:
                    atlas_post(ATLAS_TYPEDEF_URL, {"entityDefs": [entityDef]})
            except Exception as e:
                if "409" in str(e):
                    logger.info(f"Typedef déjà existant, on ignore: {entityDef['name']}")
                else:
                    raise

        for rel_def in typedefs_payload["relationshipDefs"]:
            try:
                atlas_post(ATLAS_TYPEDEF_URL, {"relationshipDefs": [rel_def]})
            except Exception as e:
                if "409" not in str(e):
                    raise

        for class_def in typedefs_payload["classificationDefs"]:
            try:
                atlas_post(ATLAS_TYPEDEF_URL, {"classificationDefs": [class_def]})
            except Exception as e:
                if "409" in str(e):
                    logger.info(f"Classification déjà existante: {class_def['name']}")
                else:
                    raise

        # 4️⃣ Calculer la signature du dataset
        signature = calculate_dataset_signature(df, original_name)
        persist_signature_to_db(db, dataset.id, signature)

        # ============================================================
        # 5️⃣ PARENT INTELLIGENT - VERSION CORRIGÉE
        # ============================================================
        parent_atlas_guid = None  # GUID Atlas du parent (pour API calls)
        parent_qn = None         # QualifiedName = hash du parent (pour DB et création)
        parent_hash = None       # Hash du parent (pour recherche DB)
        parent_found_in_atlas = False
        
        base_url = ATLAS_SEARCH_URL.split("/search")[0]

        # 🔍 CAS 1: Le dataset a déjà un atlas_guid → chercher la dernière version via versioning chain
        if dataset.atlas_guid:
            try:
                latest_version_guid = find_latest_version(dataset.atlas_guid)
                if latest_version_guid and latest_version_guid != dataset.atlas_guid:
                    parent_atlas_guid = latest_version_guid
                    # Récupérer le qualifiedName (hash) du parent
                    res = atlas_get(f"{base_url}/entity/guid/{parent_atlas_guid}")
                    parent_qn = res.json()["entity"]["attributes"]["qualifiedName"]
                    parent_hash = parent_qn  # Le qualifiedName EST le hash
                    parent_found_in_atlas = True
                    logger.info(f"📦 Parent trouvé via versioning chain: GUID={parent_atlas_guid}, hash={parent_hash[:8] if parent_hash else 'None'}...")
            except Exception as e:
                logger.warning(f"⚠️ Erreur récupération versioning chain: {e}")

        # 🔍 CAS 2: Pas de parent trouvé via versioning → chercher via signature intelligente
        if not parent_atlas_guid:
            parent_guid_from_sig, parent_hash_from_sig = find_smart_parent(df, original_name)
            
            if parent_guid_from_sig and parent_hash_from_sig:
                logger.info(f"🔍 Parent trouvé par signature: GUID={parent_guid_from_sig}, hash={parent_hash_from_sig[:8]}...")
                
                # 👉 ÉTAPE CRITIQUE: Chercher dans NOTRE base de données avec le HASH
                parent_dataset_in_db = db.query(Dataset).filter(Dataset.hash == parent_hash_from_sig).first()
                
                if parent_dataset_in_db and parent_dataset_in_db.atlas_guid:
                    # ✅ Le parent existe dans notre DB ET dans Atlas
                    parent_atlas_guid = parent_dataset_in_db.atlas_guid
                    parent_qn = parent_hash_from_sig
                    parent_hash = parent_hash_from_sig
                    parent_found_in_atlas = True
                    logger.info(f"✅ Parent trouvé dans DB et Atlas: GUID={parent_atlas_guid}")
                else:
                    # ⚠️ Le parent existe dans Atlas mais pas encore dans notre DB
                    # Cas normal: c'est la première fois qu'on push ce parent, ou on a perdu le lien
                    parent_atlas_guid = parent_guid_from_sig
                    parent_qn = parent_hash_from_sig
                    parent_hash = parent_hash_from_sig
                    parent_found_in_atlas = True
                    logger.info(f"⚠️ Parent dans Atlas mais pas en DB - utilisation du GUID retourné: {parent_atlas_guid}")
            else:
                logger.info("ℹ️ Aucun parent trouvé par find_smart_parent")

        # ============================================================
        # 6️⃣ CRÉER LE DATASET DANS ATLAS
        # ============================================================
        dataset_guid, dataset_existed = create_dataset(
            hash_value,
            original_name,
            file_path,
            parent_qn if parent_found_in_atlas else None,  # Ne passer que si parent trouvé
            df,
            signature,
            owner_employee_id=dataset.owner_employee_id
        )
        
        # Mettre à jour l'atlas_guid dans notre DB
        dataset.atlas_guid = dataset_guid
        db.commit()
        logger.info(f"✅ Dataset créé dans Atlas: GUID={dataset_guid}, existed={dataset_existed}")

        # ============================================================
        # 7️⃣ CRÉER LE VERSIONING (RELATION dataset_versioning)
        # ============================================================
        process_guid = None
        if parent_found_in_atlas and parent_atlas_guid and parent_atlas_guid != dataset_guid:
            logger.info(f"🔗 Création du versioning: {parent_atlas_guid} → {dataset_guid}")
            try:
                process_guid = create_import_process(
                    dataset_inputs=parent_atlas_guid,
                    dataset_output_guid=dataset_guid,
                    operation="TRANSFORMATION",
                    description=f"Version dérivée de {parent_qn}"
                )
                link_versioning(parent_atlas_guid, dataset_guid)
                logger.info(f"✅ Versioning créé avec succès")
            except Exception as e:
                logger.warning(f"⚠️ Erreur création versioning: {e}")
        else:
            if parent_hash and not parent_found_in_atlas:
                logger.info(f"ℹ️ Parent trouvé ({parent_hash[:8]}) mais pas dans Atlas → pas de versioning")
            else:
                logger.info(f"ℹ️ Pas de parent trouvé → dataset initial")

        # ============================================================
        # 8️⃣ CRÉER LES COLONNES AVEC MATCHING INTELLIGENT
        # ============================================================
        logger.info(f"🎯 Création des colonnes avec matching intelligent...")
        
        column_guids = []
        if parent_found_in_atlas and parent_atlas_guid and parent_atlas_guid != dataset_guid:
            # 🟢 CAS VERSIONNÉ: Dataset a un parent DANS ATLAS → matching automatique
            logger.info(f"🔗 Dataset versionné: parent GUID={parent_atlas_guid}")
            logger.info("   Utilisation du matching intelligent pour les logicalColumnId")
            
            column_guids = create_columns(
                df=df,
                dataset_guid=dataset_guid,
                dataset_qualified_name=original_name,
                logical_column_ids=None,  # None = matching auto via parent_dataset_guid
                parent_dataset_guid=parent_atlas_guid  # 🎯 Clé pour le matching!
            )
        else:
            # 🔵 CAS INITIAL: Pas de parent dans Atlas → création avec nouveaux IDs
            logger.info(f"🆕 Dataset initial - création de nouveaux logicalColumnId")
            logical_column_ids = {col: f"{dataset.id}:{col}" for col in df.columns}
            column_guids = create_columns(
                df=df,
                dataset_guid=dataset_guid,
                dataset_qualified_name=original_name,
                logical_column_ids=logical_column_ids,
                parent_dataset_guid=None
            )

        # Vérification
        if not column_guids:
            logger.warning("⚠️ Aucun GUID de colonne retourné")
        else:
            logger.info(f"✅ {len(column_guids)} colonnes créées avec succès")

        # ============================================================
        # 9️⃣ RETOUR
        # ============================================================
        message = "Ce dataset existe déjà dans Atlas." if dataset_existed else "Dataset ajouté à Atlas avec succès !"

        return {
            "message": message,
            "dataset_guid": dataset_guid,
            "process_guid": process_guid,
            "parent_guid": parent_atlas_guid if parent_found_in_atlas else None,
            "parent_hash": parent_hash[:8] + "..." if parent_hash else None,
            "parent_found_in_atlas": parent_found_in_atlas,
            "column_guids": column_guids,
        }

    except Exception as e:
        logger.error(f"❌ Erreur dans push_atlas: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Nettoyage TMP
        try:
            for f in os.listdir(TMP_DIR):
                full = os.path.join(TMP_DIR, f)
                if os.path.isfile(full):
                    os.remove(full)
        except:
            pass