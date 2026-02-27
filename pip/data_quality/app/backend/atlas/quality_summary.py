import json
import logging
import time
from typing import Dict, Any, List
from atlas.client import atlas_get, atlas_put, ATLAS_ENTITY_URL, get_typedef_by_name, ATLAS_TYPEDEF_URL

logger = logging.getLogger("atlas.quality_summary")

def ensure_quality_summary_attribute():
    """
    Vérifie et ajoute l'attribut qualitySummary au type DataSet si nécessaire.
    Respecte la structure existante du type natif DataSet.
    """
    try:
        # 🔥 ÉTAPE 1: Récupérer le typedef DataSet existant (complet)
        # Ne pas utiliser get_typedef_by_name car il ne retourne que l'entityDef
        # Il faut récupérer tout le typedef avec ses relations
        url = f"{ATLAS_TYPEDEF_URL}?name=DataSet&type=entity"
        logger.info(f"  📤 Récupération du typedef DataSet existant: {url}")
        
        res = atlas_get(url)
        data = res.json()
        
        if not data or "entityDefs" not in data or len(data["entityDefs"]) == 0:
            logger.warning("  ⚠️ Typedef DataSet non trouvé")
            return False
        
        dataset_typedef = data["entityDefs"][0]
        
        # 🔥 ÉTAPE 2: Vérifier les attributs existants
        existing_attrs = [a["name"] for a in dataset_typedef.get("attributeDefs", [])]
        logger.info(f"  📋 Attributs existants de DataSet: {existing_attrs}")
        
        if "qualitySummary" not in existing_attrs:
            logger.info("  ➕ Ajout de l'attribut qualitySummary à DataSet...")
            
            # Ajouter le nouvel attribut
            dataset_typedef["attributeDefs"].append({
                "name": "qualitySummary", 
                "typeName": "string",
                "isOptional": True,
                "displayName": "Résumé qualité",
                "options": {
                    "displayType": "text"
                }
            })
            
            # 🔥 ÉTAPE 3: Préparer le payload complet pour la mise à jour
            # Il faut inclure TOUS les types, pas seulement DataSet
            # Mais pour un update, on peut envoyer juste l'entityDef modifié
            update_payload = {
                "entityDefs": [dataset_typedef]
            }
            
            logger.info(f"  📤 Mise à jour du typedef via {ATLAS_TYPEDEF_URL}")
            
            try:
                atlas_put(ATLAS_TYPEDEF_URL, update_payload)
                logger.info("  ✅ Attribut qualitySummary ajouté à DataSet")
                time.sleep(2)  # Attendre la propagation
                return True
            except Exception as e:
                logger.error(f"  ❌ Erreur mise à jour typedef: {e}")
                
                # 🔥 ÉTAPE 4: Si ça échoue, essayer avec le typedef complet depuis typedefs_payload
                logger.info("  🔄 Tentative avec redéploiement complet...")
                try:
                    from atlas.typedefs import typedefs_payload
                    
                    # Utiliser la définition complète de DataSet depuis typedefs_payload
                    # qui contient déjà qualitySummary
                    atlas_put(ATLAS_TYPEDEF_URL, {"entityDefs": [typedefs_payload["entityDefs"][0]]})
                    logger.info("  ✅ DataSet redéployé avec qualitySummary")
                    time.sleep(2)
                    return True
                except Exception as e2:
                    logger.error(f"  ❌ Échec de la seconde tentative: {e2}")
                    
                    # 🔥 ÉTAPE 5: Dernière tentative - POST (création) au lieu de PUT
                    logger.info("  🔄 Tentative avec POST (création)...")
                    try:
                        from atlas.client import atlas_post
                        atlas_post(ATLAS_TYPEDEF_URL, {"entityDefs": [typedefs_payload["entityDefs"][0]]})
                        logger.info("  ✅ DataSet créé avec POST (étrange mais OK)")
                        time.sleep(2)
                        return True
                    except Exception as e3:
                        logger.error(f"  ❌ Toutes les tentatives ont échoué: {e3}")
                        return False
        else:
            logger.info("  ✅ qualitySummary existe déjà dans DataSet")
            return True
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la vérification du typedef: {e}")
        return False

def add_quality_summary_to_dataset(
    dataset_guid: str,
    checks_data: List[Dict]
) -> bool:
    """
    Ajoute un résumé de qualité au dataset en utilisant le champ qualitySummary
    """
    if not checks_data:
        logger.warning("⚠️ Aucune donnée de qualité pour générer un résumé")
        return False
    
    # Calculer le résumé
    total = len(checks_data)
    success = 0
    failed = 0
    warnings = 0
    
    for check in checks_data:
        status = check.get("status", "").lower()
        if not status:
            status = check.get("statut", "").lower()
            
        if status in ["réussi", "réussie", "succès", "success", "pass"]:
            success += 1
        elif status in ["échoué", "échouée", "échec", "failed", "fail"]:
            failed += 1
        elif status in ["warning", "avertissement"]:
            warnings += 1
    
    success_rate = round((success / total * 100), 1) if total > 0 else 0
    
    last_execution = None
    for check in checks_data:
        dag_run_id = check.get("dag_run_id")
        if not dag_run_id:
            dag_run_id = check.get("dag_run_id")
        if dag_run_id and "manual__" in dag_run_id:
            try:
                date_part = dag_run_id.split("__")[1].split("+")[0]
                last_execution = date_part
                break
            except:
                pass
    
    summary_json = {
        "total": total,
        "success": success,
        "failed": failed,
        "warnings": warnings,
        "rate": success_rate,
        "last_execution": last_execution,
        "summary_text": "\n".join([
            "=" * 50,
            "📊 DATA QUALITY SUMMARY",
            "=" * 50,
            f"Total checks: {total}",
            f"✅ Success: {success} ({success_rate}%)",
            f"❌ Failed: {failed}",
            f"⚠️ Warnings: {warnings}",
            f"📅 Last execution: {last_execution or 'Unknown'}",
            "=" * 50
        ])
    }
    
    summary_str = json.dumps(summary_json, ensure_ascii=False)
    
    # 🔥 TENTATIVE PRINCIPALE : Mise à jour de l'attribut
    try:
        # S'assurer que l'attribut existe
        logger.info("🔧 Vérification de l'attribut qualitySummary...")
        if ensure_quality_summary_attribute():
            logger.info("  ✅ qualitySummary disponible, tentative de mise à jour...")
            
            # Récupérer l'entité d'abord pour s'assurer qu'elle existe
            get_url = f"{ATLAS_ENTITY_URL}/guid/{dataset_guid}"
            logger.debug(f"📤 Récupération de l'entité: {get_url}")
            
            try:
                res = atlas_get(get_url)
                logger.debug(f"  ✅ Entité récupérée")
            except Exception as e:
                logger.error(f"  ❌ Impossible de récupérer l'entité: {e}")
                # Continuer quand même, la mise à jour peut fonctionner
            
            # Format pour mise à jour partielle
            update_url = f"{ATLAS_ENTITY_URL}/guid/{dataset_guid}"
            update_payload = {
                "entity": {
                    "guid": dataset_guid,
                    "typeName": "DataSet",
                    "attributes": {
                        "qualitySummary": summary_str
                    }
                }
            }
            
            logger.debug(f"📤 Mise à jour partielle de qualitySummary")
            try:
                put_res = atlas_put(update_url, update_payload)
                
                if put_res.status_code in [200, 204]:
                    logger.info(f"✅ Résumé qualité ajouté à qualitySummary du dataset")
                    logger.info(f"   📊 {success}/{total} réussis ({success_rate}%)")
                    return True
                else:
                    logger.error(f"❌ Échec mise à jour: {put_res.status_code} - {put_res.text}")
            except Exception as put_e:
                logger.error(f"❌ Erreur lors de la mise à jour: {put_e}")
        else:
            logger.warning("  ⚠️ Impossible d'ajouter qualitySummary au typedef")
            
    except Exception as e:
        logger.error(f"❌ Erreur ajout résumé qualité: {e}")
    
    # Fallback classification (ça marche toujours !)
    logger.info("🔄 Utilisation du fallback classification...")
    try:
        from atlas.classifications import add_quality_classification
        
        if failed == 0:
            add_quality_classification(dataset_guid, "SUCCESS")
            logger.info(f"✅ Fallback: classification DQ_SUCCESS ajoutée")
        elif failed > success:
            add_quality_classification(dataset_guid, "FAILED")
            logger.info(f"✅ Fallback: classification DQ_FAILED ajoutée")
        else:
            add_quality_classification(dataset_guid, "WARNING")
            logger.info(f"✅ Fallback: classification DQ_WARNING ajoutée")
        
        return True
    except Exception as e2:
        logger.error(f"❌ Fallback aussi en échec: {e2}")
        return False