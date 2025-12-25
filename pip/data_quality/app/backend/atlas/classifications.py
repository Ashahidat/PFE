# atlas/classifications.py

from atlas.client import atlas_post
import logging

# Deux endpoints possibles selon la version d'Atlas
ATLAS_BULK_CLASSIFICATION_URL = "http://localhost:21000/api/atlas/v2/entity/bulk/classification"
ATLAS_ENTITY_CLASSIFICATION_URL = "http://localhost:21000/api/atlas/v2/entity/guid"

logger = logging.getLogger(__name__)

def add_classification(entity_guid: str, classification_name: str, attributes: dict = None):
    """
    Version adaptative pour Atlas V2
    Essaie d'abord l'endpoint single entity, puis bulk si besoin
    """
    logger.info(f"📤 Envoi classification à Atlas - GUID: {entity_guid}, Type: {classification_name}")
    
    # ESSAI 1: Format single entity (le plus courant pour Atlas V2)
    try:
        url = f"{ATLAS_ENTITY_CLASSIFICATION_URL}/{entity_guid}/classifications"
        payload = [
            {
                "typeName": classification_name,
                "attributes": attributes or {}
            }
        ]
        
        logger.debug(f"Essai 1 - URL: {url}")
        logger.debug(f"Essai 1 - Payload: {payload}")
        
        response = atlas_post(url, payload)
        logger.info(f"✅ Classification ajoutée (format single) - Status: {response.status_code}")
        return response.json()
        
    except Exception as e:
        logger.warning(f"⚠️ Format single échoué: {str(e)}. Essai format bulk...")
        
        # ESSAI 2: Format bulk
        try:
            url = ATLAS_BULK_CLASSIFICATION_URL
            payload = {
                "entityGuids": [entity_guid],
                "classification": {
                    "typeName": classification_name,
                    "attributes": attributes or {}
                }
            }
            
            logger.debug(f"Essai 2 - URL: {url}")
            logger.debug(f"Essai 2 - Payload: {payload}")
            
            response = atlas_post(url, payload)
            logger.info(f"✅ Classification ajoutée (format bulk) - Status: {response.status_code}")
            return response.json()
            
        except Exception as e2:
            logger.error(f"❌ Les deux formats ont échoué: {str(e2)}")
            raise Exception(f"Impossible d'ajouter la classification à Atlas: {str(e2)}")