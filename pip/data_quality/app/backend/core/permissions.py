# core/permissions.py - NOUVEAU FICHIER
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from db.connexion_db import get_db
from db.projects import Project
from db.users import User
from jwt_dependencies import get_current_user
from core.roles import (
    SUPER_ADMIN,
    ADMINISTRATORS,
    PROJECT_CREATORS,
    USER_MANAGERS,
    DATA_OWNER,
    ADMIN_GLOSSAIRE,
    AUDIT,
)
import logging

logger = logging.getLogger(__name__)

def can_view_project(user: dict, project: Project, db: Session) -> bool:
    """
    Vérifie si un utilisateur peut voir un projet
    """
    # ADMIN et AUDIT voient tout
    if user.get("role") in ADMINISTRATORS or user.get("role") == AUDIT:
        return True
    
    # DATA_OWNER
    if user.get("role") == DATA_OWNER:
        # PUBLIC : tout le monde voit
        if project.visibility == "PUBLIC":
            return True
        
        # DEPARTMENT : seulement si même département que le créateur
        if project.visibility == "DEPARTMENT":
            # Récupérer le département du créateur
            project_owner = db.query(User).filter(
                User.employee_id == project.owner_employee_id
            ).first()
            
            if not project_owner:
                logger.warning(f"Créateur du projet {project.id} introuvable: {project.owner_employee_id}")
                return False
            
            return project_owner.department == user["department"]
    
    return False


def can_upload_to_project(user: dict, project: Project, db: Session) -> bool:
    """
    Vérifie si un utilisateur peut uploader dans un projet
    """
    # ADMIN peut uploader partout
    if user.get("role") in ADMINISTRATORS:
        return True
    
    # DATA_OWNER
    if user.get("role") == DATA_OWNER:
        # PUBLIC : tout DATA_OWNER peut uploader
        if project.visibility == "PUBLIC":
            return True
        
        # DEPARTMENT : seulement si même département que le créateur
        if project.visibility == "DEPARTMENT":
            project_owner = db.query(User).filter(
                User.employee_id == project.owner_employee_id
            ).first()
            
            if not project_owner:
                logger.warning(f"Créateur du projet {project.id} introuvable: {project.owner_employee_id}")
                return False
            
            return project_owner.department == user["department"]
    
    # AUDIT ne peut pas uploader
    return False


def can_manage_users(user: dict) -> bool:
    """
    Seul SUPER_ADMIN peut gérer les utilisateurs
    """
    return user.get("role") in USER_MANAGERS


def can_create_project(user: dict) -> bool:
    """
    Qui peut créer des projets ?
    """
    return user.get("role") in PROJECT_CREATORS


def require_project_access(project_id: str, access_type: str = "view"):
    """
    Dépendance FastAPI pour vérifier l'accès à un projet
    Utilisation: def get_project(project_id: str, db, user, _=Depends(require_project_access(project_id))):
    """
    def dependency(
        db: Session = Depends(get_db),
        user: dict = Depends(get_current_user)
    ):
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Projet introuvable")
        
        if access_type == "view":
            if not can_view_project(user, project, db):
                raise HTTPException(status_code=403, detail="Vous n'avez pas les droits pour voir ce projet")
        
        elif access_type == "upload":
            if not can_upload_to_project(user, project, db):
                raise HTTPException(status_code=403, detail="Vous n'avez pas les droits pour uploader dans ce projet")
        
        return project
    
    return dependency


def require_role(roles: list):
    """
    Dépendance FastAPI pour vérifier le rôle
    """
    def dependency(user: dict = Depends(get_current_user)):
        user_role = user.get("role")
        if user_role != SUPER_ADMIN and user_role not in roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Rôle requis: {', '.join(roles)}"
            )
        return user

    return dependency


def require_super_admin():
    """Dépendance FastAPI pour restreindre les routes aux SUPER_ADMIN."""
    def dependency(user: dict = Depends(get_current_user)):
        if user.get("role") != SUPER_ADMIN:
            raise HTTPException(
                status_code=403,
                detail="Super-admin requis"
            )
        return user

    return dependency


def _get_employee_identifier(user: dict) -> str | None:
    return user.get("employee_id") or user.get("sub")


def _dataset_visibility(dataset) -> str:
    if getattr(dataset, "classification", None):
        return dataset.classification
    if getattr(dataset, "project", None) and getattr(dataset.project, "visibility", None):
        return dataset.project.visibility
    return "DEPARTMENT"

def _dataset_owner_employee_id(dataset) -> str | None:
    owner = getattr(dataset, "owner_employee_id", None)
    if owner:
        return owner
    project = getattr(dataset, "project", None)
    if project and getattr(project, "owner_employee_id", None):
        return project.owner_employee_id
    return None


def _is_same_department(user: dict, owner_employee_id: str, db: Session) -> bool:
    if not owner_employee_id:
        return False
    owner = db.query(User).filter(User.employee_id == owner_employee_id).first()
    if not owner:
        return False
    return owner.department == user.get("department")


def can_view_dataset(user: dict, dataset, db: Session) -> bool:
    role = user.get("role")
    if role in ADMINISTRATORS:
        return True
    if role == AUDIT:
        return True
    if role == DATA_OWNER:
        visibility = _dataset_visibility(dataset)
        if visibility == "PUBLIC":
            return True
        if visibility == "DEPARTMENT":
            owner_emp_id = _dataset_owner_employee_id(dataset)
            return _is_same_department(user, owner_emp_id, db)
    return False


def can_modify_dataset(user: dict, dataset, db: Session) -> bool:
    role = user.get("role")
    if role in ADMINISTRATORS:
        return True
    if role == DATA_OWNER:
        emp_id = _get_employee_identifier(user)
        if emp_id and dataset.owner_employee_id == emp_id:
            return True
    return False
