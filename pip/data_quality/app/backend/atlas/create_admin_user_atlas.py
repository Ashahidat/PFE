import requests
import json
import os

ATLAS_REST_ADDRESS = os.getenv("ATLAS_REST_ADDRESS", "http://127.0.0.1:21002").rstrip("/")
ATLAS_URL = f"{ATLAS_REST_ADDRESS}/api/atlas/v2"
ATLAS_AUTH = (
    os.getenv("ATLAS_USERNAME", "admin"),
    os.getenv("ATLAS_PASSWORD", "admin"),
)

# 1. D'abord, créer le typedef User si nécessaire
user_typedef = {
    "entityDefs": [{
        "name": "__AtlasUserProfile",
        "typeVersion": "1.0",
        "attributeDefs": [
            {
                "name": "name",
                "typeName": "string",
                "cardinality": "SINGLE",
                "isIndexable": True,
                "isOptional": False,
                "isUnique": True
            }
        ]
    }]
}

# 2. Créer l'entité admin
admin_entity = {
    "entity": {
        "typeName": "__AtlasUserProfile",
        "attributes": {
            "name": "admin",
            "fullName": "Administrator",
            "email": "admin@localhost"
        }
    }
}

# Tentative de création
try:
    # Créer le typedef
    resp1 = requests.post(f"{ATLAS_URL}/types/typedefs", 
                         json=user_typedef,
                         auth=ATLAS_AUTH,
                         headers={"Content-Type": "application/json"})
    print(f"Typedef creation: {resp1.status_code}")
    
    # Créer l'entité admin
    resp2 = requests.post(f"{ATLAS_URL}/entity", 
                         json=admin_entity,
                         auth=ATLAS_AUTH,
                         headers={"Content-Type": "application/json"})
    print(f"Admin creation: {resp2.status_code}")
    if resp2.status_code == 200:
        print("✅ Admin user created successfully!")
    else:
        print(f"Error: {resp2.text}")
        
except Exception as e:
    print(f"Failed: {e}")
