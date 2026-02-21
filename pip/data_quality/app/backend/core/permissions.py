# core/permissions.py - NOUVEAU FICHIER
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from db.connexion_db import get_db
from db.projects import Project
from db.users import User
from jwt_dependencies import get_current_user
import logging

logger = logging.getLogger(__name__)

def can_view_project(user: dict, project: Project, db: Session) -> bool:
    """
    Vérifie si un utilisateur peut voir un projet
    """
    # ADMIN et AUDIT voient tout
    if user["role"] in ["ADMIN", "AUDIT"]:
        return True
    
    # DATA_OWNER
    if user["role"] == "DATA_OWNER":
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
    if user["role"] == "ADMIN":
        return True
    
    # DATA_OWNER
    if user["role"] == "DATA_OWNER":
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
    Seul ADMIN peut gérer les utilisateurs
    """
    return user["role"] == "ADMIN"


def can_create_project(user: dict) -> bool:
    """
    Qui peut créer des projets ?
    """
    return user["role"] in ["ADMIN", "DATA_OWNER"]


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
        if user["role"] not in roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Rôle requis: {', '.join(roles)}"
            )
        return user
    
    return dependency