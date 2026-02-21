from fastapi import Request, HTTPException, Depends
from jwt_manager import verify_token

def get_current_user(request: Request):
    print("🔐 Début vérification token...")
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        print("❌ Token manquant ou mal formaté")
        raise HTTPException(status_code=401, detail="Token manquant")

    token = auth_header.split(" ")[1]
    payload = verify_token(token)
    
    if payload is None:
        print("❌ Token invalide ou expiré")
        raise HTTPException(status_code=401, detail="Token invalide")

    # Vérifier si l'utilisateur est actif (optionnel)
    if not payload.get("is_active", True):
        raise HTTPException(status_code=403, detail="Compte désactivé")

    print(f"✅ Token valide - {payload.get('username')} ({payload.get('role')})")
    return payload


def require_admin(user=Depends(get_current_user)):
    """Dépendance pour les routes qui nécessitent le rôle ADMIN"""
    if user.get("role") != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Accès réservé aux administrateurs"
        )
    return user


def require_data_owner_or_admin(user=Depends(get_current_user)):
    """Dépendance pour les routes qui nécessitent DATA_OWNER ou ADMIN"""
    if user.get("role") not in ["ADMIN", "DATA_OWNER"]:
        raise HTTPException(
            status_code=403,
            detail="Accès réservé aux DATA_OWNER et ADMIN"
        )
    return user