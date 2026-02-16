# utils/db_utils.py
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys
sys.path.insert(0, "/home/ashahi/PFE/pip/data_quality/app/backend")


from db.crud.data_quality_results import create_result
from db.connexion_db import Base

# Configuration de la base de données
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/pfe_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def save_results_to_postgres(results: dict, dag_run_uuid: str, dataset_version_id: str):
    """
    Sauvegarde les résultats de validation dans PostgreSQL
    
    Args:
        results: Dictionnaire des résultats par type de validation
        dag_run_uuid: UUID du DAG run Airflow
        dataset_version_id: UUID de la version du dataset
    """
    db = SessionLocal()
    try:
        saved_results = []
        
        # Parcourir chaque type de validation
        for validator_name, validation_results in results.items():
            # Si le résultat est une liste (plusieurs checks)
            if isinstance(validation_results, list):
                for res in validation_results:
                    result = create_result(
                        db=db,
                        dag_run_uuid=dag_run_uuid,
                        dataset_version_id=dataset_version_id,
                        validator_name=validator_name,
                        res=res
                    )
                    saved_results.append(result)
            # Si le résultat est un dictionnaire unique
            elif isinstance(validation_results, dict):
                # Éviter les erreurs
                if "error" not in validation_results:
                    result = create_result(
                        db=db,
                        dag_run_uuid=dag_run_uuid,
                        dataset_version_id=dataset_version_id,
                        validator_name=validator_name,
                        res=validation_results
                    )
                    saved_results.append(result)
        
        print(f"✅ {len(saved_results)} résultats sauvegardés dans PostgreSQL")
        return saved_results
        
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde: {e}")
        db.rollback()
        raise
    finally:
        db.close()