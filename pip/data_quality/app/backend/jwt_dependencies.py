from fastapi import HTTPException, Request

from jwt_manager import verify_token

def get_current_user(request: Request):
    print("🔐 Début vérification token...")
    auth_header = request.headers.get("Authorization")
    print(f"📨 Header Authorization: {auth_header}")
    
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
    else:
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            token = cookie_token

    if not token:
        print("❌ Token manquant ou mal formaté")
        raise HTTPException(status_code=401, detail="Token manquant")

    print(f"🔑 Token extrait: {token[:20]}...")  # Affiche seulement les 20 premiers caractères
    
    payload = verify_token(token)
    print(f"📊 Payload décodé: {payload}")
    
    if payload is None:
        print("❌ Token invalide ou expiré")
        raise HTTPException(status_code=401, detail="Token invalide")

    print("✅ Token valide")
    return payload
