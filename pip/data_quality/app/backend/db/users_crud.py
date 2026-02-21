from sqlalchemy.orm import Session
from db.users import User
from typing import Optional, Dict
from datetime import datetime

def get_user_by_employee_id(db: Session, employee_id: str) -> Optional[User]:
    """Récupère un utilisateur par son employee_id"""
    return db.query(User).filter(User.employee_id == employee_id).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Récupère un utilisateur par son ID"""
    return db.query(User).filter(User.id == user_id).first()

def get_all_users(db: Session, include_inactive: bool = False):
    """Récupère tous les utilisateurs (actifs par défaut)"""
    query = db.query(User)
    if not include_inactive:
        query = query.filter(User.is_active == True)
    return query.all()

def create_user(
    db: Session,
    employee_id: str,
    username: str,
    password_hash: str,
    department: str,
    business_unit: str = None,
    role: str = "DATA_OWNER"
) -> User:
    """Crée un nouvel utilisateur"""
    user = User(
        employee_id=employee_id,
        username=username,
        password_hash=password_hash,
        department=department,
        business_unit=business_unit,
        role=role,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_user_role(db: Session, user_id: int, new_role: str) -> Optional[User]:
    """Met à jour le rôle d'un utilisateur"""
    user = get_user_by_id(db, user_id)
    if user:
        user.role = new_role
        db.commit()
        db.refresh(user)
    return user

def deactivate_user(db: Session, user_id: int) -> Optional[User]:
    """Désactive un utilisateur (soft delete)"""
    user = get_user_by_id(db, user_id)
    if user:
        user.is_active = False
        db.commit()
        db.refresh(user)
    return user

def update_last_login(db: Session, user_id: int):
    """Met à jour la date de dernière connexion"""
    user = get_user_by_id(db, user_id)
    if user:
        user.last_login = datetime.now()
        db.commit()