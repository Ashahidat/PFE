# routes/projects.py 

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import Optional, List, Literal
import logging
import uuid
import os

from db.connexion_db import get_db
from db.crud_projects import create_project, get_user_projects, get_project, delete_project
from db.datasets import Dataset
from db.projects import Project  # IMPORTANT: pour les requêtes directes
from jwt_dependencies import get_current_user
from core.permissions import (
    can_view_project, 
    can_upload_to_project, 
    can_create_project,
    can_view_dataset,
    can_modify_dataset,
    require_role,
    require_project_access,
    require_super_admin,
)
from core.roles import ADMINISTRATORS, PROJECT_CREATORS
from grafana.settings import get_grafana_settings
from grafana.client import GrafanaClient
from grafana.maintenance import cleanup_project_artifacts
from grafana.provisioning import provision_project_dashboards
from grafana.links import build_project_grafana_links

router = APIRouter(prefix="/projects", tags=["projects"])
logger = logging.getLogger("projects")


def _grafana_identity_headers(user: dict, *, for_project_creator: bool = False) -> dict[str, str] | None:
    """
    Build the trusted auth-proxy headers Grafana can use during server-side provisioning.

    Project creation can be performed by DATA_OWNER too, so we allow the broader
    PROJECT_CREATORS group there. Other privileged provisioning paths keep the stricter
    admin-only gate.
    """
    allowed_roles = PROJECT_CREATORS if for_project_creator else ADMINISTRATORS
    if str(user.get("role") or "").upper() not in allowed_roles:
        return None
    return {
        "X-WEBAUTH-USER": str(user.get("employee_id") or user.get("sub") or ""),
        "X-WEBAUTH-NAME": str(user.get("username") or ""),
        "X-WEBAUTH-ROLE": "Admin",
    }

# ========== Schémas Pydantic ==========
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    visibility: Literal["PUBLIC", "DEPARTMENT"] = "DEPARTMENT"

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    owner_employee_id: str
    visibility: str  # AJOUTÉ
    created_at: str
    datasets_count: int
    grafana_links: Optional[dict] = None

    class Config:
        from_attributes = True


class ProjectDatasetResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    uploaded_by: Optional[str] = None
    classification: str
    columns: List[str]
    columns_count: int
    created_at: Optional[str] = None
    atlas_guid: Optional[str] = None
    atlas_synced: bool
    can_edit: bool

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

    # Grafana provisioning (Dashboard as Code) - best effort, never blocks project creation.
    try:
        settings = get_grafana_settings()
        identity_headers = _grafana_identity_headers(user, for_project_creator=True)
        result = provision_project_dashboards(
            settings,
            project_id=str(db_project.id),
            project_name=db_project.name,
            project_visibility=db_project.visibility,
            owner_department=user.get("department") or "UNKNOWN",
            identity_headers=identity_headers,
        )
        if result.get("enabled") is False:
            logger.info("⏭️ Grafana provisioning disabled (GRAFANA_PROVISIONING_ENABLED=false)")
        elif result.get("skipped"):
            logger.warning("⚠️ Grafana provisioning skipped: %s", result.get("reason"))
        else:
            logger.info("✅ Grafana provisioning done: folder_uid=%s", (result.get("folder") or {}).get("uid"))
    except Exception as e:
        # Use exception() to keep the traceback in logs; this is the main breadcrumb when provisioning fails.
        logger.exception(
            "⚠️ Grafana provisioning failed for project %s (url=%s enabled=%s): %s",
            db_project.id,
            os.getenv("GRAFANA_URL", "http://127.0.0.1:3300"),
            os.getenv("GRAFANA_PROVISIONING_ENABLED", "true"),
            e,
        )
    
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
            "datasets_count": datasets_count,
            "grafana_links": build_project_grafana_links(
                project_id=str(p.id),
                project_name=p.name,
                org_id=get_grafana_settings().org_id,
            ),
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

    # Best-effort: keep the dashboard links aligned with the current project state.
    try:
        settings = get_grafana_settings()
        identity_headers = None
        if str(user.get("role") or "").upper() in PROJECT_CREATORS:
            identity_headers = {
                "X-WEBAUTH-USER": str(user.get("employee_id") or user.get("sub") or ""),
                "X-WEBAUTH-NAME": str(user.get("username") or ""),
                "X-WEBAUTH-ROLE": "Admin",
            }
        if settings.enabled:
            provision_project_dashboards(
                settings,
                project_id=str(project.id),
                project_name=project.name,
                project_visibility=project.visibility,
                owner_department=user.get("department") or "UNKNOWN",
                identity_headers=identity_headers,
            )
    except Exception:
        pass
    
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "owner_employee_id": project.owner_employee_id,
        "visibility": project.visibility,  # AJOUTÉ
        "created_at": str(project.created_at),
        "datasets_count": datasets_count,
        "grafana_links": build_project_grafana_links(
            project_id=str(project.id),
            project_name=project.name,
            org_id=get_grafana_settings().org_id,
        ),
    }


@router.get("/{project_id}/datasets", response_model=List[ProjectDatasetResponse])
def list_project_datasets(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Liste les datasets visibles d'un projet avec un résumé utile pour la page détail.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    if not can_view_project(user, project, db):
        raise HTTPException(status_code=403, detail="Vous n'avez pas les droits pour voir ce projet")

    datasets = (
        db.query(Dataset)
        .options(joinedload(Dataset.project))
        .filter(Dataset.project_id == project_id)
        .order_by(Dataset.created_at.desc())
        .all()
    )

    result = []
    for dataset in datasets:
        if not can_view_dataset(user, dataset, db):
            continue

        classification = dataset.classification or (dataset.project.visibility if dataset.project else "DEPARTMENT")
        result.append(
            {
                "id": str(dataset.id),
                "name": dataset.name,
                "description": dataset.description,
                "uploaded_by": dataset.owner_employee_id,
                "classification": classification,
                "columns": dataset.columns_list or [],
                "columns_count": len(dataset.columns_list or []),
                "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
                "atlas_guid": dataset.atlas_guid,
                "atlas_synced": bool(dataset.atlas_synced),
                "can_edit": can_modify_dataset(user, dataset, db),
            }
        )

    return result


@router.get("/{project_id}/grafana-links")
def get_project_grafana_links(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Returns the Grafana folder + 4 dashboards URLs for this project.
    URLs are meant to be opened through the backend reverse-proxy `/api/grafana/...`.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    if not can_view_project(user, project, db):
        raise HTTPException(status_code=403, detail="Vous n'avez pas les droits pour voir ce projet")

    # Best-effort: if provisioning was skipped/failed at creation time, try again on-demand
    # so users don't end up with broken `/api/grafana/dashboards/f/...` links.
    settings = get_grafana_settings()
    try:
        folder_uid = build_project_grafana_links(
            project_id=str(project.id),
            project_name=project.name,
            org_id=None,
        )["folder"]["uid"]
        # Allow provisioning through Grafana auth-proxy when no API creds are configured.
        identity_headers = _grafana_identity_headers(user, for_project_creator=True)

        if settings.enabled:
            client = GrafanaClient(settings, extra_headers=identity_headers)
            existing = client.get_folder_by_uid(folder_uid)
            if not existing:
                logger.info("🛠️ Grafana folder missing for project %s; provisioning", project.id)
            else:
                logger.info("🛠️ Grafana folder exists for project %s; refreshing provisioning", project.id)
            provision_project_dashboards(
                settings,
                project_id=str(project.id),
                project_name=project.name,
                project_visibility=project.visibility,
                owner_department=user.get("department") or "UNKNOWN",
                identity_headers=identity_headers,
            )
    except Exception:
        # Do not fail link retrieval when provisioning fails.
        pass

    return build_project_grafana_links(
        project_id=str(project.id),
        project_name=project.name,
        org_id=get_grafana_settings().org_id,
    )


@router.post("/{project_id}/grafana-provision")
def provision_grafana_for_project(
    project_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_super_admin()),
):
    """
    Force Grafana provisioning for a given project (folder + permissions + dashboards).
    Useful when provisioning was previously skipped (missing Grafana creds) or failed.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")

    settings = get_grafana_settings()
    try:
        identity_headers = _grafana_identity_headers(user)
        result = provision_project_dashboards(
            settings,
            project_id=str(project.id),
            project_name=project.name,
            project_visibility=project.visibility,
            owner_department=user.get("department") or "UNKNOWN",
            identity_headers=identity_headers,
        )
    except Exception as e:
        logger.exception("⚠️ Grafana provisioning failed for project %s: %s", project_id, e)
        raise HTTPException(status_code=502, detail=f"Grafana provisioning failed: {e}")

    return {
        "project_id": str(project.id),
        "folder_uid": (result.get("folder") or {}).get("uid"),
        "result": result,
    }


@router.post("/grafana-provision-all")
def provision_grafana_for_all_projects(
    db: Session = Depends(get_db),
    user=Depends(require_super_admin()),
):
    """
    Force Grafana provisioning for ALL projects (folder + permissions + dashboards).
    Useful when provisioning was previously skipped (missing Grafana creds) or after a fresh Grafana install.
    """
    settings = get_grafana_settings()
    identity_headers = {
        "X-WEBAUTH-USER": str(user.get("employee_id") or user.get("sub") or ""),
        "X-WEBAUTH-NAME": str(user.get("username") or ""),
        "X-WEBAUTH-ROLE": "Admin",
    }
    projects = db.query(Project).order_by(Project.created_at.asc()).all()

    summary = {
        "total": len(projects),
        "ok": 0,
        "skipped": 0,
        "failed": 0,
        "items": [],
    }

    for project in projects:
        try:
            result = provision_project_dashboards(
                settings,
                project_id=str(project.id),
                project_name=project.name,
                project_visibility=project.visibility,
                owner_department=user.get("department") or "UNKNOWN",
                identity_headers=identity_headers,
            )
            if result.get("enabled") is False or result.get("skipped"):
                summary["skipped"] += 1
                status = "skipped"
            else:
                summary["ok"] += 1
                status = "ok"
            summary["items"].append(
                {
                    "project_id": str(project.id),
                    "project_name": project.name,
                    "folder_uid": (result.get("folder") or {}).get("uid"),
                    "status": status,
                    "result": result,
                }
            )
        except Exception as e:
            summary["failed"] += 1
            logger.exception("⚠️ Grafana provisioning failed for project %s: %s", project.id, e)
            summary["items"].append(
                {
                    "project_id": str(project.id),
                    "project_name": project.name,
                    "status": "failed",
                    "error": str(e),
                }
            )

    return summary


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

    try:
        settings = get_grafana_settings()
        if settings.enabled:
            cleanup_project_artifacts(settings, project_id=str(project.id))
    except Exception:
        logger.exception("⚠️ Grafana cleanup failed for deleted project %s", project_id)

    db.delete(project)
    db.commit()
    
    logger.info(f"🗑️ Projet {project_id} supprimé par {user['sub']}")
    return {"message": "Projet supprimé avec succès"}
