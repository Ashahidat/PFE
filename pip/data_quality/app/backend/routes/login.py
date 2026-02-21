from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
from db.connexion_db import SessionLocal
from db.users_crud import get_user_by_employee_id, update_last_login
from jwt_manager import create_access_token

router = APIRouter()
pwd = CryptContext(schemes=["bcrypt"])

@router.post("/login")
def login(data: dict):
    print("📩 Login reçu:", data)

    db = SessionLocal()

    user = get_user_by_employee_id(db, data["employee_id"])
    
    if not user or not user.is_active:
        raise HTTPException(400, "Identifiants incorrects ou compte inactif")

    if not pwd.verify(data["password"], user.password_hash):
        print("❌ Mot de passe incorrect")
        raise HTTPException(400, "Identifiants incorrects")

    # Mettre à jour la dernière connexion
    update_last_login(db, user.id)

    print(f"🎉 Login réussi: {user.username} ({user.role})")

    # Token enrichi avec rôle et département
    token = create_access_token({
        "sub": user.employee_id,
        "username": user.username,
        "role": user.role,
        "department": user.department,
        "is_active": user.is_active
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user.username,
        "role": user.role
    }