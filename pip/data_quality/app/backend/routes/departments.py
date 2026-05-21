import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core.permissions import require_role
from core.roles import SUPER_ADMIN, ADMIN, ADMIN_GLOSSAIRE
from db.connexion_db import get_db
from db.departments import Department
from db.user_department_scopes import UserDepartmentScope
from db.users import User
from jwt_dependencies import get_current_user

router = APIRouter(tags=["departments"])


def _normalize_code(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"\s+", "_", value)
    return value.upper()


class DepartmentResponse(BaseModel):
    code: str
    label: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class DepartmentCreate(BaseModel):
    code: str
    label: str
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    label: str | None = None
    is_active: bool | None = None


@router.get("/departments", response_model=List[DepartmentResponse])
def list_departments(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(Department)
    if not include_inactive:
        query = query.filter(Department.is_active == True)
    return query.order_by(Department.label.asc()).all()


@router.post("/departments", response_model=DepartmentResponse)
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    user=Depends(require_role([SUPER_ADMIN])),
):
    code = _normalize_code(payload.code)
    if not code:
        raise HTTPException(status_code=400, detail="Code département obligatoire")
    if db.query(Department).filter(Department.code == code).first():
        raise HTTPException(status_code=400, detail="Ce département existe déjà")
    dept = Department(code=code, label=payload.label.strip(), is_active=bool(payload.is_active))
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@router.put("/departments/{code}", response_model=DepartmentResponse)
def update_department(
    code: str,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_role([SUPER_ADMIN])),
):
    norm = _normalize_code(code)
    dept = db.query(Department).filter(Department.code == norm).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Département introuvable")
    if payload.label is not None:
        dept.label = payload.label.strip()
    if payload.is_active is not None:
        dept.is_active = bool(payload.is_active)
    db.commit()
    db.refresh(dept)
    return dept


class ScopeGrant(BaseModel):
    employee_id: str
    department_code: str


@router.get("/departments/scopes/{employee_id}", response_model=List[DepartmentResponse])
def list_scopes_for_user(
    employee_id: str,
    db: Session = Depends(get_db),
    user=Depends(require_role([SUPER_ADMIN])),
):
    scopes = (
        db.query(Department)
        .join(UserDepartmentScope, UserDepartmentScope.department_code == Department.code)
        .filter(UserDepartmentScope.employee_id == employee_id)
        .order_by(Department.label.asc())
        .all()
    )
    return scopes


@router.post("/departments/scopes", response_model=dict)
def grant_scope(
    payload: ScopeGrant,
    db: Session = Depends(get_db),
    user=Depends(require_role([SUPER_ADMIN])),
):
    employee_id = (payload.employee_id or "").strip()
    dept_code = _normalize_code(payload.department_code)
    if not employee_id or not dept_code:
        raise HTTPException(status_code=400, detail="employee_id et department_code requis")

    target = db.query(User).filter(User.employee_id == employee_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    dept = db.query(Department).filter(Department.code == dept_code).first()
    if not dept or not dept.is_active:
        raise HTTPException(status_code=404, detail="Département introuvable ou inactif")

    existing = (
        db.query(UserDepartmentScope)
        .filter(UserDepartmentScope.employee_id == employee_id, UserDepartmentScope.department_code == dept_code)
        .first()
    )
    if existing:
        return {"message": "Déjà autorisé"}

    db.add(UserDepartmentScope(employee_id=employee_id, department_code=dept_code))
    db.commit()
    return {"message": "Autorisation ajoutée"}


@router.delete("/departments/scopes", response_model=dict)
def revoke_scope(
    payload: ScopeGrant,
    db: Session = Depends(get_db),
    user=Depends(require_role([SUPER_ADMIN])),
):
    employee_id = (payload.employee_id or "").strip()
    dept_code = _normalize_code(payload.department_code)
    scope = (
        db.query(UserDepartmentScope)
        .filter(UserDepartmentScope.employee_id == employee_id, UserDepartmentScope.department_code == dept_code)
        .first()
    )
    if not scope:
        raise HTTPException(status_code=404, detail="Autorisation introuvable")
    db.delete(scope)
    db.commit()
    return {"message": "Autorisation retirée"}


@router.get("/departments/allowed", response_model=List[DepartmentResponse])
def list_allowed_departments_for_current_user(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Returns departments the current user is allowed to manage for glossary operations.
    - SUPER_ADMIN / ADMIN: all active departments
    - ADMIN_GLOSSAIRE: only granted scopes
    - others: empty list
    """
    role = user.get("role")
    if role in (SUPER_ADMIN, ADMIN):
        return (
            db.query(Department)
            .filter(Department.is_active == True)
            .order_by(Department.label.asc())
            .all()
        )
    if role == ADMIN_GLOSSAIRE:
        emp_id = user.get("employee_id") or user.get("sub")
        if not emp_id:
            return []
        return (
            db.query(Department)
            .join(UserDepartmentScope, UserDepartmentScope.department_code == Department.code)
            .filter(UserDepartmentScope.employee_id == emp_id, Department.is_active == True)
            .order_by(Department.label.asc())
            .all()
        )
    return []
