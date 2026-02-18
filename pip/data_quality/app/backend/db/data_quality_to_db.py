from sqlalchemy.orm import Session
from db.data_quality_results import DataQualityResult
from db.dag_runs import DAGRun 
import json
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

def save_data_quality_results_from_json(
    db: Session,
    dataset_version_id: UUID,
    dag_run_uuid: str,  # Garder en str car peut être texte ou UUID
    json_path: str
):
    """
    Sauvegarde les résultats de qualité depuis un fichier JSON.
    - Cherche l'UUID réel du dag_run à partir du dag_run_id textuel
    - Crée les enregistrements dans data_quality_results
    """
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Récupérer le dag_run_id textuel du JSON
    dag_run_text_id = data.get("dag_run_id")
    
    if not dag_run_text_id:
        logger.error(f"❌ Pas de dag_run_id dans le JSON: {json_path}")
        return []
    
    logger.info(f"🔍 Recherche de l'UUID pour dag_run_id: {dag_run_text_id}")
    
    # Chercher l'UUID correspondant dans la table dag_runs
    dag_run_record = db.query(DAGRun).filter(  # ← Utiliser DAGRun
        DAGRun.dag_run_id == dag_run_text_id
    ).first()
    
    if not dag_run_record:
        logger.error(f"❌ Aucun dag_run trouvé avec l'ID: {dag_run_text_id}")
        logger.error(f"   Vérifiez que la table dag_runs contient cet enregistrement")
        return []
    
    # Utiliser le vrai UUID
    real_dag_run_uuid = dag_run_record.id
    logger.info(f"✅ UUID trouvé: {real_dag_run_uuid}")
    
    created_ids = []
    
    # Parcourir tous les checks
    for check in data.get("checks", []):
        try:
            # Calculer le ratio (gérer le format "X/Y")
            ratio_str = check.get("ratio", "0/0")
            try:
                if '/' in ratio_str:
                    num, denom = ratio_str.split('/')
                    ratio_value = float(num) / float(denom) if float(denom) > 0 else 0.0
                else:
                    ratio_value = float(ratio_str)
            except (ValueError, ZeroDivisionError):
                ratio_value = 0.0
            
            # Créer l'enregistrement avec le BON UUID
            result = DataQualityResult(
                dag_run_uuid=real_dag_run_uuid,  # ← C'est un UUID maintenant !
                dataset_version_id=dataset_version_id,
                validator_name=check.get("rule_type", "unknown"),
                check_type=check.get("rule_type", "unknown"),
                column_name=check.get("column_name"),
                status=check.get("status", "inconnu"),
                error_count=check.get("error_count", 0),
                ratio=ratio_value,
                alert=(check.get("status") == "échoué"),
                examples=json.dumps(check.get("examples", []), ensure_ascii=False)
            )
            
            db.add(result)
            db.flush()  # Pour obtenir l'ID sans commit
            created_ids.append(str(result.id))
            
            logger.debug(f"  ✅ Check ajouté: {check.get('rule_type')} - {result.id}")
            
        except Exception as e:
            logger.error(f"❌ Erreur sur un check: {e}")
            db.rollback()
            raise
    
    # Commit final
    db.commit()
    logger.info(f"✅ {len(created_ids)} résultats qualité sauvegardés dans PostgreSQL")
    
    return created_ids