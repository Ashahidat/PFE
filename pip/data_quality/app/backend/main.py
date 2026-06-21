import logging
import sys
from logging.handlers import RotatingFileHandler
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
# LOGGING
# ============================================================================
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "backend.log"

root_logger = logging.getLogger()
if not root_logger.handlers:
    handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    root_logger.addHandler(handler)

    # Also log to stdout so dev runs (uvicorn) show Atlas/term sync diagnostics in the console.
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s", "%H:%M:%S")
    )
    root_logger.addHandler(stream_handler)
root_logger.setLevel(logging.DEBUG)

# ============================================================================
# IMPORTS
# ============================================================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from config import REACT_DIST_DIR
from routes import upload, dag, results, push_atlas, login, classifications, classifications_col, projects, descriptions, versionning, profile, glossary, datasets_meta, departments, grafana_auth, grafana_proxy

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
API_PREFIX = "/api"

# Register API routers under a common prefix so SPA routes (/) don't collide with
# API endpoints like `/users`. This ensures direct navigation to client routes
# returns the React `index.html` while API requests are available under `/api/...`.
app.include_router(upload.router, prefix=API_PREFIX)
app.include_router(dag.router, prefix=API_PREFIX)
app.include_router(results.router, prefix=API_PREFIX)
app.include_router(push_atlas.router, prefix=API_PREFIX)
app.include_router(login.router, prefix=API_PREFIX)
app.include_router(classifications.router, prefix=API_PREFIX)
app.include_router(classifications_col.router, prefix=API_PREFIX)
app.include_router(projects.router, prefix=API_PREFIX)
app.include_router(descriptions.router, prefix=API_PREFIX)
app.include_router(versionning.router, prefix=API_PREFIX)
app.include_router(profile.router, prefix=API_PREFIX)
app.include_router(glossary.router, prefix=API_PREFIX)
app.include_router(datasets_meta.router, prefix=API_PREFIX)
app.include_router(departments.router, prefix=API_PREFIX)
app.include_router(grafana_auth.router, prefix=API_PREFIX)
app.include_router(grafana_proxy.router, prefix=API_PREFIX)


# React SPA (build output under app/frontend-react/dist)
if os.path.isdir(REACT_DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(REACT_DIST_DIR, "assets")), name="react-assets")

    @app.get("/")
    def get_root():
        return FileResponse(os.path.join(REACT_DIST_DIR, "index.html"))

    @app.get("/{full_path:path}")
    def get_react_spa(full_path: str):
        candidate = os.path.join(REACT_DIST_DIR, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(REACT_DIST_DIR, "index.html"))
