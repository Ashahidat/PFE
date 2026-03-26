from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
import logging
import os
import time
import uuid
import shutil
import json
from typing import List, Dict, Any, Optional  # 👈 AJOUTER Optional

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
# 👇 IMPORTS MIS À JOUR - Ajout des fonctions de sécurité
from atlas.classifications import (
    add_quality_summary_classification, 
    add_quality_classification,
    add_restricted_classification,  # 👈 NOUVEAU
    add_public_classification        # 👈 NOUVEAU
)
from atlas.client import get_typedef_by_name
from db.column_descriptions import ColumnDescription

router = APIRouter()
logger = logging.getLogger("push-atlas")
logger.setLevel(logging.DEBUG)

TMP_DIR = "/home/ashahi/PFE/pip/data_quality/tmp"
RESULTS_DIR = "/home/ashahi/PFE/pip/data_quality/results"
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# ============================================================
# ROUTE PRINCIPALE
# ============================================================

@router.post("/push-atlas/{dataset_id}")
def push_atlas(
    dataset_id: str, 
    is_public: bool = False,  # 👈 NOUVEAU PARAMÈTRE
    db: Session = Depends(get_db), 
    user=Depends(get_current_user)
):
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
    security_success = False  # 👈 NOUVEAU
    
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
        description = dataset.description

        # ----------------------
        # 2️⃣ Lire le PARQUET
        # ----------------------
        df = spark.read.parquet(file_path)
        rows_count = df.count()
        columns_count = len(df.columns)
        logger.info(f"📊 {rows_count} lignes, {columns_count} colonnes")
        logger.info(f"   Colonnes: {list(df.columns)}")

        # ----------------------
        # 3️⃣ DÉPLOYER TYPEDEFS (robuste pour types personnalisés)
        # ----------------------
        logger.info("📦 Déploiement des typedefs Atlas...")

        # ⚡ 1️⃣ Déployer d'abord Column
        column_def = next(e for e in typedefs_payload["entityDefs"] if e["name"] == "Column")
        try:
            atlas_post(ATLAS_TYPEDEF_URL, {"entityDefs": [column_def]})
            logger.info("✅ EntityDef créé: Column")
        except Exception as e:
            if "409" not in str(e):
                raise
            logger.info("ℹ️ EntityDef existant: Column")

        # ⚡ 2️⃣ Déployer DataQualityCheck (dépend de Column)
        dq_def = next(e for e in typedefs_payload["entityDefs"] if e["name"] == "DataQualityCheck")
        try:
            atlas_post(ATLAS_TYPEDEF_URL, {"entityDefs": [dq_def]})
            logger.info("✅ EntityDef créé: DataQualityCheck")
        except Exception as e:
            if "409" not in str(e):
                raise
            logger.info("ℹ️ EntityDef existant: DataQualityCheck")

        # ⚡ 3️⃣ Déployer DataSet
        dataSetDef = next(e for e in typedefs_payload["entityDefs"] if e["name"] == "DataSet")
        try:
            atlas_put(ATLAS_TYPEDEF_URL, {"entityDefs": [dataSetDef]})
            logger.info("✅ DataSet déployé")
        except Exception as e:
            if "409" not in str(e):
                raise
            logger.info("ℹ️ DataSet existant")

        # ⚡ 3️⃣ Déployer les relations
        for rel_def in typedefs_payload.get("relationshipDefs", []):
            try:
                atlas_post(ATLAS_TYPEDEF_URL, {"relationshipDefs": [rel_def]})
                logger.info(f"✅ RelationshipDef: {rel_def['name']}")
            except Exception as e:
                if "409" not in str(e):
                    raise
                logger.info(f"ℹ️ RelationshipDef existant: {rel_def['name']}")

        # ⚡ 4️⃣ Déployer les classifications (y compris DQ_SUMMARY)
        for class_def in typedefs_payload.get("classificationDefs", []):
            try:
                atlas_post(ATLAS_TYPEDEF_URL, {"classificationDefs": [class_def]})
                logger.info(f"✅ Classification: {class_def['name']}")
            except Exception as e:
                if "409" not in str(e):
                    raise
                logger.info(f"ℹ️ Classification existante: {class_def['name']}")

        logger.info("⏳ Attente de la propagation des typedefs...")
        time.sleep(3)

        # ----------------------
        # 4️⃣ Calcul signature
        # ----------------------
        # 🔽🔽🔽 10 LIGNES À AJOUTER 🔽🔽🔽
        # Vérifier si une signature existe déjà (pré-calculée par /compute-signature)
        existing_sig = db.query(DatasetSignature).filter(
            DatasetSignature.dataset_id == dataset.id
        ).order_by(DatasetSignature.created_at.desc()).first()

        if existing_sig:
            logger.info(f"✅ Signature existante réutilisée: {existing_sig.structure_hash[:16]}...")
            signature = existing_sig.signature
        else:
            # Signature non trouvée, on la calcule (ancien comportement)
            logger.info("🔍 Calcul de la signature...")
            signature = calculate_dataset_signature(df, original_name)
            persist_signature_to_db(db, dataset.id, signature)
            logger.info(f"✅ Signature calculée: {signature['structure_hash'][:16]}...")
        # 🔼🔼🔼 FIN DES 10 LIGNES À AJOUTER 🔼🔼🔼

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
            parent_guid, parent_qn, parent_columns, parent_column_mapping = find_smart_parent(df, original_name, dataset_id, db, project_id=str(dataset.project_id))
            if parent_guid:
                parent_version = get_version_by_atlas_guid(db, parent_guid)
                if parent_version:
                    parent_version_id = str(parent_version.id)
                    parent_version_number = parent_version.version_number
                    
                    sig_current = signature  # Utiliser la signature récupérée ou calculée
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
        dataset_guid, dataset_existed = create_dataset(
            hash_value,
            original_name,
            file_path,
            parent_qn,
            df,
            owner_employee_id=dataset.owner_employee_id,
            project_id=str(dataset.project_id),
            description=description,
            version_number=new_version.version_number 
        )

        # 🔥 NOUVEAU : Récupérer le qualified name du dataset depuis Atlas
        base_url = ATLAS_SEARCH_URL.split("/search")[0]
        try:
            response = atlas_get(f"{base_url}/entity/guid/{dataset_guid}")
            if response.status_code == 200:
                entity_data = response.json()
                dataset_qualified_name = entity_data.get("entity", {}).get("attributes", {}).get("qualifiedName")
                logger.info(f"📛 Qualified name du dataset: {dataset_qualified_name}")
            else:
                # Fallback : construction manuelle (même logique que dans create_dataset)
                dataset_qualified_name = f"{original_name}@{hash_value}"
                logger.warning(f"⚠️ Utilisation fallback: {dataset_qualified_name}")
        except Exception as e:
            dataset_qualified_name = f"{original_name}@{hash_value}"
            logger.warning(f"⚠️ Erreur récupération, fallback: {dataset_qualified_name}")

        # Mettre à jour l'atlas_guid du dataset
        old_atlas_guid = dataset.atlas_guid
        dataset.atlas_guid = dataset_guid
        dataset.last_modified_by = employee_id
        dataset.last_modified_at = func.now()
        db.commit()
        logger.info(f"✅ Dataset créé: {dataset_guid}")

        # 🔍 RECHERCHER une version existante non pushée (créée par /descriptions)
        existing_version = db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset.id,
            DatasetVersion.atlas_guid.is_(None)  # Version temporaire
        ).first()

        if existing_version:
            # ✅ RÉUTILISER la version existante
            new_version = existing_version
            new_version.atlas_guid = dataset_guid  # Mettre à jour le GUID
            new_version.change_comment = f"Push depuis {file_path}"
            new_version.source_file = file_path
            db.commit()
            db.refresh(new_version)
            logger.info(f"📌 Version existante réutilisée: v{new_version.version_number}")
            
        else:
            # ⚠️ Créer une nouvelle version (cas où on push sans passer par /descriptions)
            # Déterminer le numéro de version
            if parent_version_id and parent_version_number > 0:
                new_version_number = parent_version_number + 1
            else:
                # Récupérer la dernière version du dataset
                last_version = db.query(DatasetVersion).filter(
                    DatasetVersion.dataset_id == dataset.id
                ).order_by(DatasetVersion.version_number.desc()).first()
                
                if last_version:
                    new_version_number = last_version.version_number + 1
                else:
                    new_version_number = 1
            
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

        # 7️⃣ Lien versioning datasets
        process_guid = None
        process_name = None
        if parent_guid and parent_guid != dataset_guid:
            logger.info(f"🔗 Création du lien versioning datasets...")
            process_guid, process_name = create_import_process(
                dataset_inputs=parent_guid,
                dataset_output_guid=dataset_guid,
                operation="TRANSFORMATION",
                description=f"Version dérivée de {parent_qn}"
            )
            
            if process_guid:
                try:
                    create_process_record(
                        db=db,
                        atlas_process_guid=process_guid,
                        process_name=process_name,
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
        # 8️⃣ Colonnes - UTILISER dataset_qualified_name
        # ----------------------
        logger.info(f"📋 Création des colonnes avec relations visibles...")

        # Récupérer les descriptions pour cette version
        descriptions_dict = {}
        if new_version and new_version.id:
            desc_records = db.query(ColumnDescription).filter(
                ColumnDescription.dataset_version_id == new_version.id
            ).all()
            descriptions_dict = {d.column_name: d.description for d in desc_records}
            logger.info(f"📝 {len(descriptions_dict)} descriptions chargées pour la version {new_version.version_number}")

        # ✅ MAINTENANT ON PASSE LE VRAI QUALIFIED NAME
        column_guids, column_entities = create_columns(
            df, 
            dataset_guid, 
            dataset_qualified_name,  # ← ICI, plus hash_value
            parent_dataset_guid=parent_guid,
            parent_columns=parent_columns,
            parent_column_mapping=parent_column_mapping,
            descriptions=descriptions_dict
        )
        logger.info(f"✅ {len(column_guids)} colonnes créées")

        # ENREGISTRER LA LIGNÉE DES COLONNES
        propagated = 0
        column_lineages = []
        
        for col_name, child_guid in column_guids.items():
            logical_id = None
            parent_col_id = None
            
            for entity in column_entities:
                if entity.get("guid") == child_guid:
                    logical_id = entity["attributes"].get("logicalColumnId")
                    break
            
            if logical_id:
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
        # 🔟 ENVOYER LES RÉSULTATS DE QUALITÉ
        # ----------------------
        print("--------------------------------------------------------------------------------------------------")
        logger.info(f"📤 Envoi des résultats de qualité...")

        # Collecter tous les checks pour le résumé global
        all_checks_data = []

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

                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                dag_run_uuid = data.get("dag_run_id")
                checks = data.get("checks", [])
                all_checks_data.extend(checks)

                # Envoyer vers Atlas
                guids = create_data_quality_checks_from_json(
                    dataset_version_guid=new_version.atlas_guid,
                    column_mapping=column_guids,
                    json_path=json_path
                )
                dq_guids.extend(guids)

                # Sauvegarder en PostgreSQL
                db_ids = save_data_quality_results_from_json(
                    db=db,
                    dataset_version_id=new_version.id,
                    dag_run_uuid=dag_run_uuid,
                    json_path=json_path
                )
                dq_db_ids.extend(db_ids)

                processed_files.append(jf)

                logger.info(f"✅ {len(guids)} checks envoyés Atlas")
                logger.info(f"✅ {len(db_ids)} checks enregistrés PostgreSQL")

            except Exception as e:
                logger.error(f"❌ Erreur traitement fichier {jf}: {e}")

        # ============================================================
        # AJOUT DU RÉSUMÉ QUALITÉ (VERSION LISIBLE)
        # ============================================================
        quality_success = False
        if all_checks_data:
            logger.info("📊 Ajout du résumé qualité...")
            
            quality_success = add_quality_summary_classification(
                entity_guid=new_version.atlas_guid,
                checks_data=all_checks_data
            )
            
            if quality_success:
                logger.info(f"✅ Résumé qualité ajouté")
            else:
                logger.warning("⚠️ Échec de l'ajout du résumé qualité")
                
                # Fallback minimal
                failed = sum(1 for c in all_checks_data 
                            if c.get("status", "").lower() in ["échoué", "failed"])
                if failed == 0:
                    add_quality_classification(new_version.atlas_guid, "SUCCESS")
                else:
                    add_quality_classification(new_version.atlas_guid, "WARNING")


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
            "version_number": new_version.version_number,
            "parent_guid": parent_guid,
            "parent_qualified_name": parent_qn,
            "parent_version_number": parent_version_number if parent_version_number > 0 else None,
            "process_guid": process_guid,
            "column_guids": column_guids,
            "columns_count": len(column_guids),
            "propagated_columns": propagated,
            "execution_time_ms": execution_time,
            "similarity_score": similarity_score,
            "data_quality_checks_count": len(dq_guids),
            "quality_summary_added": quality_success if all_checks_data else False,
            "security_classification": "PUBLIC" if is_public else "RESTRICTED",  # 👈 NOUVEAU
            "security_classification_added": security_success  # 👈 NOUVEAU
        }

    except Exception as e:
        logger.error(f"❌ Erreur: {e}", exc_info=True)
        
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

        # 📦 Archivage des fichiers JSON
        try:
            archive_dir = os.path.join(RESULTS_DIR, "archive")
            os.makedirs(archive_dir, exist_ok=True)
            
            archived_count = 0
            if os.path.exists(RESULTS_DIR):
                for f in os.listdir(RESULTS_DIR):
                    if f.endswith('.json') and f != 'archive':
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