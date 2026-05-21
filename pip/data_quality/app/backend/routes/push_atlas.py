import sys
from pathlib import Path

# Ajouter la racine du projet au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
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
from db.push_history import PushHistory
from atlas.client import atlas_post, atlas_put, ATLAS_TYPEDEF_URL, ATLAS_SEARCH_URL, atlas_get
from atlas.typedefs import typedefs_payload
from atlas.datasets import create_dataset, link_versioning
from atlas.columns import create_columns
from atlas.signatures import find_smart_parent, calculate_dataset_signature, persist_signature_to_db, compute_similarity_score
from atlas.processes import create_import_process
from atlas.versioning import find_latest_version
from jwt_dependencies import get_current_user
from db.dataset_versions import DatasetVersion
# 👇 IMPORTS MIS À JOUR - Ajout des fonctions de sécurité
from atlas.classifications import (
    add_quality_summary_classification, 
    add_quality_classification,
    add_restricted_classification,  # 👈 NOUVEAU
    add_public_classification        # 👈 NOUVEAU
)
from db.classifications_use_case import apply_classification_use_case
from db.users_crud import get_user_department
from atlas.client import get_typedef_by_name
from atlas.glossary import sync_glossary_terms, assign_terms_to_entity
from db.column_descriptions import ColumnDescription
from db.crud_column_classification_choices import (
    copy_choices_from_previous_version as copy_column_classification_choices_from_previous_version,
    get_choice_dict_by_version as get_column_classification_choice_dict_by_version,
)
from db.dataset_glossary_crud import get_assignments_for_dataset
from db.glossary_crud import get_glossaries_with_categories
from atlas.data_quality import create_data_quality_checks_from_json
from db.data_quality_to_db import save_data_quality_results_from_json


def _apply_saved_glossary_assignments(
    db: Session,
    dataset,
    dataset_qualified_name: str,
    column_info: Dict[str, Dict[str, str]],
):
    results = {"dataset": 0, "columns": 0}
    if not dataset or not dataset.atlas_guid:
        return results

    assignments = get_assignments_for_dataset(db, dataset.id)
    if not assignments:
        return results

    entity_display = dataset_qualified_name or dataset.name
    for assignment in assignments:
        term = assignment.term
        if not term or not term.atlas_guid:
            continue

        column_name = assignment.column_name
        if column_name:
            info = column_info.get(column_name)
            if info and info.get("guid"):
                display = info.get("qualified_name") or column_name
                if assign_terms_to_entity(
                    [term.atlas_guid],
                    info["guid"],
                    "Column",
                    display,
                ):
                    results["columns"] += 1
        else:
            if assign_terms_to_entity(
                [term.atlas_guid],
                dataset.atlas_guid,
                "DataSet",
                entity_display,
            ):
                results["dataset"] += 1

    return results


def _latest_push_history(db: Session, dataset_id: str) -> PushHistory | None:
    return (
        db.query(PushHistory)
        .filter(PushHistory.dataset_id == dataset_id)
        .order_by(desc(PushHistory.pushed_at), desc(PushHistory.id))
        .first()
    )


def _deploy_typedef_with_retry(payload_key: str, entity_def: Dict, max_attempts: int = 4, backoff: float = 1.5):
    attempt = 0
    while attempt < max_attempts:
        try:
            atlas_post(ATLAS_TYPEDEF_URL, {payload_key: [entity_def]})
            return
        except Exception as exc:
            error_text = str(exc)
            if "Failed to get the lock" in error_text and attempt < max_attempts - 1:
                wait = (attempt + 1) * backoff
                logger.warning(f"ℹ️ Lock Atlas détecté (tentative {attempt + 1}), pause {wait:.1f}s")
                time.sleep(wait)
                attempt += 1
                continue
            raise

router = APIRouter()
logger = logging.getLogger("push-atlas")
logger.setLevel(logging.DEBUG)
from settings.config_paths import TMP_DIR, RESULTS_DIR

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
    security_classification = None  # PUBLIC | RESTRICTED (valeur réellement appliquée)
    push_history_row = None
    glossary_stats = {
        "created_terms": 0,
        "existing_terms": 0,
        "total_terms": 0,
        "created_categories": 0,
        "existing_categories": 0,
        "total_categories": 0,
        "glossaries_synced": 0,
        "glossary_guids": [],
        "term_guids": [],
        "dataset_assignments": 0,
        "column_assignments": 0,
    }
    
    try:
        # ----------------------
        # 1️⃣ Récupérer dataset
        # ----------------------
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset introuvable")

        latest_push = _latest_push_history(db, dataset_id)
        if latest_push and latest_push.status == "RUNNING":
            raise HTTPException(
                status_code=409,
                detail="Un push Atlas est déjà en cours pour ce dataset",
            )

        if dataset.atlas_guid and dataset.atlas_synced:
            logger.info("ℹ️ Push ignoré: dataset déjà synchronisé avec Atlas")
            return {
                "message": "Dataset déjà synchronisé avec Atlas",
                "dataset_guid": dataset.atlas_guid,
                "already_synced": True,
            }

        push_history_row = PushHistory(
            id=uuid.uuid4(),
            dataset_id=dataset.id,
            pushed_by=employee_id,
            status="RUNNING",
        )
        db.add(push_history_row)
        db.commit()

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
        deploy_typedefs = os.getenv("ATLAS_DEPLOY_TYPEDEFS", "1") != "0"
        # force_update_typedefs = os.getenv("ATLAS_FORCE_TYPEDEF_UPDATE", "0") == "1"
        force_update_typedefs = True

        if deploy_typedefs:
            logger.info("📦 Déploiement des typedefs Atlas...")

            # ⚡ 1️⃣ Déployer d'abord Column (type de base)
            base_types = ["Column"]
            for type_name in base_types:
                if not force_update_typedefs and get_typedef_by_name(type_name, "entity"):
                    logger.info(f"ℹ️ EntityDef existant (skip): {type_name}")
                    continue
                entityDef = next(e for e in typedefs_payload["entityDefs"] if e["name"] == type_name)
                try:
                    _deploy_typedef_with_retry("entityDefs", entityDef)
                    logger.info(f"✅ EntityDef créé: {type_name}")
                except Exception as e:
                    if "409" not in str(e):
                        raise
                    logger.info(f"ℹ️ EntityDef existant: {type_name}")

            # ⚡ 2️⃣ Déployer DataQualityCheck (dépend de Column)
            if force_update_typedefs or not get_typedef_by_name("DataQualityCheck", "entity"):
                dataQualityDef = next(e for e in typedefs_payload["entityDefs"] if e["name"] == "DataQualityCheck")
                try:
                    _deploy_typedef_with_retry("entityDefs", dataQualityDef)
                    logger.info("✅ EntityDef créé: DataQualityCheck")
                except Exception as e:
                    if "409" not in str(e):
                        raise
                    logger.info("ℹ️ EntityDef existant: DataQualityCheck")
            else:
                logger.info("ℹ️ EntityDef existant (skip): DataQualityCheck")

            # ⚡ 3️⃣ Déployer DataSet (PUT = update possible)
            if force_update_typedefs or not get_typedef_by_name("DataSet", "entity"):
                dataSetDef = next(e for e in typedefs_payload["entityDefs"] if e["name"] == "DataSet")
                try:
                    atlas_put(ATLAS_TYPEDEF_URL, {"entityDefs": [dataSetDef]})
                    logger.info("✅ DataSet déployé")
                except Exception as e:
                    if "409" not in str(e):
                        raise
                    logger.info("ℹ️ DataSet existant")
            else:
                logger.info("ℹ️ EntityDef existant (skip): DataSet")

            # ⚡ 4️⃣ Déployer les relations
            for rel_def in typedefs_payload.get("relationshipDefs", []):
                rel_name = rel_def.get("name")
                if rel_name and not force_update_typedefs and get_typedef_by_name(rel_name, "relationship"):
                    logger.info(f"ℹ️ RelationshipDef existant (skip): {rel_name}")
                    continue
                try:
                    _deploy_typedef_with_retry("relationshipDefs", rel_def)
                    logger.info(f"✅ RelationshipDef: {rel_def['name']}")
                except Exception as e:
                    if "409" not in str(e):
                        raise
                    logger.info(f"ℹ️ RelationshipDef existant: {rel_def['name']}")

            # ⚡ 5️⃣ Déployer les classifications
            for class_def in typedefs_payload.get("classificationDefs", []):
                class_name = class_def.get("name")
                if class_name and not force_update_typedefs and get_typedef_by_name(class_name, "classification"):
                    logger.info(f"ℹ️ Classification existante (skip): {class_name}")
                    continue
                try:
                    _deploy_typedef_with_retry("classificationDefs", class_def)
                    logger.info(f"✅ Classification: {class_def['name']}")
                except Exception as e:
                    if "409" not in str(e):
                        raise
                    logger.info(f"ℹ️ Classification existante: {class_def['name']}")

            logger.info("⏳ Attente de la propagation des typedefs...")
            time.sleep(3)
        else:
            logger.info("⏭️ Déploiement typedefs désactivé via ATLAS_DEPLOY_TYPEDEFS=0")

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

        # ============================================================
        # 5.5️⃣ CRÉER LA VERSION EN BASE AVANT LE DATASET ATLAS
        # ============================================================



        # Déterminer le numéro de version cible
        if parent_guid and parent_version_number > 0:
            target_version_number = parent_version_number + 1
        else:
            last_version = db.query(DatasetVersion).filter(
                DatasetVersion.dataset_id == dataset.id
            ).order_by(DatasetVersion.version_number.desc()).first()
            target_version_number = (last_version.version_number + 1) if last_version else 1

        # Vérifier s'il existe déjà une version temporaire
        existing_temp = db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset.id,
            DatasetVersion.atlas_guid.is_(None)
        ).first()

        if existing_temp and existing_temp.version_number == target_version_number:
            new_version = existing_temp
            logger.info(f"📌 Version temporaire existante réutilisée (v{target_version_number})")
        else:
            # Créer la nouvelle version avec le bon numéro
            new_version = create_dataset_version(
                db=db,
                dataset_id=dataset.id,
                version_number=target_version_number,
                atlas_guid=None,
                parent_version_id=parent_version_id,
                created_by=employee_id,
                change_comment="Version temporaire (en attente de push)",
                source_file=file_path
            )
            logger.info(f"📌 Nouvelle version temporaire créée: v{target_version_number}")

            # Si une ancienne version temporaire existait, transférer ses descriptions
            if existing_temp:
                old_version_id = existing_temp.id
                old_descriptions = db.query(ColumnDescription).filter(
                    ColumnDescription.dataset_version_id == old_version_id
                ).all()
                for desc in old_descriptions:
                    new_desc = ColumnDescription(
                        id=uuid.uuid4(),
                        dataset_version_id=new_version.id,
                        column_name=desc.column_name,
                        description=desc.description,
                        created_by=desc.created_by,
                        created_at=desc.created_at,
                        updated_by=employee_id,
                        updated_at=func.now()
                    )
                    db.add(new_desc)
                db.commit()
                logger.info(f"📌 Descriptions transférées de l'ancienne version v{existing_temp.version_number} vers v{target_version_number}")

                try:
                    copied = copy_column_classification_choices_from_previous_version(
                        db=db,
                        new_version_id=str(new_version.id),
                        previous_version_id=str(old_version_id),
                        user_id=employee_id,
                    )
                    logger.info(
                        f"📌 {copied} classification(s) colonne transférée(s) "
                        f"de v{existing_temp.version_number} vers v{target_version_number}"
                    )
                except Exception as exc:
                    logger.warning(f"⚠️ Impossible de transférer les classifications colonnes: {exc}")

                # ❌ NE PAS SUPPRIMER l'ancienne version temporaire (elle reste en base mais inutilisée)

        # ----------------------
        # 6️⃣ Créer le DataSet dans Atlas (AVEC le numéro de version)
        # ----------------------
        # on récupère le nom du projet grâce à la relation SQLAlchemy et id du produit
        project_name = dataset.project.name if dataset.project else None
        project_id_str = str(dataset.project_id) if dataset.project_id else None

        dataset_guid, dataset_existed = create_dataset(
            hash_value,
            original_name,
            file_path,
            parent_qn,
            df,
            owner_employee_id=dataset.owner_employee_id,
            project_id=project_id_str,
            project_name=project_name,
            description=description,
            version_number=new_version.version_number  # ← MAINTENANT new_version existe
        )

        # 🔥 Récupérer le qualified name du dataset depuis Atlas
        base_url = ATLAS_SEARCH_URL.split("/search")[0]
        try:
            response = atlas_get(f"{base_url}/entity/guid/{dataset_guid}")
            if response.status_code == 200:
                entity_data = response.json()
                dataset_qualified_name = entity_data.get("entity", {}).get("attributes", {}).get("qualifiedName")
                logger.info(f"📛 Qualified name du dataset: {dataset_qualified_name}")
            else:
                dataset_qualified_name = f"{original_name}@{hash_value}"
                logger.warning(f"⚠️ Utilisation fallback: {dataset_qualified_name}")
        except Exception as e:
            dataset_qualified_name = f"{original_name}@{hash_value}"
            logger.warning(f"⚠️ Erreur récupération, fallback: {dataset_qualified_name}")

        glossaries = get_glossaries_with_categories(db)
        if glossaries:
            try:
                stats = sync_glossary_terms(glossaries, db)
                glossary_stats["created_terms"] += stats.get("created_terms", 0)
                glossary_stats["existing_terms"] += stats.get("existing_terms", 0)
                glossary_stats["total_terms"] += stats.get("total_terms", 0)
                glossary_stats["created_categories"] += stats.get("created_categories", 0)
                glossary_stats["existing_categories"] += stats.get("existing_categories", 0)
                glossary_stats["total_categories"] += stats.get("total_categories", 0)
                glossary_stats["glossaries_synced"] += stats.get("glossaries_synced", 0)
                glossary_stats["glossary_guids"].extend(stats.get("glossary_guids", []))
                glossary_stats["term_guids"].extend(stats.get("term_guids", []))

                logger.info(
                    f"📚 {stats.get('glossaries_synced', 0)} glossaire(s) synchronisé(s) "
                    f"· {stats.get('created_terms', 0)} termes créés "
                    f"({stats.get('existing_terms', 0)} existants)"
                )
            except Exception as exc:
                logger.warning(f"⚠️ Échec de la synchronisation des glossaires: {exc}")

        # Mettre à jour l'atlas_guid du dataset
        dataset.atlas_guid = dataset_guid
        dataset.last_modified_by = employee_id
        dataset.last_modified_at = func.now()
        dataset.atlas_qualified_name = dataset_qualified_name
        dataset.atlas_synced = True
        db.commit()
        logger.info(f"✅ Dataset créé: {dataset_guid}")

        # Mettre à jour l'atlas_guid de la version
        new_version.atlas_guid = dataset_guid
        new_version.change_comment = f"Push depuis {file_path}"
        new_version.source_file = file_path
        db.commit()
        db.refresh(new_version)

        # ----------------------
        # 6.5️⃣ Classification sécurité (replace semantics)
        # ----------------------
        try:
            # Source de vérité: visibilité stockée sur le Dataset (choisie à l'upload).
            # NOTE: on garde `is_public` pour compatibilité API, mais il ne pilote plus la décision.
            dataset_visibility = (getattr(dataset, "classification", None) or "").strip().upper()
            if not dataset_visibility:
                # Fallback ultime (ancien comportement) si la base ne contient rien.
                dataset_visibility = "PUBLIC" if is_public else "DEPARTMENT"

            if dataset_visibility == "PUBLIC":
                security_classification = "PUBLIC"
                security_attributes = {"visibility_scope": "ENTERPRISE"}
            else:
                security_classification = "RESTRICTED"
                # IMPORTANT: le département doit dépendre du owner (dataset/projet), pas du pusher.
                owner_emp = getattr(dataset, "owner_employee_id", None) or ""
                if not owner_emp and getattr(dataset, "project", None):
                    owner_emp = getattr(dataset.project, "owner_employee_id", None) or ""
                dept = get_user_department(db, owner_emp) or "UNKNOWN"
                security_attributes = {"visibility_scope": "DEPARTMENT", "department": dept}

            apply_classification_use_case(
                db,
                entity_type="DATASET",
                entity_id=str(dataset.id),
                atlas_guid=dataset_guid,
                classification_name=security_classification,
                attributes=security_attributes,
                user=user,
            )
            security_success = True
            logger.info(
                f"🔒 Classification sécurité appliquée: {security_classification} "
                f"(dataset_visibility={dataset_visibility})"
            )
        except Exception as sec_exc:
            security_success = False
            # Backfill best-effort to avoid returning stale API field values
            security_classification = security_classification or ("PUBLIC" if is_public else "RESTRICTED")
            logger.warning(f"⚠️ Impossible d'appliquer la classification sécurité: {sec_exc}")

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

        # Préparer infos colonnes pour les assignations
        column_info = {}
        for entity in column_entities:
            attrs = entity.get("attributes", {}) or {}
            name = attrs.get("name")
            if not name:
                continue
            column_info[name] = {
                "guid": entity.get("guid"),
                "qualified_name": attrs.get("qualifiedName")
            }

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

        assignment_results = _apply_saved_glossary_assignments(
            db,
            dataset,
            dataset_qualified_name,
            column_info
        )
        glossary_stats["dataset_assignments"] += assignment_results.get("dataset", 0)
        glossary_stats["column_assignments"] += assignment_results.get("columns", 0)
        if assignment_results.get("dataset") or assignment_results.get("columns"):
            logger.info(
                f"📌 {assignment_results['dataset']} assignations dataset et "
                f"{assignment_results['columns']} assignations colonnes envoyées vers Atlas"
            )

        # ----------------------
        # 8.5️⃣ Appliquer les classifications colonnes sauvegardées (depuis describe)
        # ----------------------
        column_classifications_applied = 0
        column_classifications_errors = 0
        try:
            choices = get_column_classification_choice_dict_by_version(db, str(new_version.id))
            if choices:
                logger.info(f"🏷️ Application de {len(choices)} classification(s) colonne sauvegardée(s)...")
            for col_name, class_name in (choices or {}).items():
                guid = column_guids.get(col_name)
                if not guid:
                    continue
                try:
                    apply_classification_use_case(
                        db,
                        entity_type="COLUMN",
                        entity_id=str(dataset.id),
                        atlas_guid=guid,
                        classification_name=class_name,
                        attributes={},
                        user=user,
                        column_name=col_name,
                    )
                    column_classifications_applied += 1
                except Exception as exc:
                    column_classifications_errors += 1
                    logger.warning(f"⚠️ Échec classification {col_name}={class_name}: {exc}")
        except Exception as exc:
            logger.warning(f"⚠️ Impossible d'appliquer les classifications colonnes sauvegardées: {exc}")

        # ----------------------
        # 🔟 ENVOYER LES RÉSULTATS DE QUALITÉ
        # ----------------------
        print("--------------------------------------------------------------------------------------------------")
        logger.info(f"📤 Envoi des résultats de qualité...")

        # Collecter tous les checks pour le résumé global
        all_checks_data = []

        archive_dir = RESULTS_DIR / "archive"
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
            json_path = RESULTS_DIR / jf

            try:
                logger.info(f"📤 Traitement du fichier qualité: {jf}")

                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                dag_run_uuid = data.get("dag_run_id")
                checks = data.get("checks", [])
                all_checks_data.extend(checks)

                guids: List[str] = []
                db_ids: List[str] = []

                # Sauvegarder en PostgreSQL (indépendant d'Atlas)
                try:
                    db_ids = save_data_quality_results_from_json(
                        db=db,
                        dataset_version_id=new_version.id,
                        dag_run_uuid=dag_run_uuid,
                        json_path=str(json_path)
                    )
                    dq_db_ids.extend(db_ids)
                except Exception as db_exc:
                    logger.error(f"❌ Erreur sauvegarde PostgreSQL pour {jf}: {db_exc}", exc_info=True)

                # Envoyer vers Atlas (indépendant de PostgreSQL)
                try:
                    guids = create_data_quality_checks_from_json(
                        dataset_version_guid=new_version.atlas_guid,
                        column_mapping=column_guids,
                        json_path=str(json_path)
                    )
                    dq_guids.extend(guids)
                except Exception as atlas_exc:
                    logger.error(f"❌ Erreur envoi Atlas pour {jf}: {atlas_exc}", exc_info=True)

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
        if push_history_row is not None:
            push_history_row.status = "SUCCESS"
            push_history_row.execution_time_ms = execution_time
            push_history_row.columns_count = columns_count
            push_history_row.rows_count = rows_count
            push_history_row.parent_found = (parent_guid is not None)
            push_history_row.similarity_score = similarity_score if similarity_score > 0 else None
            push_history_row.propagated_columns_count = propagated
            db.commit()
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
            "security_classification": security_classification or ("PUBLIC" if is_public else "RESTRICTED"),
            "security_classification_added": security_success,  # 👈 NOUVEAU
            "glossary_terms_total": glossary_stats.get("total_terms"),
            "glossary_terms_created": glossary_stats.get("created_terms"),
            "glossary_terms_existing": glossary_stats.get("existing_terms"),
            "glossary_categories_total": glossary_stats.get("total_categories"),
            "glossary_categories_created": glossary_stats.get("created_categories"),
            "glossary_categories_existing": glossary_stats.get("existing_categories"),
            "glossaries_synced": glossary_stats.get("glossaries_synced"),
            "glossary_guids": glossary_stats.get("glossary_guids"),
            "glossary_dataset_assignments": glossary_stats.get("dataset_assignments"),
            "glossary_column_assignments": glossary_stats.get("column_assignments"),
            "column_classifications_applied": column_classifications_applied,
            "column_classifications_errors": column_classifications_errors,
        }

    except Exception as e:
        logger.error(f"❌ Erreur: {e}", exc_info=True)
        
        try:
            execution_time = int((time.time() - start_time) * 1000)
            if push_history_row is not None:
                push_history_row.status = "FAILED"
                push_history_row.error_message = str(e)[:500]
                push_history_row.execution_time_ms = execution_time
                db.commit()
                logger.info(f"📊 Échec enregistré dans push_history")
        except Exception as inner_e:
            logger.error(f"❌ Impossible d'enregistrer l'échec: {inner_e}")
        
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # 🧹 Nettoyage TMP
        try:
            for f in os.listdir(TMP_DIR):
                full = TMP_DIR / f
                if full.is_file():  # ou os.path.isfile(full)
                    full.unlink()   # ou os.remove(full)
            logger.debug("🧹 Nettoyage tmp effectué")
        except Exception as e:
            logger.warning(f"⚠️ Erreur nettoyage tmp: {e}")

        # 📦 Archivage des fichiers JSON
        try:
            archive_dir = RESULTS_DIR / "archive"
            archive_dir.mkdir(parents=True, exist_ok=True)  # os.makedirs → mkdir
            
            archived_count = 0
            if RESULTS_DIR.exists():  # os.path.exists → .exists()
                for f in RESULTS_DIR.glob("*.json"):  # plus simple que os.listdir + filter
                    if f.name != 'archive':
                        destination = archive_dir / f"{int(time.time())}_{f.name}"
                        if f.is_file():
                            f.rename(destination)
                            archived_count += 1
                                
            logger.info(f"📦 {archived_count} fichiers qualité archivés")
        except Exception as e:
            logger.warning(f"⚠️ Erreur archivage results: {e}")
