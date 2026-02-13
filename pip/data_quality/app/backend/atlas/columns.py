from .client import atlas_post, ATLAS_ENTITY_BULK_URL, ATLAS_RELATIONSHIP_URL
from atlas.column_matching import ColumnMatcher
import hashlib
import logging

logger = logging.getLogger("atlas.columns")
logger.setLevel(logging.DEBUG)

def link_column_versioning(parent_column_guid: str, child_column_guid: str, parent_col_name: str = "", child_col_name: str = ""):
    """
    Crée une relation VISIBLE dans Atlas entre deux versions d'une même colonne
    """
    if not parent_column_guid or not child_column_guid:
        logger.error(f"❌ link_column_versioning: GUIDs manquants - parent={parent_column_guid}, child={child_column_guid}")
        return None
    
    if parent_column_guid == child_column_guid:
        logger.error(f"❌ link_column_versioning: même GUID, skip")
        return None
    
    # 🔥 Vérifier que ce sont des vrais GUIDs Atlas (pas des temporaires)
    if parent_column_guid.startswith("-col-") or child_column_guid.startswith("-col-"):
        logger.error(f"❌ GUID temporaire détecté! parent={parent_column_guid}, child={child_column_guid}")
        return None
    
    relationship_payload = {
        "typeName": "column_versioning",
        "end1": {
            "guid": child_column_guid,
            "typeName": "Column"
        },
        "end2": {
            "guid": parent_column_guid,
            "typeName": "Column"
        }
    }
    
    try:
        logger.info(f"🔗 Création relation column_versioning: '{child_col_name}' → '{parent_col_name}' ({parent_column_guid[:8]}... → {child_column_guid[:8]}...)")
        res = atlas_post(ATLAS_RELATIONSHIP_URL, relationship_payload)
        result = res.json()
        logger.info(f"✅ Relation column_versioning créée: {result.get('guid')}")
        return result
    except Exception as e:
        logger.error(f"❌ Erreur création column_versioning: {e}")
        return None

def create_columns(df, dataset_guid, dataset_qualified_name, 
                  parent_dataset_guid=None, parent_columns=None,
                  parent_column_mapping=None):
    """
    Crée les colonnes dans Atlas ET les relations de versioning entre colonnes
    RETOURNE (column_mapping, entities_with_real_guids)
    """
    entities = []
    temp_to_name = {}  # {temp_guid: column_name}
    temp_to_logical_id = {}  # {temp_guid: logical_id}
    
    # Initialiser le matcher
    matcher = ColumnMatcher()
    
    # Récupérer les colonnes parent
    parent_column_logical_ids = {}
    parent_columns_by_position = {}
    columns_to_use = []
    
    if parent_dataset_guid:
        logger.info(f"👪 Parent dataset trouvé: {parent_dataset_guid[:8]}...")
        
        # Utiliser les colonnes passées en paramètre si disponibles
        if parent_columns:
            logger.info(f"📦 Utilisation de {len(parent_columns)} colonnes parent fournies")
            columns_to_use = parent_columns
        else:
            logger.info(f"🔍 Recherche des colonnes parent dans Atlas...")
            columns_to_use = matcher._get_dataset_columns(parent_dataset_guid)
            logger.info(f"📦 {len(columns_to_use)} colonnes trouvées dans Atlas")
        
        # Créer les mappings pour le matching
        for col in columns_to_use:
            attrs = col.get("attributes", {})
            parent_name = attrs.get("name")
            logical_id = attrs.get("logicalColumnId")
            position = attrs.get("position")
            
            if parent_name and logical_id:
                parent_column_logical_ids[parent_name] = logical_id
                logger.debug(f"  📌 Parent: '{parent_name}' → logicalId: {logical_id[:8]}...")
            
            if position is not None and logical_id:
                parent_columns_by_position[position] = logical_id
        
        logger.info(f"📦 {len(parent_column_logical_ids)} logicalColumnIds récupérés du parent")
    
    logger.info(f"📋 Création de {len(df.columns)} colonnes pour dataset {dataset_guid[:8]}...")
    
    for idx, (col_name, dtype) in enumerate(zip(df.columns, df.dtypes)):
        temp_guid = f"-col-{idx}"
        
        # ============= STRATÉGIE DE MATCHING =============
        logical_id = None
        match_strategy = "none"
        
        # NIVEAU 1: Match exact par nom
        if col_name in parent_column_logical_ids:
            logical_id = parent_column_logical_ids[col_name]
            match_strategy = "exact_name"
            logger.info(f"✅ [NIVEAU 1] Match exact pour '{col_name}' → logicalId: {logical_id[:8]}...")
        
        # NIVEAU 2: Match par position
        elif idx in parent_columns_by_position and not logical_id:
            logical_id = parent_columns_by_position[idx]
            match_strategy = "position"
            logger.info(f"📌 [NIVEAU 2] Match par position pour '{col_name}' → logicalId: {logical_id[:8]}...")
        
        # NIVEAU 3: Matching fuzzy
        elif columns_to_use and len(columns_to_use) > 0 and not logical_id:
            temp_entity = {
                "attributes": {
                    "name": col_name,
                    "type": str(dtype),
                    "position": idx
                }
            }
            found_id = matcher.propagate_logical_column_id(temp_entity, parent_dataset_guid)
            if found_id:
                logical_id = found_id
                match_strategy = "fuzzy"
                logger.info(f"🎯 [NIVEAU 3] Match fuzzy pour '{col_name}' → logicalId: {logical_id[:8]}...")
        
        # NIVEAU 4: Nouvel ID
        if not logical_id:
            unique_string = f"{dataset_qualified_name}.{col_name}"
            logical_id = hashlib.sha256(unique_string.encode()).hexdigest()[:32]
            match_strategy = "new"
            logger.info(f"🆕 [NIVEAU 4] Nouvel ID généré pour '{col_name}' → logicalId: {logical_id[:8]}...")
        
        # Construction de l'entité
        entity = {
            "typeName": "Column",
            "attributes": {
                "name": col_name,
                "qualifiedName": f"{dataset_qualified_name}.{col_name}",
                "type": str(dtype),
                "position": idx,
                "logicalColumnId": logical_id,
                "dataset": {
                    "typeName": "DataSet", 
                    "guid": dataset_guid
                }
            },
            "guid": temp_guid
        }
        entities.append(entity)
        temp_to_name[temp_guid] = col_name
        temp_to_logical_id[temp_guid] = logical_id

    if not entities:
        logger.warning("⚠️ Aucune colonne à créer")
        return {}, []

    # 🔥 ENVOYER À ATLAS ET RÉCUPÉRER LES VRAIS GUIDS
    logger.info(f"📤 Envoi de {len(entities)} colonnes à Atlas...")
    
    column_mapping = {}  # {nom_colonne: vrai_guid_atlas}
    entities_with_real_guids = []  # Entités avec vrais GUIDs
    
    try:
        res = atlas_post(ATLAS_ENTITY_BULK_URL, {"entities": entities})
        assignments = res.json().get("guidAssignments", {})
        
        logger.info(f"📥 Reçu {len(assignments)} assignations de GUIDs")
        
        for temp_guid, atlas_guid in assignments.items():
            if temp_guid in temp_to_name:
                column_name = temp_to_name[temp_guid]
                column_mapping[column_name] = atlas_guid
                
                # 🔥 Créer l'entité avec le vrai GUID Atlas
                for entity in entities:
                    if entity["guid"] == temp_guid:
                        entity_with_real_guid = entity.copy()
                        entity_with_real_guid["guid"] = atlas_guid
                        entities_with_real_guids.append(entity_with_real_guid)
                        break
                
                logger.debug(f"  ✅ Colonne créée: '{column_name}' → {atlas_guid[:8]}...")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'envoi des colonnes: {e}")
        raise
    
    # 🔥🔥🔥 CRÉER LES RELATIONS VISIBLES ENTRE COLONNES
    if parent_dataset_guid and parent_column_mapping:
        relations_creees = 0
        relations_ratees = 0
        
        for col_name, child_guid in column_mapping.items():
            # Chercher la colonne parent correspondante
            if col_name in parent_column_mapping:
                parent_guid = parent_column_mapping[col_name]
                
                # 🔥 Vérifier que les deux GUIDs sont valides
                if parent_guid and child_guid and not parent_guid.startswith("-col-") and not child_guid.startswith("-col-"):
                    logger.info(f"🔗 Création relation: {col_name} ({parent_guid[:8]}... → {child_guid[:8]}...)")
                    result = link_column_versioning(parent_guid, child_guid, col_name, col_name)
                    if result:
                        relations_creees += 1
                    else:
                        relations_ratees += 1
                else:
                    logger.warning(f"⚠️ GUID invalide pour {col_name}: parent={parent_guid}, child={child_guid}")
                    relations_ratees += 1
        
        logger.info(f"🔗 {relations_creees} relations column_versioning créées, {relations_ratees} échouées")
    else:
        logger.info(f"ℹ️ Pas de parent ou pas de mapping, aucune relation column_versioning créée")
    
    # Statistiques
    logical_ids_set = set()
    for entity in entities_with_real_guids:
        lid = entity["attributes"].get("logicalColumnId")
        if lid:
            logical_ids_set.add(lid)
    
    logger.info(f"✅ {len(column_mapping)}/{len(df.columns)} colonnes créées dans Atlas")
    
    if parent_dataset_guid and parent_column_logical_ids:
        propagated = sum(1 for e in entities_with_real_guids if e["attributes"].get("logicalColumnId") and 
                        e["attributes"]["logicalColumnId"] in parent_column_logical_ids.values())
        logger.info(f"🏷️  {propagated} logicalColumnIds propagés depuis le parent")
        logger.info(f"🏷️  {len(logical_ids_set) - propagated} nouveaux logicalColumnIds générés")
    else:
        logger.info(f"🏷️  {len(logical_ids_set)} nouveaux logicalColumnIds générés")
    
    return column_mapping, entities_with_real_guids