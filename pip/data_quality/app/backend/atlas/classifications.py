# atlas/classifications.py

from atlas.client import atlas_post, atlas_get
import logging
import requests

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
    Version corrigée qui vérifie d'abord si la classification existe
    """
    logger.info(f"📤 Envoi classification à Atlas - GUID: {entity_guid}, Type: {classification_name}")
    
    # VÉRIFIER SI LA CLASSIFICATION EXISTE DÉJÀ
    if check_classification_exists(entity_guid, classification_name):
        logger.info(f"✅ Classification '{classification_name}' existe déjà sur l'entité {entity_guid}")
        return {"status": "already_exists", "message": "Classification déjà présente"}
    
    # ESSAI 1: Format bulk (plus fiable selon la doc Atlas V2)
    try:
        payload = {
            "entityGuids": [entity_guid],
            "classification": {
                "typeName": classification_name,
                "attributes": attributes or {}
            }
        }
        
        logger.debug(f"Essai bulk - Payload: {payload}")
        
        response = atlas_post(ATLAS_BULK_CLASSIFICATION_URL, payload)
        
        if response.status_code == 204:  # No Content = succès
            logger.info(f"✅ Classification ajoutée (format bulk) - Status: 204")
            return {"status": "added", "message": "Classification ajoutée"}
        
        # Essayer de lire le JSON si disponible
        try:
            return response.json()
        except:
            return {"status": "added", "message": f"Status: {response.status_code}"}
            
    except Exception as e1:
        logger.error(f"❌ Format bulk échoué: {str(e1)}")
        
        # ESSAI 2: Format single (alternative)
        try:
            url = f"{ATLAS_ENTITY_CLASSIFICATION_URL}/{entity_guid}/classifications"
            payload = {
                "classification": {
                    "typeName": classification_name,
                    "attributes": attributes or {}
                }
            }
            
            response = atlas_post(url, payload)
            
            if response.status_code == 204:
                logger.info(f"✅ Classification ajoutée (format single) - Status: 204")
                return {"status": "added", "message": "Classification ajoutée"}
                
            try:
                return response.json()
            except:
                return {"status": "added", "message": f"Status: {response.status_code}"}
                
        except Exception as e2:
            logger.error(f"❌ Format single échoué: {str(e2)}")
            raise Exception(f"Impossible d'ajouter la classification à Atlas: {str(e2)}")