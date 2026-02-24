# atlas/quality_summary.py
import json
import logging
from typing import Dict, Any, List
from atlas.client import atlas_get, atlas_put, ATLAS_ENTITY_URL

logger = logging.getLogger("atlas.quality_summary")

def add_quality_summary_to_dataset(
    dataset_guid: str,
    checks_data: List[Dict]
) -> bool:
    """
    Ajoute un résumé de qualité au dataset en utilisant le champ description
    C'est la méthode la plus simple et fiable car 'description' existe toujours
    """
    if not checks_data:
        logger.warning("⚠️ Aucune donnée de qualité pour générer un résumé")
        return False
    
    # Calculate summary
    total = len(checks_data)
    success = 0
    failed = 0
    warnings = 0
    
    for check in checks_data:
        status = check.get("status", "").lower()
        if status in ["réussi", "success", "pass"]:
            success += 1
        elif status in ["échoué", "failed", "fail"]:
            failed += 1
        elif status in ["warning", "avertissement"]:
            warnings += 1
    
    success_rate = round((success / total * 100), 1) if total > 0 else 0
    
    # Extract last execution date
    last_execution = None
    for check in checks_data:
        dag_run_id = check.get("dag_run_id")
        if dag_run_id and "manual__" in dag_run_id:
            try:
                # Format: manual__2026-02-24T05:50:04.010872+00:00
                date_part = dag_run_id.split("__")[1].split("+")[0]
                last_execution = date_part
                break
            except:
                pass
    
    # Create a nice formatted summary
    summary_lines = [
        "=" * 50,
        "📊 DATA QUALITY SUMMARY",
        "=" * 50,
        f"Total checks: {total}",
        f"✅ Success: {success} ({success_rate}%)",
        f"❌ Failed: {failed}",
        f"⚠️ Warnings: {warnings}",
        f"📅 Last execution: {last_execution or 'Unknown'}",
        "=" * 50
    ]
    
    summary_text = "\n".join(summary_lines)
    
    # Also create a JSON version for structured data (optional)
    summary_json = {
        "total": total,
        "success": success,
        "failed": failed,
        "warnings": warnings,
        "rate": success_rate,
        "last_execution": last_execution
    }
    
    # Combine both in description
    full_description = f"{summary_text}\n\nDATA: {json.dumps(summary_json, ensure_ascii=False)}"
    
    try:
        # Step 1: Get current entity
        url = f"{ATLAS_ENTITY_URL}/guid/{dataset_guid}"
        logger.debug(f"📤 Getting entity: {url}")
        
        res = atlas_get(url)
        entity_data = res.json()
        entity = entity_data.get("entity", {})
        
        # Step 2: Update description
        attributes = entity.get("attributes", {})
        
        # Check if there's an existing description
        current_desc = attributes.get("description", "")
        
        # If there's already a quality summary, replace it
        if "DATA QUALITY SUMMARY" in current_desc:
            # Find where the quality summary starts and replace
            parts = current_desc.split("=" * 50)
            if len(parts) >= 3:
                # Keep everything before the first separator
                new_desc = parts[0].strip()
                if new_desc:
                    new_desc += "\n\n"
                new_desc += full_description
            else:
                new_desc = full_description
        else:
            # Append to existing description
            if current_desc:
                new_desc = current_desc + "\n\n" + full_description
            else:
                new_desc = full_description
        
        attributes["description"] = new_desc
        
        # Step 3: Prepare update payload with ALL required fields
        update_payload = {
            "entity": {
                "guid": dataset_guid,
                "typeName": "DataSet",
                "attributes": attributes,
                "classifications": entity.get("classifications", []),
                "labels": entity.get("labels", []),
                "meaningNames": entity.get("meaningNames", []),
                "meanings": entity.get("meanings", [])
            }
        }
        
        # Step 4: Update entity
        logger.debug(f"📤 Updating entity description")
        put_res = atlas_put(url, update_payload)
        
        if put_res.status_code in [200, 204]:
            logger.info(f"✅ Résumé qualité ajouté à la description du dataset")
            logger.info(f"   📊 {success}/{total} réussis ({success_rate}%)")
            return True
        else:
            logger.error(f"❌ Failed to update: {put_res.status_code}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Erreur ajout résumé qualité: {e}")
        
        # Fallback: try to add as classification
        try:
            from atlas.classifications import add_quality_classification
            
            if failed == 0:
                add_quality_classification(dataset_guid, "SUCCESS")
            elif failed > success:
                add_quality_classification(dataset_guid, "FAILED")
            else:
                add_quality_classification(dataset_guid, "WARNING")
            
            logger.info(f"✅ Fallback: added quality classification instead")
            return True
        except Exception as e2:
            logger.error(f"❌ Fallback also failed: {e2}")
            return False