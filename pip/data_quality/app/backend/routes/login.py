from fastapi import APIRouter, HTTPException, Depends
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from db.connexion_db import get_db
from db.users import User
from jwt_manager import create_access_token

router = APIRouter()
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/login")
def login(data: dict, db: Session = Depends(get_db)):
    # Vérifier si un admin existe déjà dans la base
    admin_exists = db.query(User).filter(User.role == "ADMIN").first()
    
    # =========================================================
    # CAS 1 : Premier lancement - aucun admin n'existe
    # =========================================================
    if not admin_exists:
        # Chercher si l'utilisateur existe déjà
        user = db.query(User).filter(User.employee_id == data["employee_id"]).first()
        
        if not user:
            # Créer le premier utilisateur comme ADMIN protégé
            hashed = pwd.hash(data["password"])
            user = User(
                employee_id=data["employee_id"],
                username=data.get("username", data["employee_id"]),
                password_hash=hashed,
                department=data.get("department", "ADMIN"),
                role="ADMIN",
                is_protected=True  # ← PREMIER ADMIN PROTÉGÉ
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Générer le token
        token = create_access_token({
            "sub": user.employee_id,
            "username": user.username,
            "role": user.role,
            "department": user.department
        })
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "username": user.username,
            "role": user.role,
            "department": user.department,
            "employee_id": user.employee_id
        }
    
    # =========================================================
    # CAS 2 : Login normal (admin existe déjà)
    # =========================================================
    user = db.query(User).filter(User.employee_id == data["employee_id"]).first()
    
    if not user:
        raise HTTPException(status_code=400, detail="Identifiants incorrects")
    
    if not pwd.verify(data["password"], user.password_hash):
        raise HTTPException(status_code=400, detail="Identifiants incorrects")
    
    token = create_access_token({
        "sub": user.employee_id,
        "username": user.username,
        "role": user.role,
        "department": user.department
    })
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role,
        "department": user.department,
        "employee_id": user.employee_id
    }


@router.get("/users/count-admin")
def check_admin_exists(db: Session = Depends(get_db)):
    admin_exists = db.query(User).filter(User.role == "ADMIN").first() is not None
    return {"admin_exists": admin_exists}