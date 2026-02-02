# atlas/classifications.py

from atlas.client import atlas_post, atlas_get
import logging
import requests 
import time  

ATLAS_BULK_CLASSIFICATION_URL = "http://localhost:21000/api/atlas/v2/entity/bulk/classification"
ATLAS_ENTITY_CLASSIFICATION_URL = "http://localhost:21000/api/atlas/v2/entity/guid"

logger = logging.getLogger(__name__)

def check_classification_exists(entity_guid: str, classification_name: str) -> bool:
    """
    Vérifie si une classification existe déjà sur une entité
    """
    try:
        url = f"{ATLAS_ENTITY_CLASSIFICATION_URL}/{entity_guid}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers, verify=False)
        
        if response.status_code == 200:
            entity_data = response.json()
            entity = entity_data.get("entity", {})
            classifications = entity.get("classifications", [])
            
            # Vérifier si la classification existe déjà
            for classification in classifications:
                if classification.get("typeName") == classification_name:
                    return True
        return False
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification: {str(e)}")
        return False


def add_classification(entity_guid: str, classification_name: str, attributes: dict = None):
    """
    Essaie plusieurs fois avec des délais car Atlas est asynchrone
    """
    logger.info(f"📤 Envoi classification à Atlas - GUID: {entity_guid}, Type: {classification_name}")
    
    retries = 3
    
    for attempt in range(retries):
        try:
            # Attente progressive : 3s, 6s, 9s...
            if attempt > 0:
                wait_time = 3 * attempt
                logger.info(f"⏳ Tentative {attempt+1}/{retries}, attente {wait_time}s...")
                time.sleep(wait_time)
            
            # VÉRIFIER SI LA CLASSIFICATION EXISTE DÉJÀ
            if check_classification_exists(entity_guid, classification_name):
                logger.info(f"✅ Classification '{classification_name}' existe déjà")
                return {"status": "already_exists", "message": "Classification déjà présente"}
            
            # ESSAI 1: Format bulk
            try:
                payload = {
                    "classification": {
                        "typeName": classification_name,
                        "attributes": attributes or {}
                    },
                    "entityGuids": [entity_guid]
                }
                
                logger.debug(f"Essai bulk - Tentative {attempt+1}")
                response = atlas_post(ATLAS_BULK_CLASSIFICATION_URL, payload)
                
                if response.status_code == 204:
                    logger.info(f"✅ Classification ajoutée (bulk)")
                    return {"status": "added", "message": "Classification ajoutée"}
                
                # Si 400 "already associated", c'est OK
                if response.status_code == 400 and "already associated" in response.text:
                    logger.info("✅ Classification déjà associée")
                    return {"status": "already_exists", "message": "Classification déjà présente"}
                    
                # Sinon, essayer format single
                raise Exception(f"Bulk: {response.status_code} - {response.text[:100]}")
                
            except Exception as e1:
                logger.warning(f"Bulk échoué: {str(e1)[:100]}")
                
                # ESSAI 2: Format single
                try:
                    url = f"{ATLAS_ENTITY_CLASSIFICATION_URL}/{entity_guid}/classifications"
                    
                    # IMPORTANT: Format ARRAY pour single endpoint
                    payload = [{  # TABLEAU !
                        "typeName": classification_name,
                        "attributes": attributes or {}
                    }]
                    
                    logger.debug(f"Essai single - Tentative {attempt+1}")
                    response = atlas_post(url, payload)
                    
                    if response.status_code == 204:
                        logger.info(f"✅ Classification ajoutée (single)")
                        return {"status": "added", "message": "Classification ajoutée"}
                    
                    # Si 400 "already associated", c'est OK
                    if response.status_code == 400 and "already associated" in response.text:
                        logger.info("✅ Classification déjà associée (single)")
                        return {"status": "already_exists", "message": "Classification déjà présente"}
                    
                    raise Exception(f"Single: {response.status_code} - {response.text[:100]}")
                    
                except Exception as e2:
                    logger.warning(f"Single échoué: {str(e2)[:100]}")
                    raise Exception(f"Bulk: {e1}, Single: {e2}")
            
        except Exception as e:
            # Si "not found" et pas dernière tentative, réessayer
            if ("invalid/not found" in str(e) or "404" in str(e)) and attempt < retries - 1:
                logger.warning(f"Entité non trouvée, nouvelle tentative dans {3*(attempt+1)}s...")
                continue
            # Si "already exists", c'est OK
            elif "already associated" in str(e) or "already exists" in str(e):
                logger.info("✅ Classification déjà présente")
                return {"status": "already_exists", "message": "Classification déjà présente"}
            else:
                # Dernière tentative échouée
                if attempt == retries - 1:
                    logger.error(f"❌ Échec après {retries} tentatives: {str(e)}")
                    raise Exception(f"Impossible d'ajouter la classification à Atlas après {retries} tentatives: {str(e)}")
    
    return {"status": "error", "message": "Échec après plusieurs tentatives"}