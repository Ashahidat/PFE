# sync_atlas_classifications.py
import requests
from sqlalchemy.orm import Session
# from sqlalchemy import create_engine
from datetime import datetime
import logging
from typing import Dict, List, Optional
import os
from db.connexion_db import get_db
import sys
from contextlib import contextmanager
from db.connexion_db import get_db
from sqlalchemy.orm import Session


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atlas.classifications import check_classification_exists
from db.classifications_crud import (
    get_classifications_by_entity,
    disable_classification_by_id,
    create_entity_classification
)
from db.classifications import EntityClassification
from db.users_crud import get_user_department_bu
from db.datasets import Dataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ATLAS_BASE_URL = "http://localhost:21000/api/atlas/v2"
ATLAS_USERNAME = "admin"
ATLAS_PASSWORD = "admin"

def get_atlas_classifications(entity_guid: str) -> List[Dict]:
    """
    Récupère les classifications actuelles depuis Atlas pour une entité
    """
    try:
        url = f"{ATLAS_BASE_URL}/entity/guid/{entity_guid}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers, auth=(ATLAS_USERNAME, ATLAS_PASSWORD), verify=False)
        
        if response.status_code == 200:
            entity_data = response.json()
            classifications = entity_data.get("entity", {}).get("classifications", [])
            return classifications
        elif response.status_code == 404:
            logger.warning(f"Entité non trouvée dans Atlas: {entity_guid}")
            return []
        else:
            logger.error(f"Erreur Atlas pour {entity_guid}: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération depuis Atlas: {str(e)}")
        return []

def sync_entity_classifications(db: Session, entity_type: str, entity_id: str, atlas_guid: str):
    """
    Synchronise les classifications d'une entité spécifique
    """
    try:
        logger.info(f"🔍 Synchronisation {entity_type}:{entity_id} (GUID: {atlas_guid})")
        
        # 1. Récupérer les classifications actuelles depuis Atlas
        atlas_classifications = get_atlas_classifications(atlas_guid)
        
        if not atlas_classifications:  # Liste vide ou None
            logger.info(f"Aucune classification dans Atlas pour {atlas_guid}")
            
            # Chercher TOUTES les classifications pour ce GUID (pas seulement par entity_id)
            db_classifications = db.query(EntityClassification).filter(
                EntityClassification.atlas_guid == atlas_guid,
                EntityClassification.is_active.is_(True)
            ).all()
            
            if db_classifications:
                for db_class in db_classifications:
                    disable_classification_by_id(db, db_class.id)
                logger.info(f"Désactivé {len(db_classifications)} classification(s) en base pour {atlas_guid}")
            
            return {"added": 0, "disabled": len(db_classifications), "entity_id": entity_id}
        
        # 2. Récupérer les classifications dans notre base POUR CE GUID
        db_classifications = db.query(EntityClassification).filter(
            EntityClassification.atlas_guid == atlas_guid,
            EntityClassification.is_active.is_(True)
        ).all()

        # 3. Créer des structures pour comparer
        db_class_dict = {
            f"{c.classification_name}": c for c in db_classifications
        }
        
        atlas_class_dict = {}
        for atlas_class in atlas_classifications:
            class_name = atlas_class.get("typeName")
            # Extraire les attributs pertinents
            attributes = atlas_class.get("attributes", {})
            # Garder seulement certains attributs si nécessaire
            filtered_attrs = {}
            if "level" in attributes:
                filtered_attrs["level"] = attributes.get("level")
            if "confidence" in attributes:
                filtered_attrs["confidence"] = attributes.get("confidence")
            
            atlas_class_dict[class_name] = {
                "name": class_name,
                "attributes": filtered_attrs,
                "validityPeriods": atlas_class.get("validityPeriods", [])
            }
        
        atlas_class_names = set(atlas_class_dict.keys())
        
        # 4. Identifier les différences
        classifications_to_add = []
        classifications_to_disable = []
        
        # a) Vérifier ce qui existe dans Atlas mais pas dans notre base
        for class_name, atlas_class in atlas_class_dict.items():
            if class_name not in db_class_dict:
                classifications_to_add.append(atlas_class)
        
        # b) Vérifier ce qui existe dans notre base mais pas dans Atlas
        for class_name, db_class in db_class_dict.items():
            if class_name not in atlas_class_names:
                classifications_to_disable.append(db_class.id)
        
        # 5. Appliquer les changements
        sync_results = {
            "added": 0,
            "disabled": 0,
            "entity_id": entity_id,
            "entity_type": entity_type
        }
        
        # Utiliser un utilisateur système pour l'audit
        system_user = {
            "employee_id": "SYSTEM_SYNC",
            "sub": "SYSTEM_SYNC"
        }
        
        # Désactiver les classifications manquantes
        if classifications_to_disable:
            logger.info(f"🔄 Désactivation de {len(classifications_to_disable)} classification(s) pour {entity_id}")
            for class_id in classifications_to_disable:
                try:
                    disable_classification_by_id(db, class_id)
                    sync_results["disabled"] += 1
                except Exception as e:
                    logger.error(f"Erreur désactivation classification {class_id}: {str(e)}")
        
        # Ajouter les nouvelles classifications
        if classifications_to_add:
            logger.info(f"➕ Ajout de {len(classifications_to_add)} classification(s) pour {entity_id}")
            
            # Récupérer les infos de l'utilisateur système
            dept_bu = get_user_department_bu(db, "SYSTEM_SYNC")
            department, business_unit = dept_bu if dept_bu else ("SYSTEM", "SYSTEM")
            
            for classification in classifications_to_add:
                try:
                    # Vérifier si la classification existe déjà (au cas où)
                    if check_classification_exists(atlas_guid, classification["name"]):
                        # Créer l'enregistrement en base
                        new_classification = create_entity_classification(
                            db=db,
                            entity_type=entity_type,
                            entity_id=entity_id,
                            atlas_guid=atlas_guid,
                            classification_name=classification["name"],
                            classification_attributes=classification.get("attributes", {}),
                            applied_by="SYSTEM_SYNC",
                            department=department,
                            business_unit=business_unit
                        )
                        
                        db.flush()
                        sync_results["added"] += 1
                        logger.info(f"  ✓ Ajouté: {classification['name']}")
                    else:
                        logger.warning(f"  ⚠ Classification {classification['name']} non trouvée dans Atlas")
                        
                except Exception as e:
                    logger.error(f"Erreur ajout classification {classification['name']}: {str(e)}")
        
        logger.info(f"✅ Synchronisation terminée pour {entity_id}: {sync_results}")
        return sync_results
        
    except Exception as e:
        logger.error(f"❌ Erreur synchronisation {entity_id}: {str(e)}", exc_info=True)
        return None

def sync_all_classifications(db: Session = None):
    """
    Fonction principale de synchronisation
    """
    close_db = False

    if db is None:
        close_db = True
        db = next(get_db())  # 🔥 UTILISE LA CONNEXION CENTRALE

    try:
        logger.info("🔄 Début synchronisation globale des classifications")

        datasets = (
            db.query(Dataset)
            .filter(Dataset.atlas_guid.isnot(None))
            .all()
        )

        logger.info(f"📊 {len(datasets)} datasets à synchroniser")

        for dataset in datasets:
            sync_entity_classifications(
                db=db,
                entity_type="DATASET",
                entity_id=str(dataset.id),
                atlas_guid=dataset.atlas_guid
            )

        db.commit()
        logger.info("✅ Synchronisation terminée avec succès")

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur synchronisation globale: {str(e)}", exc_info=True)
        raise

    finally:
        if close_db:
            db.close()


def sync_specific_entity(entity_type: str, entity_id: str, db: Session):
    """
    Synchronise une entité spécifique
    """
    try:
        if entity_type.upper() == "DATASET":
            entity = db.query(Dataset).filter(Dataset.id == entity_id).first()
        elif entity_type.upper() == "COLUMN":
            entity = db.query(Column).filter(Column.id == entity_id).first()
        else:
            logger.error(f"Type d'entité non supporté: {entity_type}")
            return None
        
        if not entity or not entity.atlas_guid:
            logger.error(f"Entité {entity_type}:{entity_id} non trouvée ou sans GUID Atlas")
            return None
        
        return sync_entity_classifications(
            db=db,
            entity_type=entity_type,
            entity_id=entity_id,
            atlas_guid=entity.atlas_guid
        )
        
    except Exception as e:
        logger.error(f"Erreur synchronisation {entity_type}:{entity_id}: {str(e)}")
        return None

if __name__ == "__main__":
    # Mode standalone
    sync_all_classifications()