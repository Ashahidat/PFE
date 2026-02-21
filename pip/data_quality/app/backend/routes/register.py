from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
from db.connexion_db import SessionLocal
from db.users_crud import create_user, get_user_by_employee_id

router = APIRouter()
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/register")
def register_user(data: dict):
    print("📩 Reçu du frontend:", data)

    db = SessionLocal()

    # Vérifier si l'employee_id existe déjà
    existing = get_user_by_employee_id(db, data["employee_id"])
    if existing:
        raise HTTPException(400, "employee_id déjà utilisé")

    # Hasher le mot de passe
    hashed = pwd.hash(data["password"])

    # Créer l'utilisateur (DATA_OWNER par défaut)
    user = create_user(
        db=db,
        employee_id=data["employee_id"],
        username=data["username"],
        password_hash=hashed,
        department=data["department"],
        business_unit=data.get("business_unit"),
        role="DATA_OWNER"  # Par défaut
    )

    print("✅ Utilisateur créé:", user.employee_id, user.role)

    return {
        "status": "success",
        "user_id": user.id,
        "role": user.role
    }