# atlas/classifications_col_history.py

from atlas.client import (
    atlas_post,
    atlas_get,
    ATLAS_ENTITY_BULK_URL,
    ATLAS_RELATIONSHIP_URL,
    ATLAS_SEARCH_URL
)
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)

def find_previous_classification_history(column_guid, logical_column_id, dataset_guid=None):
    """
    Cherche la classification précédente via logicalColumnId
    Si dataset_guid fourni, cherche aussi via versioning du dataset
    """
    try:
        base_url = ATLAS_SEARCH_URL.split("/search")[0]
        
        logger.info(f"🔍 Recherche historique pour:")
        logger.info(f"   - column_guid: {column_guid}")
        logger.info(f"   - logical_column_id: {logical_column_id}")
        logger.info(f"   - dataset_guid: {dataset_guid}")
        
        # OPTION 1: Recherche par logicalColumnId exact
        if logical_column_id:
            previous_history = _find_by_logical_id(column_guid, logical_column_id, base_url)
            if previous_history:
                return previous_history
        
        # OPTION 2: Recherche via versioning du dataset parent
        if dataset_guid:
            previous_history = _find_via_dataset_versioning(column_guid, dataset_guid, base_url)
            if previous_history:
                return previous_history
        
        logger.info("ℹ️ Aucun historique précédent trouvé")
        return None
        
    except Exception as e:
        logger.warning(f"❌ Erreur recherche historique: {e}", exc_info=True)
        return None

def _find_by_logical_id(column_guid, logical_column_id, base_url):
    """Cherche par logicalColumnId"""
    try:
        search_query = f'logicalColumnId:"{logical_column_id}" AND __typeName:"Column"'
        res = atlas_get(f"{ATLAS_SEARCH_URL}?typeName=Column&query={search_query}")
        columns = res.json().get("entities", [])
        
        logger.info(f"📊 Colonnes trouvées avec logicalColumnId '{logical_column_id}': {len(columns)}")
        
        # Exclure la colonne actuelle et trier par date
        previous_columns = [c for c in columns if c.get("guid") != column_guid]
        if not previous_columns:
            logger.info("❌ Aucune autre colonne avec ce logicalColumnId")
            return None
        
        previous_columns.sort(
            key=lambda x: x.get("attributes", {}).get("createTime", 0),
            reverse=True
        )
        
        latest_previous = previous_columns[0]
        previous_column_guid = latest_previous.get("guid")
        logger.info(f"✅ Colonne précédente trouvée: {previous_column_guid}")
        
        # Chercher l'historique lié à cette colonne
        return find_active_history_for_column(previous_column_guid, base_url)
        
    except Exception as e:
        logger.warning(f"⚠️ Erreur recherche par logical_id: {e}")
        return None

def _find_via_dataset_versioning(column_guid, dataset_guid, base_url):
    """Cherche via versioning du dataset parent"""
    try:
        logger.info(f"🔗 Recherche via versioning du dataset {dataset_guid}")
        
        # 1. Récupérer le dataset actuel
        res = atlas_get(f"{base_url}/entity/guid/{dataset_guid}")
        dataset_entity = res.json().get("entity", {})
        
        # 2. Chercher le dataset "previous" dans le versioning
        relationships = dataset_entity.get("relationshipAttributes", {})
        previous_dataset = relationships.get("previous")
        
        if not previous_dataset:
            logger.info("ℹ️ Aucun dataset précédent dans le versioning")
            return None
        
        previous_dataset_guid = previous_dataset.get("guid")
        logger.info(f"📦 Dataset parent précédent trouvé: {previous_dataset_guid}")
        
        # 3. Récupérer le nom de la colonne actuelle
        res = atlas_get(f"{base_url}/entity/guid/{column_guid}")
        col_entity = res.json().get("entity", {})
        col_attrs = col_entity.get("attributes", {})
        col_name = col_attrs.get("name", "")
        
        if not col_name:
            logger.info("ℹ️ Impossible de récupérer le nom de la colonne")
            return None
        
        # 4. Chercher la colonne correspondante dans le dataset précédent
        search_query = f'name:"{col_name}" AND __typeName:"Column"'
        res = atlas_get(f"{ATLAS_SEARCH_URL}?typeName=Column&query={search_query}")
        all_columns = res.json().get("entities", [])
        
        for col in all_columns:
            col_attrs = col.get("attributes", {})
            col_dataset = col_attrs.get("dataset")
            
            # Vérifier si la colonne appartient au dataset précédent
            dataset_match = False
            if isinstance(col_dataset, dict) and col_dataset.get("guid") == previous_dataset_guid:
                dataset_match = True
            elif isinstance(col_dataset, str) and col_dataset == previous_dataset_guid:
                dataset_match = True
            
            if dataset_match:
                previous_column_guid = col.get("guid")
                logger.info(f"✅ Colonne correspondante trouvée: {previous_column_guid}")
                return find_active_history_for_column(previous_column_guid, base_url)
        
        logger.info(f"ℹ️ Aucune colonne '{col_name}' trouvée dans le dataset précédent")
        return None
        
    except Exception as e:
        logger.warning(f"⚠️ Erreur recherche via versioning: {e}")
        return None

def find_active_history_for_column(column_guid, base_url):
    """
    Cherche l'historique ACTIVE lié à une colonne
    """
    try:
        res = atlas_get(f"{base_url}/entity/guid/{column_guid}")
        col_entity = res.json().get("entity", {})
        rels = col_entity.get("relationshipAttributes", {})
        
        histories = rels.get("classificationHistory")
        if histories and isinstance(histories, list):
            logger.info(f"📋 Historiques trouvés pour colonne: {len(histories)}")
            # Retourner la plus récente classification active
            for hist in reversed(histories):
                status = hist.get("attributes", {}).get("status")
                hist_guid = hist.get("guid")
                logger.info(f"   - Historique {hist_guid}: status={status}")
                if status == "ACTIVE":
                    logger.info(f"🎯 Historique ACTIVE trouvé: {hist_guid}")
                    return hist_guid
        
        logger.info("ℹ️ Aucun historique trouvé pour cette colonne")
        return None
        
    except Exception as e:
        logger.warning(f"⚠️ Erreur récupération historique colonne: {e}")
        return None

def create_col_classifications_history_in_atlas(
    column_guid,
    classification_name,
    user_id,
    status="ACTIVE",
    logical_column_id=None,
    dataset_guid=None  # 🆕 Nouveau paramètre
):
    """
    Crée une entité ClassificationHistory dans Atlas,
    la lie à la colonne et (optionnellement) à l'historique précédent
    """
    logger.info(f"🎯 DEBUT create_col_classifications_history_in_atlas")
    logger.info(f"   - column_guid: {column_guid}")
    logger.info(f"   - classification_name: {classification_name}")
    logger.info(f"   - logical_column_id: {logical_column_id}")
    logger.info(f"   - dataset_guid: {dataset_guid}")
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    classification_qn = f"classification_{classification_name}_{timestamp}"

    history_payload = {
        "entities": [{
            "typeName": "ClassificationHistory",
            "attributes": {
                "qualifiedName": classification_qn,
                "name": f"{classification_name} - {timestamp}",
                "classificationType": classification_name,
                "appliedAt": datetime.now().isoformat(),
                "appliedBy": user_id,
                "status": status
            },
            "guid": "-history-temp"
        }]
    }

    # 1️⃣ Création de l'entité ClassificationHistory
    try:
        res = atlas_post(ATLAS_ENTITY_BULK_URL, history_payload)
        if res.status_code not in (200, 201):
            logger.error(f"❌ Création ClassificationHistory échouée: {res.status_code} {res.text}")
            return None

        assignments = res.json().get("guidAssignments", {})
        history_guid = assignments.get("-history-temp")

        if not history_guid:
            logger.error(f"❌ Aucun GUID renvoyé par Atlas: {res.text}")
            return None

        logger.info(f"✅ ClassificationHistory créée: {history_guid}")

    except Exception as e:
        logger.error(f"❌ Erreur création ClassificationHistory: {e}")
        return None

    # 2️⃣ Attente propagation Atlas
    time.sleep(2)

    # 3️⃣ Relation Column ↔ ClassificationHistory
    relation_payload = {
        "typeName": "has_classification_history",
        "end1": {"guid": column_guid, "typeName": "Column"},
        "end2": {"guid": history_guid, "typeName": "ClassificationHistory"}
    }

    try:
        res_rel = atlas_post(ATLAS_RELATIONSHIP_URL, relation_payload)
        if res_rel.status_code not in (200, 201):
            logger.warning(f"⚠️ Relation Column ↔ History échouée: {res_rel.status_code} {res_rel.text}")
        else:
            logger.info("✅ Relation Column ↔ ClassificationHistory créée")
    except Exception as e:
        logger.warning(f"⚠️ Relation Column ↔ History échouée: {e}")

    # ⭐ 4️⃣ Relation lineage entre historiques (SI logical_column_id fourni)
    if logical_column_id:
        logger.info(f"🔍 Recherche historique précédent...")
        
        previous_history_guid = find_previous_classification_history(
            column_guid=column_guid,
            logical_column_id=logical_column_id,
            dataset_guid=dataset_guid  # 🆕 Passer le dataset_guid
        )

        if previous_history_guid:
            logger.info(f"🔗 Historique précédent trouvé: {previous_history_guid}")
            lineage_payload = {
                "typeName": "classification_history_lineage",
                "end1": {
                    "guid": previous_history_guid,
                    "typeName": "ClassificationHistory"
                },
                "end2": {
                    "guid": history_guid,
                    "typeName": "ClassificationHistory"
                }
            }

            try:
                atlas_post(ATLAS_RELATIONSHIP_URL, lineage_payload)
                logger.info(f"✅ Lien historique créé: {previous_history_guid} → {history_guid}")
            except Exception as e:
                logger.warning(f"⚠️ Lien historique échoué: {e}")
        else:
            logger.info("ℹ️ Aucun historique précédent trouvé")

    logger.info(f"🏁 FIN create_col_classifications_history_in_atlas - retour: {history_guid}")
    return history_guid