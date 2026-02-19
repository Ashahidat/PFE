from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import logging

from db.connexion_db import get_db
from db.crud_projects import create_project, get_user_projects, get_project, delete_project
from db.datasets import Dataset
from jwt_dependencies import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])
logger = logging.getLogger("projects")

# ========== Schémas Pydantic ==========
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    owner_employee_id: str
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
    """Créer un nouveau projet"""
    employee_id = user.get("employee_id") or user.get("sub")
    
    if not employee_id:
        raise HTTPException(status_code=400, detail="Identifiant utilisateur manquant")
    
    logger.info(f"📁 Création projet '{project.name}' pour user {employee_id}")
    
    db_project = create_project(
        db=db,
        name=project.name,
        description=project.description,
        owner_employee_id=employee_id
    )
    
    return {
        "id": str(db_project.id),
        "name": db_project.name,
        "description": db_project.description,
        "owner_employee_id": db_project.owner_employee_id,
        "created_at": str(db_project.created_at),
        "datasets_count": 0
    }


@router.get("/", response_model=List[ProjectResponse])
def list_my_projects(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Lister tous mes projets"""
    employee_id = user.get("employee_id") or user.get("sub")
    
    if not employee_id:
        raise HTTPException(status_code=400, detail="Identifiant utilisateur manquant")
    
    projects = get_user_projects(db, employee_id)
    
    result = []
    for p in projects:
        # Compter les datasets associés
        datasets_count = db.query(Dataset).filter(Dataset.project_id == p.id).count()
        result.append({
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "owner_employee_id": p.owner_employee_id,
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
    """Détails d'un projet spécifique"""
    employee_id = user.get("employee_id") or user.get("sub")
    
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    
    # Vérifier que l'utilisateur est propriétaire
    if project.owner_employee_id != employee_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé à ce projet")
    
    datasets_count = db.query(Dataset).filter(Dataset.project_id == project_id).count()
    
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "owner_employee_id": project.owner_employee_id,
        "created_at": str(project.created_at),
        "datasets_count": datasets_count
    }


@router.delete("/{project_id}")
def delete_project_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Supprimer un projet (seulement s'il est vide)"""
    employee_id = user.get("employee_id") or user.get("sub")
    
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    
    if project.owner_employee_id != employee_id:
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    
    # Vérifier s'il y a des datasets
    datasets_count = db.query(Dataset).filter(Dataset.project_id == project_id).count()
    if datasets_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Impossible de supprimer : {datasets_count} dataset(s) encore associé(s)"
        )
    
    delete_project(db, project_id)
    return {"message": "Projet supprimé avec succès"}