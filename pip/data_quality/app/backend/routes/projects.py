# routes/projects.py 

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import logging
import uuid

from db.connexion_db import get_db
from db.crud_projects import create_project, get_user_projects, get_project, delete_project
from db.datasets import Dataset
from db.projects import Project  # IMPORTANT: pour les requêtes directes
from jwt_dependencies import get_current_user
from core.permissions import (
    can_view_project, 
    can_upload_to_project, 
    can_create_project,
    require_role,
    require_project_access
)

router = APIRouter(prefix="/projects", tags=["projects"])
logger = logging.getLogger("projects")

# ========== Schémas Pydantic ==========
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    visibility: str = "DEPARTMENT"  # PUBLIC ou DEPARTMENT, DEFAULT DEPARTMENT

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    owner_employee_id: str
    visibility: str  # AJOUTÉ
    created_at: str
    datasets_count: int

    class Config:
        from_attributes = True

# ========== Endpoints ==========

@router.post("/", response_model=ProjectResponse)
def create_new_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Créer un nouveau projet avec visibilité définie"""
    
    # 🔒 Vérifier que l'utilisateur peut créer des projets
    if not can_create_project(user):
        logger.warning(f"❌ Utilisateur {user['sub']} (role: {user['role']}) n'a pas le droit de créer un projet")
        raise HTTPException(status_code=403, detail="Seuls ADMIN et DATA_OWNER peuvent créer des projets")
    
    # 🔒 Validation supplémentaire pour DATA_OWNER
    if user["role"] == "DATA_OWNER" and project.visibility == "PUBLIC":
        # Option 1: Autoriser (c'est ce que je propose)
        logger.info(f"ℹ️ DATA_OWNER {user['sub']} crée un projet PUBLIC")
        # Option 2: Interdire (décommente si tu préfères)
        # raise HTTPException(status_code=403, detail="Seul ADMIN peut créer des projets PUBLIC")
    
    employee_id = user.get("employee_id") or user.get("sub")
    
    if not employee_id:
        raise HTTPException(status_code=400, detail="Identifiant utilisateur manquant")
    
    logger.info(f"📁 Création projet '{project.name}' (visibility: {project.visibility}) pour user {employee_id}")
    
    # Créer le projet avec visibility
    db_project = Project(
        id=uuid.uuid4(),
        name=project.name,
        description=project.description,
        owner_employee_id=employee_id,
        visibility=project.visibility
    )
    
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    return {
        "id": str(db_project.id),
        "name": db_project.name,
        "description": db_project.description,
        "owner_employee_id": db_project.owner_employee_id,
        "visibility": db_project.visibility,  # AJOUTÉ
        "created_at": str(db_project.created_at),
        "datasets_count": 0
    }


@router.get("/", response_model=List[ProjectResponse])
def list_my_projects(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Lister tous les projets que l'utilisateur PEUT voir"""
    employee_id = user.get("employee_id") or user.get("sub")
    
    if not employee_id:
        raise HTTPException(status_code=400, detail="Identifiant utilisateur manquant")
    
    # Récupérer TOUS les projets (pas seulement ceux de l'utilisateur)
    all_projects = db.query(Project).all()
    
    # Filtrer selon les permissions
    visible_projects = []
    for p in all_projects:
        if can_view_project(user, p, db):
            visible_projects.append(p)
    
    logger.info(f"👁️ Utilisateur {employee_id} (role: {user['role']}) voit {len(visible_projects)}/{len(all_projects)} projets")
    
    result = []
    for p in visible_projects:
        # Compter les datasets associés
        datasets_count = db.query(func.count(Dataset.id)).filter(Dataset.project_id == p.id).scalar() or 0
        result.append({
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "owner_employee_id": p.owner_employee_id,
            "visibility": p.visibility,  # AJOUTÉ
            "created_at": str(p.created_at),
            "datasets_count": datasets_count
        })
    
    return result


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_details(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Détails d'un projet spécifique avec vérification des droits"""
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    
    # 🔒 Vérifier que l'utilisateur peut VOIR ce projet
    if not can_view_project(user, project, db):
        logger.warning(f"❌ Utilisateur {user['sub']} tente d'accéder au projet {project_id} sans droit")
        raise HTTPException(status_code=403, detail="Vous n'avez pas les droits pour voir ce projet")
    
    datasets_count = db.query(func.count(Dataset.id)).filter(Dataset.project_id == project_id).scalar() or 0
    
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "owner_employee_id": project.owner_employee_id,
        "visibility": project.visibility,  # AJOUTÉ
        "created_at": str(project.created_at),
        "datasets_count": datasets_count
    }


@router.delete("/{project_id}")
def delete_project_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Supprimer un projet (seulement ADMIN ou propriétaire)"""
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    
    # 🔒 Règle: ADMIN peut tout supprimer, DATA_OWNER seulement ses projets
    if user["role"] == "ADMIN":
        # ADMIN peut supprimer n'importe quel projet
        pass
    elif user["role"] == "DATA_OWNER":
        # DATA_OWNER peut supprimer seulement ses propres projets
        if project.owner_employee_id != user["sub"]:
            logger.warning(f"❌ DATA_OWNER {user['sub']} tente de supprimer le projet de {project.owner_employee_id}")
            raise HTTPException(status_code=403, detail="Vous ne pouvez supprimer que vos propres projets")
    else:
        # AUDIT ne peut pas supprimer
        raise HTTPException(status_code=403, detail="Vous n'avez pas les droits pour supprimer des projets")
    
    # Vérifier s'il y a des datasets
    datasets_count = db.query(func.count(Dataset.id)).filter(Dataset.project_id == project_id).scalar() or 0
    if datasets_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Impossible de supprimer : {datasets_count} dataset(s) encore associé(s)"
        )
    
    db.delete(project)
    db.commit()
    
    logger.info(f"🗑️ Projet {project_id} supprimé par {user['sub']}")
    return {"message": "Projet supprimé avec succès"}
