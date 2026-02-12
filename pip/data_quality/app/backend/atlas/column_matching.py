# atlas/column_matching.py

"""
Logique robuste de matching des colonnes entre versions de datasets
"""
from atlas.client import atlas_get, ATLAS_SEARCH_URL
import hashlib
import json
import logging
import re
from rapidfuzz import fuzz
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

class ColumnMatcher:
    def __init__(self):
        self.base_url = ATLAS_SEARCH_URL.split("/search")[0]
    
    def propagate_logical_column_id(self, temp_column_entity: Dict, parent_dataset_guid: str) -> Optional[str]:
        """
        Si une colonne correspondante est trouvée dans le parent,
        propage son logicalColumnId à la colonne actuelle.
        
        À utiliser quand une colonne n'a pas été trouvée dans le mapping manuel.
        """
        try:
            # Récupérer le nom et type de la colonne actuelle
            col_name = temp_column_entity.get("attributes", {}).get("name", "")
            col_type = temp_column_entity.get("attributes", {}).get("type", "")
            col_position = temp_column_entity.get("attributes", {}).get("position", 0)
            
            if not col_name:
                logger.warning("❌ Nom de colonne vide, pas de matching possible")
                return None
            
            # Récupérer toutes les colonnes du dataset parent
            parent_columns = self._get_dataset_columns(parent_dataset_guid)
            
            if not parent_columns:
                logger.info(f"ℹ️ Aucune colonne trouvée dans le dataset parent")
                return None
            
            logger.info(f"🔍 Matching intelligent pour '{col_name}' parmi {len(parent_columns)} colonnes parent...")
            
            # Calculer les scores pour chaque colonne parent
            best_logical_id = None
            best_score = 0
            best_match_details = {}
            
            for col in parent_columns:
                col_attrs = col.get("attributes", {})
                parent_name = col_attrs.get("name", "")
                parent_type = col_attrs.get("type", "")
                parent_logical_id = col_attrs.get("logicalColumnId", "")
                parent_position = col_attrs.get("position", 0)
                
                if not parent_logical_id:
                    continue
                
                # 1. Calculer la similarité du nom
                name_similarity = self._calculate_name_similarity(col_name, parent_name)
                
                # 2. Similarité du type de données
                type_similarity = self._calculate_type_similarity(col_type, parent_type)
                
                # 3. Bonus pour position identique ou proche
                position_similarity = self._calculate_position_similarity(col_position, parent_position)
                
                # Score final pondéré
                total_score = (name_similarity * 0.70) + (type_similarity * 0.20) + (position_similarity * 0.10)
                
                if total_score > best_score:
                    best_score = total_score
                    best_logical_id = parent_logical_id
                    best_match_details = {
                        'parent_name': parent_name,
                        'parent_type': parent_type,
                        'parent_position': parent_position,
                        'name_score': name_similarity,
                        'type_score': type_similarity,
                        'position_score': position_similarity
                    }
            
            # Seuil minimum pour considérer un match
            if best_score >= 0.82:  # Seuil élevé pour éviter faux positifs
                logger.info(f"✅ Match trouvé pour '{col_name}':")
                logger.info(f"   → Parent: '{best_match_details['parent_name']}' (pos: {best_match_details['parent_position']})")
                logger.info(f"   → Score: {best_score:.3f} (nom: {best_match_details['name_score']:.3f}, type: {best_match_details['type_score']:.3f})")
                logger.info(f"   → logical_id: {best_logical_id}")
                return best_logical_id
            else:
                logger.info(f"❌ Pas de match pour '{col_name}' (meilleur score: {best_score:.3f})")
                if best_match_details:
                    logger.info(f"   Meilleur candidat: '{best_match_details['parent_name']}' (score: {best_score:.3f})")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erreur dans propagate_logical_column_id: {e}", exc_info=True)
            return None
    
    def _get_dataset_columns(self, dataset_guid: str) -> List[Dict]:
        """Récupère toutes les colonnes d'un dataset"""
        try:
            # Chercher directement les colonnes associées au dataset
            search_query = f'__typeName:"Column" AND dataset.guid:"{dataset_guid}"'
            res = atlas_get(f"{ATLAS_SEARCH_URL}?typeName=Column&query={search_query}")
            dataset_columns = res.json().get("entities", [])
            
            logger.info(f"📦 {len(dataset_columns)} colonnes trouvées pour dataset {dataset_guid[:8]}...")
            return dataset_columns
            
        except Exception as e:
            logger.warning(f"⚠️ Erreur récupération colonnes dataset: {e}")
            return []
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calcule la similarité robuste entre deux noms de colonnes
        Combine plusieurs stratégies pour plus de robustesse
        """
        if not name1 or not name2:
            return 0.0
        
        # Normalisation
        norm1 = self._normalize_column_name(name1)
        norm2 = self._normalize_column_name(name2)
        
        # 1. Exact match après normalisation
        if norm1 == norm2:
            return 1.0
        
        # 2. Match case-insensitive
        if name1.lower() == name2.lower():
            return 0.95
        
        # 3. Vérifier si un nom est un suffixe/prefixe de l'autre
        if norm1 in norm2 or norm2 in norm1:
            len_ratio = min(len(norm1), len(norm2)) / max(len(norm1), len(norm2))
            if len_ratio > 0.7:  # Les noms ont des tailles similaires
                return 0.85
        
        # 4. Multiples algorithmes de fuzzy matching
        scores = []
        
        # Levenshtein distance
        scores.append(fuzz.ratio(norm1, norm2) / 100.0)
        
        # Meilleur match partiel (pour "customer_id" vs "cust_id")
        scores.append(fuzz.partial_ratio(norm1, norm2) / 100.0)
        
        # Match indépendant de l'ordre des mots
        scores.append(fuzz.token_sort_ratio(norm1, norm2) / 100.0)
        
        # Match par ensemble de tokens
        scores.append(fuzz.token_set_ratio(norm1, norm2) / 100.0)
        
        # Prendre le meilleur score
        return max(scores)
    
    def _normalize_column_name(self, name: str) -> str:
        """
        Normalise un nom de colonne pour la comparaison
        """
        if not name:
            return ""
        
        # Convertir en minuscule
        name = name.lower()
        
        # Remplacer les espaces et caractères spéciaux par underscore
        name = re.sub(r'[^\w]', '_', name)
        
        # Supprimer les underscores multiples
        name = re.sub(r'_+', '_', name)
        
        # Supprimer les underscores en début/fin
        name = name.strip('_')
        
        # Liste de mots à supprimer (non discriminants)
        stop_words = {'col', 'column', 'field', 'attr', 'attribute', 'fld', 'val', 'value'}
        
        # Séparer par underscore et filtrer les stop words
        parts = name.split('_')
        filtered_parts = [p for p in parts if p and p not in stop_words]
        
        # Reconstruire le nom
        normalized = '_'.join(filtered_parts)
        
        return normalized if normalized else name
    
    def _calculate_type_similarity(self, type1: str, type2: str) -> float:
        """
        Calcule la similarité entre types de données
        """
        if not type1 or not type2:
            return 0.0
        
        # Normaliser les types
        type1 = str(type1).lower().strip()
        type2 = str(type2).lower().strip()
        
        # Exact match
        if type1 == type2:
            return 1.0
        
        # Groupes de types compatibles
        type_groups = {
            'int': ['int', 'integer', 'bigint', 'smallint', 'long'],
            'float': ['float', 'double', 'decimal', 'numeric'],
            'string': ['string', 'varchar', 'text', 'char'],
            'date': ['date', 'timestamp', 'datetime'],
            'bool': ['boolean', 'bool']
        }
        
        # Vérifier si dans le même groupe
        for group_name, types in type_groups.items():
            if type1 in types and type2 in types:
                return 0.8
        
        # Vérifier la compatibilité partielle
        for t1 in type1.split('(')[0].split('<'):
            for t2 in type2.split('(')[0].split('<'):
                if t1 in t2 or t2 in t1:
                    return 0.6
        
        return 0.0
    
    def _calculate_position_similarity(self, pos1: int, pos2: int) -> float:
        """
        Calcule la similarité basée sur la position dans le dataset
        """
        diff = abs(pos1 - pos2)
        
        if diff == 0:
            return 1.0
        elif diff <= 2:
            return 0.7
        elif diff <= 5:
            return 0.4
        else:
            return 0.0
    
    def find_best_match(self, current_col: Dict, parent_columns: List[Dict]) -> Tuple[Optional[str], float, Dict]:
        """
        Trouve la meilleure correspondance et retourne toutes les infos
        Utile pour le débogage
        """
        col_name = current_col.get("attributes", {}).get("name", "")
        col_type = current_col.get("attributes", {}).get("type", "")
        col_position = current_col.get("attributes", {}).get("position", 0)
        
        best_logical_id = None
        best_score = 0
        best_details = {}
        
        for parent_col in parent_columns:
            col_attrs = parent_col.get("attributes", {})
            parent_name = col_attrs.get("name", "")
            parent_type = col_attrs.get("type", "")
            parent_logical_id = col_attrs.get("logicalColumnId", "")
            parent_position = col_attrs.get("position", 0)
            
            if not parent_logical_id:
                continue
            
            name_score = self._calculate_name_similarity(col_name, parent_name)
            type_score = self._calculate_type_similarity(col_type, parent_type)
            position_score = self._calculate_position_similarity(col_position, parent_position)
            
            total_score = (name_score * 0.70) + (type_score * 0.20) + (position_score * 0.10)
            
            if total_score > best_score:
                best_score = total_score
                best_logical_id = parent_logical_id
                best_details = {
                    'parent_name': parent_name,
                    'parent_type': parent_type,
                    'parent_position': parent_position,
                    'scores': {
                        'name': name_score,
                        'type': type_score,
                        'position': position_score,
                        'total': total_score
                    }
                }
        
        return best_logical_id, best_score, best_details