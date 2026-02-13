from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import logging
import os
import time

from config import spark
from db.connexion_db import get_db
from db.datasets import Dataset
from atlas.client import atlas_post, atlas_put, ATLAS_TYPEDEF_URL, ATLAS_SEARCH_URL, atlas_get
from atlas.typedefs import typedefs_payload
from atlas.datasets import create_dataset, link_versioning
from atlas.columns import create_columns
from atlas.signatures import find_smart_parent, calculate_dataset_signature, persist_signature_to_db
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
        # ----------------------
        # 1️⃣ Récupérer dataset
        # ----------------------
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset introuvable")

        file_path = dataset.file_path
        hash_value = dataset.hash
        original_name = dataset.name

        logger.info(f"🚀 Push Atlas: {original_name}")
        logger.info(f"   ID: {dataset_id}")
        logger.info(f"   Hash: {hash_value[:8]}...")

        # ----------------------
        # 2️⃣ Lire le PARQUET
        # ----------------------
        df = spark.read.parquet(file_path)
        logger.info(f"📊 {df.count()} lignes, {len(df.columns)} colonnes")
        logger.info(f"   Colonnes: {list(df.columns)}")

        # ----------------------
        # 3️⃣ Déployer typedefs (ignorer 409)
        # ----------------------
        logger.info("📦 Déploiement des typedefs Atlas...")
        for idx, entityDef in enumerate(typedefs_payload["entityDefs"]):
            try:
                if idx == 0:
                    atlas_put(ATLAS_TYPEDEF_URL, {"entityDefs": [entityDef]})
                else:
                    atlas_post(ATLAS_TYPEDEF_URL, {"entityDefs": [entityDef]})
                logger.info(f"  ✅ EntityDef: {entityDef['name']}")
            except Exception as e:
                if "409" not in str(e):
                    raise
                logger.info(f"  ℹ️ EntityDef existant: {entityDef['name']}")

        for rel_def in typedefs_payload["relationshipDefs"]:
            try:
                atlas_post(ATLAS_TYPEDEF_URL, {"relationshipDefs": [rel_def]})
                logger.info(f"  ✅ RelationshipDef: {rel_def['name']}")
            except Exception as e:
                if "409" not in str(e):
                    raise
                logger.info(f"  ℹ️ RelationshipDef existant: {rel_def['name']}")

        for class_def in typedefs_payload["classificationDefs"]:
            try:
                atlas_post(ATLAS_TYPEDEF_URL, {"classificationDefs": [class_def]})
                logger.info(f"  ✅ Classification: {class_def['name']}")
            except Exception as e:
                if "409" not in str(e):
                    raise
                logger.info(f"  ℹ️ Classification existante: {class_def['name']}")

        # ----------------------
        # 4️⃣ Calcul signature
        # ----------------------
        logger.info("🔍 Calcul de la signature...")
        signature = calculate_dataset_signature(df, original_name)
        persist_signature_to_db(db, dataset.id, signature)
        logger.info(f"✅ Signature calculée: {signature['structure_hash'][:16]}...")

        # ----------------------
        # 5️⃣ Recherche parent
        # ----------------------
        parent_guid = None
        parent_qn = None
        parent_columns = []
        parent_column_mapping = {}
        base_url = ATLAS_SEARCH_URL.split("/search")[0]

        if dataset.atlas_guid:
            logger.info(f"🔗 Dataset déjà lié, recherche dernière version...")
            try:
                parent_guid = find_latest_version(dataset.atlas_guid)
                res = atlas_get(f"{base_url}/entity/guid/{parent_guid}")
                parent_qn = res.json()["entity"]["attributes"]["qualifiedName"]
                logger.info(f"✅ Dernière version trouvée: {parent_qn}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur recherche dernière version: {e}")

        if not parent_guid:
            logger.info(f"🔍 Recherche intelligente du parent...")
            parent_guid, parent_qn, parent_columns, parent_column_mapping = find_smart_parent(df, original_name, dataset_id, db)
            if parent_guid:
                logger.info(f"✅ Parent trouvé: {parent_qn}")
                logger.info(f"✅ {len(parent_columns)} colonnes parent récupérées")
                logger.info(f"✅ {len(parent_column_mapping)} mappings colonnes disponibles")
                logger.info(f"📋 Mappings parent: {parent_column_mapping}")
            else:
                logger.info(f"ℹ️ Aucun parent trouvé, création d'un nouveau dataset racine")

        # ----------------------
        # 6️⃣ Créer le DataSet
        # ----------------------
        logger.info(f"📝 Création du dataset...")
        dataset_guid, dataset_existed = create_dataset(
            hash_value,
            original_name,
            file_path,
            parent_qn,
            df,
            signature,
            owner_employee_id=dataset.owner_employee_id
        )
        dataset.atlas_guid = dataset_guid
        db.commit()
        logger.info(f"✅ Dataset créé: {dataset_guid}")

        # ----------------------
        # 7️⃣ Lien versioning + Process Atlas versionné
        # ----------------------
        process_guid = None
        if parent_guid and parent_guid != dataset_guid:
            logger.info(f"🔗 Gestion du lien versioning datasets et création Process Atlas...")

            # 🔹 Vérifier si un Process existe déjà pour parent -> output
            try:
                search_res = atlas_get(f"{base_url}/v2/search/basic", params={
                    "query": f"Process AND inputs.guid:{parent_guid} AND outputs.guid:{dataset_guid}"
                })
                existing_processes = search_res.json().get("entities", [])
                if existing_processes:
                    process_guid = existing_processes[0]["guid"]
                    logger.info(f"ℹ️ Process existant trouvé: {existing_processes[0]['attributes']['name']} ({process_guid})")
                else:
                    # 🔹 Créer Process versionné automatiquement
                    process_guid = create_import_process(
                        dataset_inputs=parent_guid,
                        dataset_output_guid=dataset_guid,
                        operation="TRANSFORMATION",
                        description=f"Version dérivée de {parent_qn}"
                    )
                    logger.info(f"✅ Nouveau Process créé: {process_guid}")
            except Exception as e:
                logger.warning(f"⚠️ Impossible de vérifier ou créer Process: {e}")

            # 🔹 Créer le lien versioning
            link_versioning(parent_guid, dataset_guid)
            logger.info(f"✅ Lien versioning datasets créé")

        # ----------------------
        # 8️⃣ Colonnes
        # ----------------------
        logger.info(f"📋 Création des colonnes avec relations visibles...")
        column_guids, column_entities = create_columns(
            df, 
            dataset_guid, 
            hash_value,
            parent_dataset_guid=parent_guid,
            parent_columns=parent_columns,
            parent_column_mapping=parent_column_mapping
        )
        logger.info(f"✅ {len(column_guids)} colonnes créées")
        logger.info(f"📋 Mapping colonnes créées: {column_guids}")

        # ----------------------
        # 9️⃣ Statistiques propagation colonnes
        # ----------------------
        propagated = 0
        if parent_column_mapping:
            for col_name, child_guid in column_guids.items():
                if col_name in parent_column_mapping:
                    propagated += 1
            logger.info(f"🏷️ {propagated}/{len(column_guids)} logicalColumnId propagés du parent")

        return {
            "message": "Dataset ajouté à Atlas avec relations column_versioning et Process versionné",
            "dataset_guid": dataset_guid,
            "dataset_existed": dataset_existed,
            "parent_guid": parent_guid,
            "parent_qualified_name": parent_qn,
            "process_guid": process_guid,
            "column_guids": column_guids,
            "columns_count": len(column_guids),
            "propagated_columns": propagated,
            "parent_column_mapping": parent_column_mapping
        }

    except Exception as e:
        logger.error(f"❌ Erreur: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Nettoyage
        try:
            for f in os.listdir(TMP_DIR):
                full = os.path.join(TMP_DIR, f)
                if os.path.isfile(full):
                    os.remove(full)
            logger.debug("🧹 Nettoyage tmp effectué")
        except Exception as e:
            logger.warning(f"⚠️ Erreur nettoyage tmp: {e}")
