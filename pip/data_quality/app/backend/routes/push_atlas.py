from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
import logging
import os
import time
import uuid
import shutil
import json

from config import spark
from db.connexion_db import get_db
from db.datasets import Dataset
from db.dataset_signatures import DatasetSignature
from db.crud_dataset_signatures import create_dataset_signature
from db.crud_column_signatures import create_column_signature
from db.crud_dataset_versions import (
    create_dataset_version, 
    get_latest_version, 
    get_version_by_atlas_guid
)
from db.crud_processes import create_process_record
from db.crud_column_lineage import bulk_create_column_lineage, ColumnLineage
from db.crud_push_history import create_push_history
from atlas.client import atlas_post, atlas_put, ATLAS_TYPEDEF_URL, ATLAS_SEARCH_URL, atlas_get
from atlas.typedefs import typedefs_payload
from atlas.datasets import create_dataset, link_versioning
from atlas.columns import create_columns
from atlas.signatures import find_smart_parent, calculate_dataset_signature, persist_signature_to_db, compute_similarity_score
from atlas.processes import create_import_process
from atlas.versioning import find_latest_version
from jwt_dependencies import get_current_user
from db.dataset_versions import DatasetVersion
from atlas.data_quality import create_data_quality_checks_from_json
from db.data_quality_to_db import save_data_quality_results_from_json


router = APIRouter()
logger = logging.getLogger("push-atlas")
logger.setLevel(logging.DEBUG)

TMP_DIR = "/home/ashahi/PFE/pip/data_quality/tmp"
RESULTS_DIR = "/home/ashahi/PFE/pip/data_quality/results"
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

@router.post("/push-atlas/{dataset_id}")
def push_atlas(dataset_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    import time
    start_time = time.time()
    employee_id = user.get("employee_id") or user.get("sub")
    
    if not employee_id:
        logger.error("❌ Identifiant utilisateur manquant dans le token")
        raise HTTPException(status_code=400, detail="Identifiant utilisateur manquant")
    
    # Variables à suivre dans le finally
    json_files = []
    dq_guids = []
    dq_db_ids = []
    processed_files = []
    
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
        logger.info(f"   User: {employee_id}")

        # ----------------------
        # 2️⃣ Lire le PARQUET
        # ----------------------
        df = spark.read.parquet(file_path)
        rows_count = df.count()
        columns_count = len(df.columns)
        logger.info(f"📊 {rows_count} lignes, {columns_count} colonnes")
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
        parent_version_id = None
        parent_version_number = 0
        similarity_score = 0
        base_url = ATLAS_SEARCH_URL.split("/search")[0]

        # 🔥 CORRECTION: Ne pas utiliser get_latest_version avec le dataset_id actuel
        # car c'est un nouveau dataset dans la table datasets
        if dataset.atlas_guid:
            logger.info(f"🔗 Dataset déjà lié, recherche dernière version...")
            try:
                parent_guid = find_latest_version(dataset.atlas_guid)
                res = atlas_get(f"{base_url}/entity/guid/{parent_guid}")
                parent_qn = res.json()["entity"]["attributes"]["qualifiedName"]
                
                # Récupérer la version parent en base
                parent_version = get_version_by_atlas_guid(db, parent_guid)
                if parent_version:
                    parent_version_id = str(parent_version.id)
                    parent_version_number = parent_version.version_number
                    logger.info(f"✅ Dernière version trouvée: {parent_qn} (v{parent_version.version_number})")
            except Exception as e:
                logger.warning(f"⚠️ Erreur recherche dernière version: {e}")

        if not parent_guid:
            logger.info(f"🔍 Recherche intelligente du parent...")
            parent_guid, parent_qn, parent_columns, parent_column_mapping = find_smart_parent(df, original_name, dataset_id, db)
            if parent_guid:
                # 🔥 Récupérer la version du parent pour le numéro de version
                parent_version = get_version_by_atlas_guid(db, parent_guid)
                if parent_version:
                    parent_version_id = str(parent_version.id)
                    parent_version_number = parent_version.version_number
                    
                    # Calculer le score de similarité pour le tracking
                    sig_current = calculate_dataset_signature(df, original_name)
                    parent_sig_record = db.query(DatasetSignature)\
                        .join(DatasetVersion, DatasetVersion.dataset_id == DatasetSignature.dataset_id)\
                        .filter(DatasetVersion.atlas_guid == parent_guid)\
                        .order_by(DatasetSignature.created_at.desc())\
                        .first()
                    if parent_sig_record:
                        similarity_score = compute_similarity_score(sig_current, parent_sig_record.signature)
                
                logger.info(f"✅ Parent trouvé: {parent_qn} (score: {similarity_score:.3f})")
                logger.info(f"✅ {len(parent_columns)} colonnes parent récupérées")
                logger.info(f"✅ {len(parent_column_mapping)} mappings colonnes disponibles")
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
        
        # Mettre à jour l'atlas_guid du dataset
        old_atlas_guid = dataset.atlas_guid
        dataset.atlas_guid = dataset_guid
        dataset.last_modified_by = employee_id
        dataset.last_modified_at = func.now()
        db.commit()
        logger.info(f"✅ Dataset créé: {dataset_guid}")

        # 🔥 CORRECTION: Déterminer le numéro de version basé sur le parent, pas sur dataset.id
        if parent_version_id and parent_version_number > 0:
            # Héritage du parent : version = version_parent + 1
            new_version_number = parent_version_number + 1
            logger.info(f"📌 Héritage du parent: v{parent_version_number} -> v{new_version_number}")
        else:
            # Pas de parent ou parent non trouvé en base : version 1
            new_version_number = 1
            logger.info(f"📌 Nouveau dataset racine: version 1")
        
        # Créer la nouvelle version en base
        new_version = create_dataset_version(
            db=db,
            dataset_id=dataset.id,
            version_number=new_version_number,
            atlas_guid=dataset_guid,
            parent_version_id=parent_version_id,
            created_by=employee_id,
            change_comment=f"Push depuis {file_path}",
            source_file=file_path
        )
        logger.info(f"📌 Nouvelle version créée: v{new_version_number}")

        # 7️⃣ Lien versioning datasets avec enregistrement du processus en base
        process_guid = None
        process_name = None
        if parent_guid and parent_guid != dataset_guid:
            logger.info(f"🔗 Création du lien versioning datasets...")
            # Récupérer à la fois le GUID et le nom du process
            process_guid, process_name = create_import_process(
                dataset_inputs=parent_guid,
                dataset_output_guid=dataset_guid,
                operation="TRANSFORMATION",
                description=f"Version dérivée de {parent_qn}"
            )
            
            # ✅ ENREGISTRER LE PROCESS EN BASE AVEC LE VRAI NOM
            if process_guid:
                try:
                    create_process_record(
                        db=db,
                        atlas_process_guid=process_guid,
                        process_name=process_name,  # Utiliser le vrai nom du process
                        operation_type="TRANSFORMATION",
                        output_dataset_version_id=str(new_version.id),
                        input_dataset_version_id=parent_version_id,
                        created_by=employee_id,
                        execution_time_ms=int((time.time() - start_time) * 1000),
                        status="SUCCESS",
                        metadata={"parent_qn": parent_qn}
                    )
                    logger.info(f"✅ Process enregistré en base avec le nom: {process_name}")
                except Exception as e:
                    logger.warning(f"⚠️ Impossible d'enregistrer le Process en base: {e}")
            
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

        # ENREGISTRER LA LIGNÉE DES COLONNES
        propagated = 0
        column_lineages = []
        
        for col_name, child_guid in column_guids.items():
            # Récupérer le logicalColumnId depuis les entités retournées
            logical_id = None
            parent_col_id = None
            
            # Chercher dans les entités retournées
            for entity in column_entities:
                if entity.get("guid") == child_guid:
                    logical_id = entity["attributes"].get("logicalColumnId")
                    break
            
            if logical_id:
                # Vérifier si ce logical_id existait déjà dans une version parent
                if parent_version_id and col_name in parent_column_mapping:
                    parent_col = db.query(ColumnLineage).filter(
                        ColumnLineage.logical_column_id == logical_id,
                        ColumnLineage.dataset_version_id == parent_version_id
                    ).first()
                    if parent_col:
                        parent_col_id = str(parent_col.id)
                        propagated += 1
                
                lineage = ColumnLineage(
                    id=uuid.uuid4(),
                    logical_column_id=logical_id,
                    column_name=col_name,
                    dataset_version_id=str(new_version.id),
                    parent_column_id=parent_col_id,
                    data_type=str(df.schema[col_name].dataType)
                )
                column_lineages.append(lineage)
        
        if column_lineages:
            bulk_create_column_lineage(db, column_lineages)
            logger.info(f"🏷️ {len(column_lineages)} entrées de lignée créées")
            logger.info(f"🏷️ {propagated}/{len(column_guids)} logicalColumnId propagés du parent")

        # ----------------------
        # 🔥 10️⃣ ENVOYER LES RÉSULTATS DE QUALITÉ
        #       → Atlas
        #       → PostgreSQL
        #       → Archivage
        # ----------------------
        print("--------------------------------------------------------------------------------------------------")

        logger.info(f"📤 Envoi des résultats de qualité...")


        archive_dir = os.path.join(RESULTS_DIR, "archive")
        os.makedirs(archive_dir, exist_ok=True)

        json_files = []
        dq_guids = []
        dq_db_ids = []
        processed_files = []

        if os.path.exists(RESULTS_DIR):
            all_files = os.listdir(RESULTS_DIR)
            json_files = [f for f in all_files if f.endswith(".json")]

            logger.info(f"📁 Fichiers JSON trouvés: {json_files}")
        else:
            logger.warning(f"⚠️ Dossier results introuvable")

        for jf in json_files:
            json_path = os.path.join(RESULTS_DIR, jf)

            try:
                logger.info(f"📤 Traitement du fichier qualité: {jf}")

                # Lire le JSON une seule fois
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                dag_run_uuid = data.get("dag_run_id")

                # 🔹 1️⃣ Envoyer vers Atlas
                guids = create_data_quality_checks_from_json(
                    dataset_version_guid=new_version.atlas_guid,
                    json_path=json_path
                )
                dq_guids.extend(guids)

                # 🔹 2️⃣ Sauvegarder en PostgreSQL
                db_ids = save_data_quality_results_from_json(
                    db=db,
                    dataset_version_id=new_version.id,
                    dag_run_uuid=dag_run_uuid,
                    json_path=json_path
                )
                dq_db_ids.extend(db_ids)

                # 🔹 3️⃣ Marquer comme traité
                processed_files.append(jf)

                logger.info(f"✅ {len(guids)} checks envoyés Atlas")
                logger.info(f"✅ {len(db_ids)} checks enregistrés PostgreSQL")

            except Exception as e:
                logger.error(f"❌ Erreur traitement fichier {jf}: {e}")

        logger.info(f"📊 TOTAL Atlas: {len(dq_guids)}")
        logger.info(f"📊 TOTAL PostgreSQL: {len(dq_db_ids)}")

        # ----------------------
        # 9️⃣ ENREGISTRER L'HISTORIQUE DE PUSH
        # ----------------------
        execution_time = int((time.time() - start_time) * 1000)
        create_push_history(
            db=db,
            dataset_id=dataset.id,
            pushed_by=employee_id,
            status="SUCCESS",
            execution_time_ms=execution_time,
            columns_count=columns_count,
            rows_count=rows_count,
            parent_found=(parent_guid is not None),
            similarity_score=similarity_score if similarity_score > 0 else None,
            propagated_columns_count=propagated
        )
        logger.info(f"📊 Historique push enregistré (durée: {execution_time}ms)")

        return {
            "message": "Dataset ajouté à Atlas avec traçabilité complète",
            "dataset_guid": dataset_guid,
            "dataset_existed": dataset_existed,
            "version_number": new_version_number,
            "parent_guid": parent_guid,
            "parent_qualified_name": parent_qn,
            "parent_version_number": parent_version_number if parent_version_number > 0 else None,
            "process_guid": process_guid,
            "column_guids": column_guids,
            "columns_count": len(column_guids),
            "propagated_columns": propagated,
            "execution_time_ms": execution_time,
            "similarity_score": similarity_score,
            "data_quality_checks_count": len(dq_guids)
        }

    except Exception as e:
        logger.error(f"❌ Erreur: {e}", exc_info=True)
        
        # ENREGISTRER L'ÉCHEC
        try:
            execution_time = int((time.time() - start_time) * 1000)
            create_push_history(
                db=db,
                dataset_id=dataset_id,
                pushed_by=employee_id,
                status="FAILED",
                error_message=str(e)[:500],
                execution_time_ms=execution_time
            )
            logger.info(f"📊 Échec enregistré dans push_history")
        except Exception as inner_e:
            logger.error(f"❌ Impossible d'enregistrer l'échec: {inner_e}")
        
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # 🧹 Nettoyage TMP
        try:
            for f in os.listdir(TMP_DIR):
                full = os.path.join(TMP_DIR, f)
                if os.path.isfile(full):
                    os.remove(full)
            logger.debug("🧹 Nettoyage tmp effectué")
        except Exception as e:
            logger.warning(f"⚠️ Erreur nettoyage tmp: {e}")

        # 📦 Archivage de TOUS les fichiers JSON du dossier results
        try:
            archive_dir = os.path.join(RESULTS_DIR, "archive")
            os.makedirs(archive_dir, exist_ok=True)
            
            archived_count = 0
            if os.path.exists(RESULTS_DIR):
                for f in os.listdir(RESULTS_DIR):
                    if f.endswith('.json') and f != 'archive':  # Éviter d'archiver le dossier archive lui-même
                        source = os.path.join(RESULTS_DIR, f)
                        destination = os.path.join(
                            archive_dir,
                            f"{int(time.time())}_{f}"
                        )
                        if os.path.isfile(source):
                            shutil.move(source, destination)
                            archived_count += 1
                            
            logger.info(f"📦 {archived_count} fichiers qualité archivés")
        except Exception as e:
            logger.warning(f"⚠️ Erreur archivage results: {e}")