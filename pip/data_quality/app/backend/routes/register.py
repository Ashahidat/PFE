from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
from db.connexion_db import SessionLocal
from db.users import User

router = APIRouter()
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/register")
def register_user(data: dict):
    print("📩 Reçu du frontend:", data)

    db = SessionLocal()

    # Vérifier si l’employee_id existe déjà
    existing = db.query(User).filter_by(employee_id=data["employee_id"]).first()
    print("🔍 Recherche employee_id:", existing)

    if existing:
        raise HTTPException(400, "employee_id déjà utilisé")

    hashed = pwd.hash(data["password"])
    print("🔐 Mot de passe hashé:", hashed)

    user = User(
        employee_id=data["employee_id"],
        username=data["username"],
        password_hash=hashed,
        department=data["department"],
        role="DATA_OWNER"  # Par défaut, on attribue le rôle de DATA_OWNER à tous les nouveaux utilisateurs
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    print("✅ Utilisateur créé:", user)

    return {"status": "success", "user_id": user.id}
