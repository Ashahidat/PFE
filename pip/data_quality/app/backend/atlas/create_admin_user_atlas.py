import requests
import json

ATLAS_URL = "http://localhost:21000/api/atlas/v2"

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
                         auth=("admin", "admin"),
                         headers={"Content-Type": "application/json"})
    print(f"Typedef creation: {resp1.status_code}")
    
    # Créer l'entité admin
    resp2 = requests.post(f"{ATLAS_URL}/entity", 
                         json=admin_entity,
                         auth=("admin", "admin"),
                         headers={"Content-Type": "application/json"})
    print(f"Admin creation: {resp2.status_code}")
    if resp2.status_code == 200:
        print("✅ Admin user created successfully!")
    else:
        print(f"Error: {resp2.text}")
        
except Exception as e:
    print(f"Failed: {e}")