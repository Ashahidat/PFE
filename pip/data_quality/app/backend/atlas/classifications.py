from atlas.client import atlas_post, atlas_get, atlas_delete, ATLAS_V2_BASE_URL
import logging
import time  
from typing import List, Optional, Dict
import json
from sqlalchemy.orm import Session  # ← AJOUTER CET IMPORT

ATLAS_BULK_CLASSIFICATION_URL = f"{ATLAS_V2_BASE_URL}/entity/bulk/classification"
ATLAS_ENTITY_CLASSIFICATION_URL = f"{ATLAS_V2_BASE_URL}/entity/guid"

logger = logging.getLogger(__name__)

def _classification_delete_url(entity_guid: str, classification_name: str) -> str:
    # Atlas uses a singular segment for deletion:
    #   DELETE /api/atlas/v2/entity/guid/{guid}/classification/{classificationName}
    return f"{ATLAS_ENTITY_CLASSIFICATION_URL}/{entity_guid}/classification/{classification_name}"

def check_classification_exists(entity_guid: str, classification_name: str) -> bool:
    """
    Vérifie si une classification existe déjà sur une entité
    """
    try:
        url = f"{ATLAS_ENTITY_CLASSIFICATION_URL}/{entity_guid}"
        response = atlas_get(url)
        entity_data = response.json() if response is not None else {}
        entity = (entity_data or {}).get("entity", {})
        classifications = entity.get("classifications", [])

        for classification in classifications:
            if classification.get("typeName") == classification_name:
                return True
        return False
        
    except Exception as e:
        logger.error(f"Erreur lors de la vérification: {str(e)}")
        return False


def add_classification(
    entity_guid: str,
    classification_name: str,
    attributes: dict = None,
    force_replace: bool = False,
):
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
            if force_replace:
                logger.info(f"🔁 Remplacement forcé de '{classification_name}'")
                remove_classification(entity_guid, classification_name)
                time.sleep(0.8)
            elif check_classification_exists(entity_guid, classification_name):
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


def add_classification_to_entity(
    entity_guid: str,
    classification_name: str,
    attributes: dict = None,
    force_replace: bool = False,
):
    """
    Version simplifiée qui appelle add_classification
    Gardée pour compatibilité avec le code existant
    """
    result = add_classification(
        entity_guid,
        classification_name,
        attributes,
        force_replace=force_replace,
    )
    return result.get("status") in ["added", "already_exists"]


def add_classifications_bulk(entity_guids: List[str], classification_name: str, attributes: dict = None):
    """
    Ajoute une classification à plusieurs entités en une seule requête
    """
    if not entity_guids:
        logger.warning("⚠️ Aucun GUID fourni pour l'ajout bulk de classifications")
        return False
    
    logger.info(f"📤 Envoi classification bulk à {len(entity_guids)} entités - Type: {classification_name}")
    
    try:
        payload = {
            "classification": {
                "typeName": classification_name,
                "attributes": attributes or {}
            },
            "entityGuids": entity_guids
        }
        
        response = atlas_post(ATLAS_BULK_CLASSIFICATION_URL, payload)
        
        if response.status_code == 204:
            logger.info(f"✅ Classification {classification_name} ajoutée à {len(entity_guids)} entités (bulk)")
            return True
        
        logger.warning(f"⚠️ Réponse inattendue: {response.status_code}")
        return False
        
    except Exception as e:
        logger.error(f"❌ Erreur ajout classification bulk: {e}")
        return False


def get_classification_for_status(status: str) -> str:
    """
    Retourne la classification correspondant au statut d'un test
    """
    status_lower = status.lower() if status else ""
    
    if status_lower in ["réussi", "success", "pass", "succès"]:
        return "DQ_SUCCESS"
    elif status_lower in ["échoué", "failed", "fail", "echec"]:
        return "DQ_FAILED"
    elif status_lower in ["ignoré", "skipped", "warning"]:
        return "DQ_WARNING"
    else:
        return "DQ_WARNING"  # Par défaut


def add_quality_classification(entity_guid: str, status: str):
    """
    Ajoute automatiquement la bonne classification qualité basée sur le statut
    """
    classification = get_classification_for_status(status)
    return add_classification_to_entity(entity_guid, classification)


# ============================================================
# 🆕 RÉSUMÉ QUALITÉ - VERSION ALIGNÉE AVEC DQ_SUMMARY
# ============================================================

def add_quality_summary_classification(entity_guid: str, checks_data: List[Dict]) -> bool:
    """
    Ajoute un résumé qualité lisible avec le nombre d'échecs
    Compatible avec la nouvelle définition DQ_SUMMARY
    """
    if not checks_data:
        logger.warning("⚠️ Aucune donnée de qualité pour générer un résumé")
        return False

    # Calcul des métriques
    total = len(checks_data)
    success = 0
    failed = 0

    for check in checks_data:
        status = check.get("status", "").lower()
        if not status:
            status = check.get("statut", "").lower()

        if status in ["réussi", "réussie", "succès", "success", "pass"]:
            success += 1
        elif status in ["échoué", "échouée", "échec", "failed", "fail"]:
            failed += 1

    warnings = total - success - failed
    success_rate = round((success / total * 100), 1) if total > 0 else 0

    # Format ultra-lisible pour Atlas UI
    summary_text = f"✅ {success}/{total} ({success_rate}%) | ❌ {failed} | ⚠️ {warnings}"

    logger.info(f"📊 Résumé qualité: {summary_text}")

    attributes = {
        "summary_text": summary_text,
        "failed_count": failed  # important pour requêtes analytiques
    }

    # DQ_SUMMARY doit se rafraîchir à chaque push Atlas.
    # Si on se contente d'un "add if missing", Atlas garde la première version
    # et les pushes suivants n'actualisent pas le résumé.
    try:
        remove_classification(entity_guid, "DQ_SUMMARY")
        time.sleep(0.2)
    except Exception as exc:
        logger.warning(f"⚠️ Impossible de supprimer l'ancien DQ_SUMMARY avant remplacement: {exc}")

    return add_classification_to_entity(
        entity_guid=entity_guid,
        classification_name="DQ_SUMMARY",
        attributes=attributes,
        force_replace=True,
    )


# ============================================================
# 🔒 NOUVELLES FONCTIONS - CLASSIFICATIONS DE SÉCURITÉ
# ============================================================

def add_restricted_classification(
    entity_guid: str, 
    db: Session,
    owner_employee_id: str,
    visibility_scope: str = "DEPARTMENT"
) -> bool:
    """
    Ajoute la classification RESTRICTED avec le département du propriétaire
    """
    # Import local pour éviter les circular imports
    from db.users_crud import get_user_department
    
    # Récupérer le département du propriétaire
    department = get_user_department(db, owner_employee_id)
    
    if not department:
        logger.warning(f"⚠️ Département non trouvé pour {owner_employee_id}, classification sans département")
        department = "UNKNOWN"
    
    attributes = {
        "visibility_scope": visibility_scope,
        "department": department
    }
    
    logger.info(f"🔒 Ajout classification RESTRICTED: scope={visibility_scope}, dept={department}")
    
    result = add_classification_to_entity(
        entity_guid=entity_guid,
        classification_name="RESTRICTED",
        attributes=attributes
    )
    
    if result:
        logger.info(f"✅ RESTRICTED ajoutée avec département {department}")
    else:
        logger.error(f"❌ Échec ajout RESTRICTED")
    
    return result


def add_public_classification(entity_guid: str) -> bool:
    """
    Ajoute la classification PUBLIC (scope ENTERPRISE)
    """
    attributes = {
        "visibility_scope": "ENTERPRISE"
    }
    
    logger.info(f"🌍 Ajout classification PUBLIC: scope=ENTERPRISE")
    
    result = add_classification_to_entity(
        entity_guid=entity_guid,
        classification_name="PUBLIC",
        attributes=attributes
    )
    
    if result:
        logger.info(f"✅ PUBLIC ajoutée")
    else:
        logger.error(f"❌ Échec ajout PUBLIC")
    
    return result


def add_dataset_security_classification(
    entity_guid: str,
    db: Session,
    owner_employee_id: str,
    is_public: bool = False
) -> bool:
    """
    Fonction unifiée pour ajouter la bonne classification de sécurité
    selon que le dataset est public ou non
    """
    if is_public:
        return add_public_classification(entity_guid)
    else:
        return add_restricted_classification(
            entity_guid=entity_guid,
            db=db,
            owner_employee_id=owner_employee_id
        )

def get_entity_classifications(guid: str) -> List[Dict]:
    """
    Récupère toutes les classifications d'une entité
    """
    try:
        url = f"{ATLAS_ENTITY_CLASSIFICATION_URL}/{guid}?minExtInfo=true"
        response = atlas_get(url)
        entity_data = response.json() if response is not None else {}
        entity = (entity_data or {}).get("entity", {})
        classifications = entity.get("classifications", [])
        logger.debug(f"📋 Classifications trouvées pour {guid}: {len(classifications)}")
        return classifications
            
    except Exception as e:
        logger.error(f"❌ Erreur récupération classifications: {e}")
        return []


def remove_classification(guid: str, classification_name: str) -> bool:
    """
    Supprime une classification d'une entité
    """
    try:
        url = _classification_delete_url(guid, classification_name)
        response = atlas_delete(url)

        if response.status_code == 204:
            logger.info(f"✅ Classification {classification_name} supprimée de {guid}")
            return True
        elif response.status_code == 404:
            logger.info(f"ℹ️ Classification {classification_name} non trouvée sur {guid}")
            return True  # Considéré comme succès car elle n'existe pas
        else:
            logger.warning(f"⚠️ Échec suppression {classification_name}: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur suppression classification: {e}")
        return False



def force_replace_security_classification(guid: str, new_classification: str, attributes: dict = None) -> bool:
    """
    Version FORCE - Supprime TOUTES les classifications et ajoute la nouvelle
    """
    SECURITY_TYPES = ["PUBLIC", "RESTRICTED"]
    
    logger.info(f"🔨 Remplacement forcé pour {guid}: -> {new_classification}")
    
    try:
        # Étape 1: Supprimer PUBLIC si existant
        delete_public_url = _classification_delete_url(guid, "PUBLIC")
        atlas_delete(delete_public_url)
        time.sleep(1)
        
        # Étape 2: Supprimer RESTRICTED si existant  
        delete_restricted_url = _classification_delete_url(guid, "RESTRICTED")
        atlas_delete(delete_restricted_url)
        time.sleep(1)
        
        # Étape 3: Ajouter la nouvelle
        payload = [{
            "typeName": new_classification,
            "attributes": attributes or {}
        }]
        
        add_url = f"{ATLAS_ENTITY_CLASSIFICATION_URL}/{guid}/classifications"
        add_response = atlas_post(add_url, payload)
        
        return add_response.status_code in [200, 204]
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return False









def sync_security_classification_to_atlas(guid: str, new_classification: str, attributes: dict = None) -> bool:
    """
    Version qui fonctionne - Supprime l'ancienne ET ajoute la nouvelle
    AVEC AUTHENTIFICATION CORRECTE
    """
    SECURITY_TYPES = ["PUBLIC", "RESTRICTED"]
    
    logger.info(f"🔄 Synchronisation sécurité pour {guid}: -> {new_classification}")
    
    try:
        # 1️⃣ Supprimer PUBLIC/RESTRICTED de façon déterministe.
        # (Plus robuste que de faire un GET + boucle: en cas d'erreur de listing, on veut quand même remplacer.)
        for type_name in SECURITY_TYPES:
            logger.info(f"🗑️ Suppression de {type_name} (si présent)...")
            delete_url = _classification_delete_url(guid, type_name)
            delete_response = atlas_delete(delete_url)
            if delete_response.status_code == 204:
                logger.info(f"✅ {type_name} supprimée")
            elif delete_response.status_code == 404:
                logger.info(f"ℹ️ {type_name} déjà absente")
            else:
                # atlas_delete() only returns non-raising responses for: 204, 404, or Atlas 500-mapped NotFoundException.
                # Anything else should not happen; treat it as a hard failure to avoid Atlas having BOTH classifications.
                logger.error(f"❌ Échec suppression {type_name}: {delete_response.status_code}")
                return False

            # Small delay to let Atlas settle (avoid eventual consistency glitches)
            time.sleep(0.2)

        # 2️⃣ Ajouter la nouvelle classification
        logger.info(f"➕ Ajout de {new_classification}...")
        
        # Format pour l'ajout (tableau !)
        payload = [{
            "typeName": new_classification,
            "attributes": attributes or {}
        }]
        
        add_url = f"{ATLAS_ENTITY_CLASSIFICATION_URL}/{guid}/classifications"
        add_response = atlas_post(add_url, payload)
        
        if add_response.status_code in [200, 204]:
            logger.info(f"✅ {new_classification} ajoutée avec succès")
            return True
        else:
            logger.error(f"❌ Échec ajout {new_classification}: {add_response.status_code} - {add_response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la synchronisation: {e}", exc_info=True)
        return False
