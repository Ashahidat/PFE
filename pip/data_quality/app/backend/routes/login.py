from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
import sys
sys.path.append("/home/ashahi/PFE/pip/data_quality/app/backend")
from db.base import SessionLocal
from db.users import User
from jwt_manager import create_access_token

router = APIRouter()
pwd = CryptContext(schemes=["bcrypt"])

@router.post("/login")
def login(data: dict):
    print("📩 Login reçu:", data)

    db = SessionLocal()

    user = db.query(User).filter_by(employee_id=data["employee_id"]).first()
    print("🔍 Recherche dans la DB →", user)

    if not user:
        raise HTTPException(400, "Identifiants incorrects")

    if not pwd.verify(data["password"], user.password_hash):
        print("❌ Mot de passe incorrect")
        raise HTTPException(400, "Identifiants incorrects")

    print("🔐 Mot de passe valide !")
    print("🎉 Login réussi pour:", user.username)

    token = create_access_token({
    "sub": user.employee_id,
    "username": user.username})


    #return {"message": "login ok"}
    return {
    "access_token": token,
    "token_type": "bearer",
    "username": user.username}

