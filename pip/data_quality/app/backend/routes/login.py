from fastapi import APIRouter, HTTPException, Depends
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from db.connexion_db import get_db
from db.users import User
from jwt_manager import create_access_token
from core.roles import SUPER_ADMIN

router = APIRouter()
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/login")
def login(data: dict, db: Session = Depends(get_db)):
    # Vérifier si un admin existe déjà dans la base
    super_admin_exists = db.query(User).filter(User.role == SUPER_ADMIN).first()
    
    # =========================================================
    # CAS 1 : Premier lancement - aucun admin n'existe
    # =========================================================
    if not super_admin_exists:
        user = db.query(User).filter(User.employee_id == data["employee_id"]).first()
        
        hashed = pwd.hash(data["password"])
        if not user:
            user = User(
                employee_id=data["employee_id"],
                username=data.get("username", data["employee_id"]),
                password_hash=hashed,
                department=data.get("department", "ADMIN"),
                role=SUPER_ADMIN,
                is_protected=False,
                is_active=True
            )
            db.add(user)
        else:
            user.username = data.get("username", user.username)
            user.password_hash = hashed
            user.department = data.get("department", user.department or "ADMIN")
            user.role = SUPER_ADMIN
            user.is_protected = True
            user.is_active = True
        db.commit()
        db.refresh(user)
        
        token = create_access_token({
            "sub": user.employee_id,
            "username": user.username,
            "role": user.role,
            "department": user.department,
            "employee_id": user.employee_id
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
    
    # ✅ Vérifier si le compte est actif
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Ce compte est désactivé. Contactez votre administrateur.")
    
    if not pwd.verify(data["password"], user.password_hash):
        raise HTTPException(status_code=400, detail="Identifiants incorrects")
    
    token = create_access_token({
        "sub": user.employee_id,
        "username": user.username,
        "role": user.role,
        "department": user.department,
        "employee_id": user.employee_id
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
    super_admin_exists = db.query(User).filter(User.role == SUPER_ADMIN).first() is not None
    return {"admin_exists": super_admin_exists}
