# atlas/source_files.py
import logging
import time
from atlas.client import atlas_get, atlas_post, ATLAS_SEARCH_URL, ATLAS_ENTITY_BULK_URL, ATLAS_RELATIONSHIP_URL

logger = logging.getLogger("atlas.source_files")

def create_or_get_source_file(file_hash, original_name, file_path, uploader, file_size=None):
    """
    Crée ou récupère un SourceFile dans Atlas.
    qualifiedName = file_hash (unique par fichier)
    """
    qn = f"{original_name}_{file_hash[:8]}" 
    
    # 1. Vérifier si existe déjà
    try:
        search_res = atlas_get(f"{ATLAS_SEARCH_URL}?typeName=SourceFile&query=qualifiedName:{qn}")
        entities = search_res.json().get("entities", [])
        
        if entities:
            existing_guid = entities[0].get("guid")
            logger.info(f"SourceFile déjà existant -> {existing_guid}")
            return existing_guid, True
    except:
        pass  # Si erreur, on continue pour créer

    # 2. Créer le SourceFile
    payload = {
        "entities": [{
            "typeName": "SourceFile",
            "attributes": {
                "qualifiedName": qn,
                "name": original_name,
                "originalName": original_name,
                "fileHash": file_hash,
                "filePath": file_path,
                "fileSize": file_size,
                "uploadDate": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "uploader": uploader
            },
            "guid": "-200"
        }]
    }
    
    res = atlas_post(ATLAS_ENTITY_BULK_URL, payload)
    guid = res.json().get("guidAssignments", {}).get("-200")
    
    if not guid:
        raise Exception("Pas de GUID pour SourceFile")
    
    logger.info(f"SourceFile créé: {guid}")
    return guid, False


def link_source_file(source_file_guid, dataset_guid):
    """
    Crée une relation source_of entre SourceFile et DataSet
    """
    if not source_file_guid or not dataset_guid:
        return None
    
    relationship_payload = {
        "typeName": "source_of",
        "end1": {"guid": source_file_guid, "typeName": "SourceFile"},
        "end2": {"guid": dataset_guid, "typeName": "DataSet"},
        "attributes": {"importDate": "now()"}
    }
    
    try:
        res = atlas_post(ATLAS_RELATIONSHIP_URL, relationship_payload)
        return res.json()
    except Exception as e:
        logger.error(f"Erreur relation source_of: {e}")
        return None