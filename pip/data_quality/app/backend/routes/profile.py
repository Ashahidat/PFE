from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core.permissions import require_role
from core.roles import ADMIN, ADMIN_GLOSSAIRE, SUPER_ADMIN, is_valid_role
from db.connexion_db import get_db
from db.users import User
from jwt_dependencies import get_current_user

router = APIRouter(tags=["profile"])
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


class MeResponse(BaseModel):
    employee_id: str
    username: str
    department: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class MeUpdate(BaseModel):
    username: str | None = None
    password: str | None = None

    model_config = ConfigDict(extra="forbid")


def _get_employee_id_from_token(user: dict) -> str:
    employee_id = user.get("employee_id") or user.get("sub")
    if not employee_id:
        raise HTTPException(status_code=400, detail="Identifiant utilisateur manquant")
    return employee_id


class UserSummaryResponse(BaseModel):
    employee_id: str
    username: str
    department: str
    role: str
    is_protected: bool
    is_active: bool  # ← NOUVEAU

    model_config = ConfigDict(from_attributes=True)


@router.get("/me", response_model=MeResponse)
def get_me(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    employee_id = _get_employee_id_from_token(user)
    db_user = db.query(User).filter(User.employee_id == employee_id).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    return db_user


@router.put("/me", response_model=MeResponse)
def update_me(
    payload: MeUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    employee_id = _get_employee_id_from_token(user)
    db_user = db.query(User).filter(User.employee_id == employee_id).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if payload.username is None and payload.password is None:
        raise HTTPException(status_code=400, detail="Aucun champ a mettre a jour")

    if payload.username is not None:
        db_user.username = payload.username

    if payload.password is not None:
        db_user.password_hash = pwd.hash(payload.password)

    db.commit()
    db.refresh(db_user)

    return db_user


def _build_user_query(db: Session, include_super_admin: bool):
    query = db.query(User)
    if not include_super_admin:
        query = query.filter(User.role != SUPER_ADMIN)
    return query.order_by(User.username.asc())


@router.get("/users", response_model=list[UserSummaryResponse])
def get_users(
    db: Session = Depends(get_db),
    user=Depends(require_role([ADMIN, ADMIN_GLOSSAIRE]))
):
    include_super_admin = user.get("role") == SUPER_ADMIN
    return _build_user_query(db, include_super_admin).all()


class UserCreate(BaseModel):
    employee_id: str
    username: str
    password: str
    department: str
    role: str

    model_config = ConfigDict(from_attributes=True)


@router.post("/users", response_model=UserSummaryResponse)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role([ADMIN, ADMIN_GLOSSAIRE]))
):
    existing = db.query(User).filter(User.employee_id == payload.employee_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="employee_id déjà utilisé")

    if not is_valid_role(payload.role):
        raise HTTPException(status_code=400, detail="Rôle invalide")
    if payload.role == SUPER_ADMIN and user.get("role") != SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Seul un super-admin peut créer un super-admin")

    hashed_password = pwd.hash(payload.password)

    new_user = User(
        employee_id=payload.employee_id,
        username=payload.username,
        password_hash=hashed_password,
        department=payload.department,
        role=payload.role,
        is_protected=(payload.role == SUPER_ADMIN),
        is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


class UserUpdate(BaseModel):
    username: str | None = None
    password: str | None = None
    department: str | None = None
    role: str | None = None
    is_active: bool | None = None  # ← NOUVEAU


@router.put("/users/{employee_id}", response_model=UserSummaryResponse)
def update_user_by_admin(
    employee_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin_user=Depends(require_role([ADMIN, ADMIN_GLOSSAIRE]))
):
    target_user = db.query(User).filter(User.employee_id == employee_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    if target_user.is_protected and target_user.employee_id != admin_user.get("employee_id") and admin_user.get("role") != SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Cet utilisateur est protégé et ne peut pas être modifié"
        )
    if target_user.role == SUPER_ADMIN and admin_user.get("role") != SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Seul un super-admin peut modifier un autre super-admin"
        )

    if all(field is None for field in [payload.username, payload.password, payload.department, payload.role, payload.is_active]):
        raise HTTPException(status_code=400, detail="Aucun champ à mettre à jour")

    if payload.role is not None and not is_valid_role(payload.role):
        raise HTTPException(status_code=400, detail="Rôle invalide")
    if payload.role == SUPER_ADMIN and admin_user.get("role") != SUPER_ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Seul un super-admin peut assigner le rôle super-admin"
        )

    if payload.username is not None:
        target_user.username = payload.username
    if payload.password is not None:
        target_user.password_hash = pwd.hash(payload.password)
    if payload.department is not None:
        target_user.department = payload.department
    if payload.role is not None:
        target_user.role = payload.role
    if payload.is_active is not None:
        target_user.is_active = payload.is_active

    db.commit()
    db.refresh(target_user)

    return target_user
