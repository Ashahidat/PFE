# db/user_crud.py

from sqlalchemy.orm import Session
from db.users import User
from typing import Optional, Dict

def get_user_info(db: Session, employee_id: str) -> Optional[Dict]:
    """
    Récupère les informations d'un utilisateur par son employee_id.
    
    Args:
        db: Session SQLAlchemy
        employee_id: Identifiant de l'employé
    
    Returns:
        Dict avec les informations utilisateur ou None si non trouvé
    """
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        return None
    
    return {
        "id": user.id,
        "employee_id": user.employee_id,
        "username": user.username,
        "department": user.department,
        "business_unit": user.business_unit,
        "role": user.role
    }


def get_user_department_bu(db: Session, employee_id: str) -> Optional[tuple]:
    """
    Version simplifiée qui retourne seulement department et business_unit.
    
    Args:
        db: Session SQLAlchemy
        employee_id: Identifiant de l'employé
    
    Returns:
        Tuple (department, business_unit) ou None
    """
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        return None
    
    return user.department, user.business_unit


def get_or_create_user(
    db: Session,
    employee_id: str,
    username: str,
    department: str,
    business_unit: str,
    role: str = "analyst"
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
            business_unit=business_unit,
            role=role
        )
        db.add(user)
        db.flush()
    
    return user