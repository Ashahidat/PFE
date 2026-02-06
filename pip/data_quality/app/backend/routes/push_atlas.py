# routes/push_atlas.py 

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import logging
import os
from datetime import datetime

from config import spark
from db.connexion_db import get_db
from db.datasets import Dataset
from atlas.client import atlas_post, atlas_put, atlas_get, ATLAS_TYPEDEF_URL, ATLAS_ENTITY_BULK_URL, ATLAS_RELATIONSHIP_URL
from atlas.typedefs import typedefs_payload
from atlas.datasets import create_dataset, link_versioning
from atlas.columns import create_columns
from atlas.signatures import find_smart_parent, calculate_dataset_signature
from jwt_dependencies import get_current_user
from atlas.signatures import persist_signature_to_db


router = APIRouter()
logger = logging.getLogger("push-atlas")
logger.setLevel(logging.DEBUG)

TMP_DIR = "/home/ashahi/PFE/pip/data_quality/tmp"
os.makedirs(TMP_DIR, exist_ok=True)


def ensure_lineage_types():
    """
    S'assure que TOUS les types nécessaires sont définis dans Atlas
    """
    try:
        logger.info("🔧 Vérification/création de TOUS les types nécessaires...")
        
        # Types ABSOLUMENT nécessaires
        required_types = ["Column", "FileUploadProcess"]
        
        for type_name in required_types:
            try:
                # VÉRIFICATION CORRECTE : Chercher une entité de ce type
                res = atlas_get(f"{ATLAS_SEARCH_URL}?typeName={type_name}&query=*")
                entities = res.json().get("entities", [])
                if entities:
                    logger.info(f"✅ {type_name} existe déjà (entités trouvées)")
                else:
                    # Pas d'entités, mais le type pourrait quand même exister
                    logger.info(f"ℹ️  Aucune entité {type_name} trouvée, vérification du type...")
                    create_single_type(type_name)
            except Exception as e:
                # Le type n'existe probablement pas, le créer
                logger.warning(f"⚠️ {type_name} probablement inexistant: {e}, création...")
                create_single_type(type_name)
        
        logger.info("✅ Tous les types sont prêts")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur vérification types: {e}")
        return False

def create_single_type(type_name):
    """Crée un seul type dans Atlas"""
    from atlas.typedefs import typedefs_payload
    
    # Trouver la définition du type
    type_def = None
    for entity_def in typedefs_payload.get("entityDefs", []):
        if entity_def.get("name") == type_name:
            type_def = entity_def
            break
    
    if not type_def:
        logger.error(f"❌ Définition non trouvée pour {type_name}")
        return False
    
    try:
        # Créer le TYPE dans Atlas
        payload = {"entityDefs": [type_def]}
        res = atlas_post(ATLAS_TYPEDEF_URL, payload)
        
        if res.status_code in [200, 201]:
            logger.info(f"✅ Type {type_name} créé avec succès")
            return True
        elif res.status_code == 409:
            logger.info(f"✅ Type {type_name} existe déjà (conflit)")
            return True
        else:
            logger.error(f"❌ Erreur création type {type_name}: {res.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Exception création type {type_name}: {e}")
        return False


        


@router.post("/push-atlas/{dataset_id}")
def push_atlas(dataset_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        logger.info("=" * 80)
        logger.info("🚀 DÉBUT PUSH ATLAS - VERSION CORRIGÉE")
        logger.info(f"User: {user.get('sub', 'unknown')}")
        logger.info(f"Dataset ID: {dataset_id}")
        logger.info("=" * 80)
        
        # ============ ÉTAPE 0 : TYPES D'ABORD ============
        logger.info("🔧 ÉTAPE 0: Vérification/création des types Atlas...")
        if not ensure_lineage_types():
            logger.error("❌ Problème avec les types Atlas")
            # Création d'urgence
            logger.info("🆘 Création d'urgence des types...")
            create_emergency_types()
        
        # 1️⃣ Récupérer dataset
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset introuvable")

        file_path = dataset.file_path
        hash_value = dataset.hash
        original_name = dataset.name

        # 2️⃣ Lire le PARQUET
        df = spark.read.parquet(file_path)

        # 3️⃣ Signature
        signature = calculate_dataset_signature(df, original_name)
        persist_signature_to_db(db, dataset.id, signature)

        # 4️⃣ Parent intelligent
        parent_guid, parent_qn = find_smart_parent(df, original_name)

        # 5️⃣ Créer dataset Atlas
        dataset_guid, existed = create_dataset(
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

        logger.info(f"✅ Dataset créé dans Atlas: {dataset_guid}")

        # 6️⃣ Versioning
        if parent_guid and parent_guid != dataset_guid:
            link_versioning(parent_guid, dataset_guid)

        # 7️⃣ Colonnes
        column_guids = create_columns(df, dataset_guid, hash_value)
        logger.info(f"✅ Colonnes créées: {len(column_guids)}")
        
        # 8️⃣ FileUploadProcess
        logger.info("🎯 Création FileUploadProcess...")
        
        try:
            upload_process_id = f"upload_{dataset_guid}"
            upload_process_payload = {
                "entities": [{
                    "typeName": "FileUploadProcess",
                    "attributes": {
                        "qualifiedName": upload_process_id,
                        "name": f"Upload: {original_name}",
                        "filename": original_name,
                        "uploadedBy": user.get("sub", "unknown"),
                        "uploadTimestamp": datetime.now().isoformat()
                    },
                    "guid": f"-upload-{upload_process_id}"
                }]
            }
            
            res = atlas_post(ATLAS_ENTITY_BULK_URL, upload_process_payload)
            
            if res.status_code == 200:
                res_data = res.json()
                upload_process_guid = res_data.get("guidAssignments", {}).get(f"-upload-{upload_process_id}")
                
                if upload_process_guid:
                    logger.info(f"✅ FileUploadProcess créé: {upload_process_guid}")
                    
                    # Mettre à jour le dataset avec sourceUpload
                    update_payload = {
                        "entities": [{
                            "typeName": "DataSet",
                            "guid": dataset_guid,
                            "attributes": {
                                "sourceUpload": {
                                    "guid": upload_process_guid,
                                    "typeName": "FileUploadProcess"
                                }
                            }
                        }]
                    }
                    
                    atlas_post(ATLAS_ENTITY_BULK_URL, update_payload)
                    logger.info(f"✅ Dataset mis à jour avec sourceUpload")
                    
        except Exception as e:
            logger.error(f"⚠️ Erreur création FileUploadProcess: {e}")

        message = "Ce dataset existe déjà dans Atlas." if existed else "Dataset ajouté à Atlas avec succès !"

        return {
            "message": message,
            "dataset_guid": dataset_guid,
            "parent_guid": parent_guid,
            "column_guids": column_guids,
            "upload_process_created": "upload_process_guid" in locals()
        }

    except Exception as e:
        logger.error(f"❌ Erreur push-atlas: {e}", exc_info=True)
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

def create_emergency_types():
    """Crée les types manquants en cas d'urgence"""
    try:
        logger.info("🆘 Création d'urgence du type Column...")
        
        column_type = {
            "entityDefs": [{
                "name": "Column",
                "superTypes": ["Asset"],
                "attributeDefs": [
                    {"name": "type", "typeName": "string", "isOptional": True},
                    {
                        "name": "dataset",
                        "typeName": "DataSet",
                        "isOptional": False,
                        "cardinality": "SINGLE"
                    }
                ]
            }]
        }
        
        res = atlas_post(ATLAS_TYPEDEF_URL, column_type)
        logger.info(f"✅ Column type créé: {res.status_code}")
        
    except Exception as e:
        logger.error(f"❌ Échec création d'urgence: {e}")