from atlas.client import atlas_get, ATLAS_SEARCH_URL, atlas_post
import logging
import re
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

class ColumnMatcher:
    def __init__(self):
        self.base_url = ATLAS_SEARCH_URL.split("/search")[0]
    
    def _get_dataset_columns(self, dataset_guid: str):
        """Récupère les colonnes d'un dataset"""
        try:
            search_payload = {
                "typeName": "Column",
                "entityFilters": {
                    "condition": "AND",
                    "criterion": [{
                        "attributeName": "dataset",
                        "operator": "eq",
                        "attributeValue": dataset_guid
                    }]
                },
                "limit": 100
            }
            response = atlas_post(ATLAS_SEARCH_URL, search_payload)
            if response.status_code == 200:
                data = response.json()
                columns = data.get("entities", [])
                logger.info(f"📦 {len(columns)} colonnes trouvées pour {dataset_guid[:8]}...")
                return columns
            else:
                logger.warning(f"Erreur recherche colonnes: {response.status_code}")
                return []
        except Exception as e:
            logger.warning(f"⚠️ Erreur: {e}")
            return []
    
    def propagate_logical_column_id(self, temp_column_entity, parent_dataset_guid):
        """Trouve un logicalColumnId correspondant"""
        try:
            col_name = temp_column_entity.get("attributes", {}).get("name", "")
            col_type = temp_column_entity.get("attributes", {}).get("type", "")
            
            if not col_name:
                return None
            
            parent_columns = self._get_dataset_columns(parent_dataset_guid)
            
            if not parent_columns:
                return None
            
            best_logical_id = None
            best_score = 0
            
            for col in parent_columns:
                attrs = col.get("attributes", {})
                parent_name = attrs.get("name", "")
                parent_logical_id = attrs.get("logicalColumnId", "")
                
                if not parent_logical_id:
                    continue
                
                # Score de similarité
                name_score = fuzz.ratio(col_name.lower(), parent_name.lower()) / 100.0
                
                if name_score > best_score:
                    best_score = name_score
                    best_logical_id = parent_logical_id
            
            if best_score >= 0.82:
                logger.info(f"✅ Match fuzzy: {col_name} -> {best_logical_id[:8]}... (score: {best_score:.3f})")
                return best_logical_id
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erreur: {e}")
            return None