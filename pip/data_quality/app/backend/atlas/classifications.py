# atlas/classifications.py

from atlas.client import atlas_post
import logging

ATLAS_CLASSIFICATION_URL = "http://localhost:21000/api/atlas/v2/entity/guid"

logger = logging.getLogger(__name__)

print("-----------------------------------------------------------------------------------------------")
print("⚠️  Module 'atlas/classifications.py' utilisé - Vérifiez la version Atlas (V2) pour la compatibilité ⚠️")
print("-----------------------------------------------------------------------------------------------")

def add_classification(entity_guid: str, classification_name: str, attributes: dict = None):
    """
    Ajoute une classification Atlas sur une entité (Atlas V2)
    Payload compatible V2 : {"classifications": [...]}
    """
    print("-----------------------------------------------------------------------------------------------")
    print("⚠️  Fonction 'add_classification' utilisée - Vérifiez la version Atlas (V2) pour la compatibilité ⚠️")
    print("-----------------------------------------------------------------------------------------------")
    logger.debug(f"📤 Envoi classification à Atlas - GUID: {entity_guid}, Type: {classification_name}")

    payload = {
        "classifications": [
            {
                "typeName": classification_name
            }
        ]
    }

    if attributes:
        payload["classifications"][0]["attributes"] = attributes

    logger.debug(f"Payload Atlas V2: {payload}")

    url = f"{ATLAS_CLASSIFICATION_URL}/{entity_guid}/classification"
    logger.debug(f"URL Atlas: {url}")

    try:
        response = atlas_post(url, payload)
        logger.debug(f"✅ Réponse Atlas: {response}")
        return response
    except Exception as e:
        logger.error(f"❌ Erreur Atlas: {str(e)}")
        raise
