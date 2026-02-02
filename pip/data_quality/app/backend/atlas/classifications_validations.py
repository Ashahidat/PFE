from enum import Enum
from typing import Set, Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

class EntityType(Enum):
    DATASET = "DATASET"
    COLUMN = "COLUMN"

class DatasetClassification(Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"

class ColumnClassification(Enum):
    PII_DIRECT = "PII_DIRECT"
    PII_QUASI = "PII_QUASI"
    SENSITIVE = "SENSITIVE"
    ENCRYPTED = "ENCRYPTED"

# Ensembles pour validation rapide
DATASET_CLASSIFICATIONS = {c.value for c in DatasetClassification}
COLUMN_CLASSIFICATIONS = {c.value for c in ColumnClassification}
ALL_CLASSIFICATIONS = DATASET_CLASSIFICATIONS.union(COLUMN_CLASSIFICATIONS)

# Règles de cohérence - Mise à jour avec vos classifications
VALID_COMBINATIONS: Dict[str, Set[str]] = {
    "PUBLIC": set(),  # Dataset PUBLIC → pas de colonnes classifiées
    "INTERNAL": {
        "PII_QUASI",
        "ENCRYPTED"
    },
    "CONFIDENTIAL": {
        "PII_DIRECT",
        "PII_QUASI",
        "SENSITIVE",
        "ENCRYPTED"
    },
    "RESTRICTED": {
        "PII_DIRECT",
        "PII_QUASI",
        "SENSITIVE",
        "ENCRYPTED"
    }
}

class ClassificationValidationError(Exception):
    pass

def validate_entity_classification(entity_type: str, classification: str) -> bool:
    """
    Valide qu'une classification correspond au type d'entité
    """
    if entity_type == "DATASET":
        if classification not in DATASET_CLASSIFICATIONS:
            raise ClassificationValidationError(
                f"'{classification}' ne peut pas être appliqué à un DATASET. "
                f"Utilisez: {', '.join(sorted(DATASET_CLASSIFICATIONS))}"
            )
    
    elif entity_type == "COLUMN":
        if classification not in COLUMN_CLASSIFICATIONS:
            raise ClassificationValidationError(
                f"'{classification}' ne peut pas être appliqué à une COLONNE. "
                f"Utilisez: {', '.join(sorted(COLUMN_CLASSIFICATIONS))}"
            )
    
    else:
        raise ClassificationValidationError(f"Type d'entité inconnu: {entity_type}")
    
    return True

def validate_dataset_columns_consistency(
    db_session,
    dataset_id: str,
    column_classifications: Dict[str, str]  # {column_name: classification}
) -> bool:
    """
    Valide la cohérence entre classification dataset et ses colonnes
    """
    from db.classifications import EntityClassification
    
    # Récupérer la classification active du dataset
    dataset_class = db_session.query(EntityClassification).filter(
        EntityClassification.entity_type == "DATASET",
        EntityClassification.entity_id == dataset_id,
        EntityClassification.is_active.is_(True)
    ).first()
    
    if not dataset_class:
        # Si le dataset n'a pas de classification, autoriser toutes les colonnes
        logger.warning(f"Dataset {dataset_id} n'a pas de classification active")
        return True
    
    dataset_classification = dataset_class.classification_name
    
    # Vérifier si la classification est valide pour un dataset
    validate_entity_classification("DATASET", dataset_classification)
    
    # Vérifier la cohérence avec chaque colonne
    for column_name, column_class in column_classifications.items():
        if dataset_classification == "PUBLIC" and column_class:
            raise ClassificationValidationError(
                f"Un dataset PUBLIC ne peut pas avoir de colonnes classifiées. "
                f"Colonne '{column_name}' a '{column_class}'"
            )
        
        if dataset_classification in VALID_COMBINATIONS:
            allowed = VALID_COMBINATIONS[dataset_classification]
            if column_class and column_class not in allowed:
                raise ClassificationValidationError(
                    f"Dataset '{dataset_classification}' incompatible avec colonne '{column_name}' "
                    f"classée '{column_class}'. Autorisé: {', '.join(sorted(allowed)) if allowed else 'AUCUNE'}"
                )
    
    return True

def get_allowed_column_classifications(dataset_classification: str) -> List[str]:
    """
    Retourne les classifications autorisées pour les colonnes
    Utile pour l'interface utilisateur
    """
    return sorted(VALID_COMBINATIONS.get(dataset_classification, []))