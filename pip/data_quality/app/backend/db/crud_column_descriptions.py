from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from db.column_descriptions import ColumnDescription
import uuid
from typing import List, Dict, Optional, Iterable
import logging

# Configuration du logger
logger = logging.getLogger("descriptions.crud")

def create_or_update_description(
    db: Session,
    dataset_version_id: str,
    column_name: str,
    description: str,
    user_id: str
) -> ColumnDescription:
    """
    Crée ou met à jour une description de colonne
    """
    # Chercher si une description existe déjà
    existing = db.query(ColumnDescription).filter(
        ColumnDescription.dataset_version_id == dataset_version_id,
        ColumnDescription.column_name == column_name
    ).first()

    if existing:
        # Mise à jour
        existing.description = description
        existing.updated_at = func.now()
        existing.updated_by = user_id
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # Création
        new_desc = ColumnDescription(
            id=uuid.uuid4(),
            dataset_version_id=dataset_version_id,
            column_name=column_name,
            description=description,
            created_by=user_id
        )
        db.add(new_desc)
        db.commit()
        db.refresh(new_desc)
        return new_desc

def bulk_create_or_update_descriptions(
    db: Session,
    dataset_version_id: str,
    descriptions: Dict[str, str],  # {column_name: description}
    user_id: str
) -> int:
    """
    Crée ou met à jour plusieurs descriptions en une fois
    Retourne le nombre de descriptions sauvegardées
    """
    logger.info(f"📝 bulk_create: version_id={dataset_version_id}, {len(descriptions)} descriptions à traiter")
    
    if len(descriptions) == 0:
        logger.warning("⚠️ Aucune description à sauvegarder!")
        return 0
    
    # Afficher un échantillon
    sample = dict(list(descriptions.items())[:3])
    logger.info(f"   Échantillon: {sample}")
    
    count = 0
    for column_name, description in descriptions.items():
        if description and description.strip():
            create_or_update_description(
                db, 
                dataset_version_id, 
                column_name, 
                description.strip(), 
                user_id
            )
            count += 1
            if count <= 5:  # Log les 5 premières
                logger.debug(f"   ✅ Sauvegardé: {column_name} = '{description[:30]}'")
    
    logger.info(f"✅ {count} descriptions sauvegardées avec succès")
    return count

def get_descriptions_by_version(
    db: Session,
    dataset_version_id: str
) -> List[ColumnDescription]:
    """
    Récupère toutes les descriptions d'une version
    """
    return db.query(ColumnDescription).filter(
        ColumnDescription.dataset_version_id == dataset_version_id
    ).all()

def get_description_dict_by_version(
    db: Session,
    dataset_version_id: str
) -> Dict[str, str]:
    """
    Récupère les descriptions sous forme de dictionnaire {colonne: description}
    """
    descriptions = get_descriptions_by_version(db, dataset_version_id)
    return {d.column_name: d.description for d in descriptions}

def copy_descriptions_from_previous_version(
    db: Session,
    new_version_id: str,
    previous_version_id: str,
    user_id: str
) -> int:
    """
    Copie les descriptions d'une ancienne version vers la nouvelle
    Utile quand on crée une nouvelle version d'un dataset
    """
    previous_descriptions = get_descriptions_by_version(db, previous_version_id)
    
    count = 0
    for old_desc in previous_descriptions:
        new_desc = ColumnDescription(
            id=uuid.uuid4(),
            dataset_version_id=new_version_id,
            column_name=old_desc.column_name,
            description=old_desc.description,
            created_by=user_id,
            created_at=func.now()
        )
        db.add(new_desc)
        count += 1
    
    db.commit()
    return count

def delete_descriptions_by_version(
    db: Session,
    dataset_version_id: str
) -> int:
    """
    Supprime toutes les descriptions d'une version
    (utile en cas de rollback)
    """
    deleted = db.query(ColumnDescription).filter(
        ColumnDescription.dataset_version_id == dataset_version_id
    ).delete(synchronize_session=False)
    db.commit()
    return deleted


def delete_descriptions_for_columns(
    db: Session,
    dataset_version_id: str,
    columns: Iterable[str],
) -> int:
    """
    Supprime les descriptions d'une liste de colonnes pour une version donnée.
    Utile quand l'UI envoie une description vide => on veut effacer en base.
    """
    cols = [c for c in (columns or []) if c and str(c).strip()]
    if not cols:
        return 0
    deleted = (
        db.query(ColumnDescription)
        .filter(
            ColumnDescription.dataset_version_id == dataset_version_id,
            ColumnDescription.column_name.in_(cols),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted or 0)
