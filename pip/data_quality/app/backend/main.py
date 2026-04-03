import sys
from pathlib import Path

# ============================================================================
# AJOUTER LES CHEMINS AU PYTHONPATH - VERSION CORRIGÉE
# ============================================================================
# main.py est dans app/backend/
# Pour arriver à la racine (data_quality), il faut remonter 3 niveaux :
# app/backend/main.py -> app/ -> data_quality/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = BASE_DIR / "app" / "backend"

# Ajouter au sys.path
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BACKEND_DIR))

print(f"BASE_DIR: {BASE_DIR}")
print(f"BACKEND_DIR: {BACKEND_DIR}")
print(f"sys.path: {sys.path[:3]}")

# ============================================================================
# IMPORTS
# ============================================================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from config import FRONTEND_DIR
from routes import upload, dag, results, push_atlas, login, classifications, classifications_col, projects, descriptions, versionning, profile

app = FastAPI()


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routes
app.include_router(upload.router)
app.include_router(dag.router)
app.include_router(results.router)
app.include_router(push_atlas.router)
app.include_router(login.router)
app.include_router(classifications.router)
app.include_router(classifications_col.router)
app.include_router(projects.router)
app.include_router(descriptions.router)
app.include_router(versionning.router)
app.include_router(profile.router)

# Frontend
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/ui")
def get_ui():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
