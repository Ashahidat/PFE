# db/classifications_use_case.py

from atlas.classifications import add_classification
from atlas.classifications_col_history import create_col_classifications_history_in_atlas
from db.classifications_crud import disable_active_classifications, create_entity_classification
from db.users_crud import get_user_department_bu
from atlas.classifications_validations import (
    validate_entity_classification,
    validate_dataset_columns_consistency,
    ClassificationValidationError
)
import logging
from sqlalchemy.exc import IntegrityError
from atlas.client import atlas_get, ATLAS_SEARCH_URL
from db.datasets import Dataset

logger = logging.getLogger(__name__)


def apply_classification_use_case(
    db,
    *,
    entity_type,
    entity_id,
    atlas_guid,
    classification_name,
    attributes,
    user,
    column_name: str = None,
    dataset_id: str = None  # utilisé pour logical_column_id
):
    logger.info(f"🚀 Début use_case - {entity_type}:{entity_id} -> {classification_name}")

    try:
        # 1️⃣ Validation
        validate_entity_classification(entity_type, classification_name)

        if entity_type == "COLUMN" and column_name:
            validate_dataset_columns_consistency(
                db,
                entity_id,  # dataset_id
                {column_name: classification_name}
            )

        # 2️⃣ Sécurisation transaction
        if db.in_transaction():
            logger.warning("⚠️ Transaction déjà active - rollback")
            db.rollback()

        # 3️⃣ Identification utilisateur
        employee_id = user.get("employee_id") or user.get("sub")
        if not employee_id:
            raise ValueError("Identifiant utilisateur manquant dans le token")

        dept_bu = get_user_department_bu(db, employee_id)
        if not dept_bu:
            raise ValueError(f"Utilisateur {employee_id} non trouvé")

        department, business_unit = dept_bu

        # 4️⃣ Désactiver anciennes classifications (DB = source de vérité)
        rows_updated = disable_active_classifications(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            column_name=column_name
        )
        logger.info(f"Anciennes classifications désactivées: {rows_updated}")

        # 5️⃣ Créer nouvelle classification en base
        classification = create_entity_classification(
            db=db,
            entity_type=entity_type,
            entity_id=entity_id,
            atlas_guid=atlas_guid,
            classification_name=classification_name,
            classification_attributes=attributes,
            applied_by=employee_id,
            department=department,
            business_unit=business_unit,
            column_name=column_name
        )

        db.flush()

        # 6️⃣ Ajouter classification ACTIVE dans Atlas
        atlas_response = add_classification(atlas_guid, classification_name, attributes)
        if atlas_response and atlas_response.get("status") == "already_exists":
            logger.info("Classification déjà présente dans Atlas")

        # 7️⃣ Historique Atlas (VISUALISATION)
        if entity_type == "COLUMN" and column_name and dataset_id:
            try:
                # Récupérer le dataset pour avoir son atlas_guid
                dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
                dataset_atlas_guid = dataset.atlas_guid if dataset else None
                
                # Récupérer le logical_column_id de la colonne depuis Atlas
                base_url = ATLAS_SEARCH_URL.split("/search")[0]
                res = atlas_get(f"{base_url}/entity/guid/{atlas_guid}")
                col_entity = res.json().get("entity", {})
                logical_column_id = col_entity.get("attributes", {}).get("logicalColumnId")
                
                logger.info(f"📝 Création historique pour colonne '{column_name}':")
                logger.info(f"   - logical_column_id: {logical_column_id}")
                logger.info(f"   - dataset_atlas_guid: {dataset_atlas_guid}")
                
                if not logical_column_id:
                    logger.warning(f"⚠️ logicalColumnId non trouvé pour la colonne {atlas_guid}")
                    # Fallback: utiliser juste le nom de colonne
                    logical_column_id = column_name.lower().strip()
                
                # 🆕 Appeler avec dataset_guid en plus (NECESSAIRE POUR LE VERSIONING)
                history_guid = create_col_classifications_history_in_atlas(
                    column_guid=atlas_guid,
                    classification_name=classification_name,
                    user_id=employee_id,
                    status="ACTIVE",
                    logical_column_id=logical_column_id,
                    dataset_guid=dataset_atlas_guid  # 🆕 Nouveau paramètre CRITIQUE
                )
                
                if history_guid:
                    logger.info(f"✅ Historique créé dans Atlas: {history_guid}")
                else:
                    logger.warning("❌ Échec création historique")

            except Exception as e:
                logger.warning(f"⚠️ Historique Atlas non créé (non bloquant): {e}", exc_info=True)

        # 8️⃣ Commit final
        db.commit()
        return classification

    except ClassificationValidationError as e:
        logger.error(f"❌ Erreur validation: {str(e)}")
        if db.in_transaction():
            db.rollback()
        raise ValueError(str(e)) from e

    except IntegrityError as e:
        logger.error("❌ Violation unicité classification active", exc_info=True)
        if db.in_transaction():
            db.rollback()
        raise ValueError("Une classification active existe déjà pour cette entité.") from e

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'application de la classification: {str(e)}", exc_info=True)
        if db.in_transaction():
            db.rollback()
        raise