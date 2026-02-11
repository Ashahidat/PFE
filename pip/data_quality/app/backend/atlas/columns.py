# atlas/columns.py

from atlas.client import atlas_post, ATLAS_ENTITY_BULK_URL
import logging
import json
import hashlib
from atlas.column_matching import ColumnMatcher  # 🆕 Juste changer l'import

logger = logging.getLogger(__name__)

def create_columns(df, dataset_guid, dataset_qualified_name, logical_column_ids=None, parent_dataset_guid=None):
    """
    Crée les colonnes dans Atlas avec matching intelligent
    logical_column_ids: dict {col_name: logical_column_id} (optionnel)
    parent_dataset_guid: GUID du dataset parent pour le matching (optionnel)
    """
    entities = []
    temp_to_name = {}  # Mapping temporaire {temp_guid: column_name}
    
    # 🆕 Initialiser le matcher si parent_dataset_guid fourni
    matcher = ColumnMatcher() if parent_dataset_guid else None
    
    for idx, col_name in enumerate(df.columns):
        temp_guid = f"-col-{idx}"
        
        # 🆕 DÉTERMINATION INTELLIGENTE DU logicalColumnId
        logical_id = None
        
        # 1. Priorité: logical_column_ids fourni manuellement
        if logical_column_ids and col_name in logical_column_ids:
            logical_id = logical_column_ids[col_name]
            logger.info(f"📝 '{col_name}' → logicalColumnId manuel: '{logical_id}'")
        
        # 2. Priorité: Matching intelligent avec le parent
        elif matcher and parent_dataset_guid:
            # Créer une entité temporaire pour le matching
            temp_entity = {
                "guid": temp_guid,
                "attributes": {
                    "name": col_name,
                    "type": str(df.dtypes[idx]),
                    "qualifiedName": f"{dataset_qualified_name}.{col_name}",
                    "position": idx
                }
            }
            
            # 🆕 Chercher le logicalColumnId correspondant dans le parent
            logical_id = matcher.propagate_logical_column_id(temp_entity, parent_dataset_guid)
            
            if logical_id:
                logger.info(f"🔗 '{col_name}' → logicalColumnId propagé: '{logical_id}'")
        
        # 3. Fallback: Nouveau basé sur signature unique
        if not logical_id:
            # Créer un ID unique mais stable basé sur plusieurs critères
            signature_data = {
                "name": col_name.lower(),
                "type": str(df.dtypes[idx]),
                "position": idx,
                "dataset": dataset_guid[:8]  # Premier partie du GUID dataset
            }
            signature_str = json.dumps(signature_data, sort_keys=True)
            logical_id = f"col_{hashlib.sha256(signature_str.encode()).hexdigest()[:12]}"
            logger.info(f"🆕 '{col_name}' → nouveau logicalColumnId: '{logical_id}'")
        
        # Créer l'entité colonne
        entities.append({
            "typeName": "Column",
            "attributes": {
                "name": col_name,
                "qualifiedName": f"{dataset_qualified_name}.{col_name}",
                "logicalColumnId": logical_id,
                "type": str(df.dtypes[idx]),
                "dataset": {"typeName": "DataSet", "guid": dataset_guid},
                "position": idx  # 🆕 Stocker la position pour futur matching
            },
            "guid": temp_guid
        })
        temp_to_name[temp_guid] = col_name

    if not entities:
        logger.warning("❌ Aucune entité colonne à créer")
        return {}

    try:
        # Envoyer les colonnes à Atlas
        res = atlas_post(ATLAS_ENTITY_BULK_URL, {"entities": entities})
        
        if res.status_code not in (200, 201):
            logger.error(f"❌ Erreur API Atlas: {res.status_code} - {res.text}")
            return {}
        
        assignments = res.json().get("guidAssignments", {})
        
        # Mapping final {col_name: guid_atlas}
        column_mapping = {}
        for temp_guid, guid in assignments.items():
            if temp_guid in temp_to_name:
                col_name = temp_to_name[temp_guid]
                column_mapping[col_name] = guid
                
                # Récupérer le logicalColumnId correspondant
                for entity in entities:
                    if entity.get("guid") == temp_guid:
                        logical_id = entity.get("attributes", {}).get("logicalColumnId")
                        logger.info(f"✅ Colonne '{col_name}' → GUID: {guid}, logicalColumnId: {logical_id}")
                        break
        
        logger.info(f"🎯 {len(column_mapping)} colonnes créées dans Atlas")
        return column_mapping

    except Exception as e:
        logger.error(f"❌ Erreur création colonnes Atlas: {e}", exc_info=True)
        return {}