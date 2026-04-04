# db/users_crud.py

from sqlalchemy.orm import Session
from db.users import User
from typing import Optional, Dict, List

def get_user_info(db: Session, employee_id: str) -> Optional[Dict]:
    """
    Récupère les informations d'un utilisateur par son employee_id.
    """
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        return None

    return {
        "id": user.id,
        "employee_id": user.employee_id,
        "username": user.username,
        "department": user.department,
        "role": user.role
    }


def get_user_department(db: Session, employee_id: str) -> Optional[str]:
    """
    Retourne uniquement le département de l'utilisateur.
    """
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        return None

    return user.department


def get_or_create_user(
    db: Session,
    employee_id: str,
    username: str,
    department: str,
    role: str = "DATA_OWNER"
) -> User:
    """
    Récupère un utilisateur existant ou le crée s'il n'existe pas.
    Utile pour l'authentification OAuth/SSO.
    """
    user = db.query(User).filter(User.employee_id == employee_id).first()

    if not user:
        user = User(
            employee_id=employee_id,
            username=username,
            department=department,
            role=role
        )
        db.add(user)
        db.flush()

    return user

def get_active_users(db: Session) -> List[User]:
    """Récupère tous les utilisateurs actifs"""
    return db.query(User).filter(User.is_active == True).order_by(User.username.asc()).all()

def get_inactive_users(db: Session) -> List[User]:
    """Récupère tous les utilisateurs inactifs"""
    return db.query(User).filter(User.is_active == False).order_by(User.username.asc()).all()

def deactivate_user(db: Session, employee_id: str) -> Optional[User]:
    """Désactive un utilisateur"""
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        return None
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user

def activate_user(db: Session, employee_id: str) -> Optional[User]:
    """Réactive un utilisateur"""
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        return None
    user.is_active = True
    db.commit()
    db.refresh(user)
    return user