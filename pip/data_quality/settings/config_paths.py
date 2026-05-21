# config/paths.py
"""
Gestion centralisée des chemins du projet
Remplacer tous les chemins absolus par ces variables
"""

from pathlib import Path
import os

# ============================================================================
# DÉTECTION AUTOMATIQUE DE LA RACINE
# ============================================================================
# Ce fichier est dans config/
# La racine est donc config/..
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================================
# DOSSIERS PRINCIPAUX
# ============================================================================
# Dossiers de l'application
APP_DIR = BASE_DIR / "app"
BACKEND_DIR = APP_DIR / "backend"
FRONTEND_REACT_DIR = APP_DIR / "frontend-react"

# Dossiers fonctionnels
ORCHESTRATION_DIR = BASE_DIR / "orchestration"
VALIDATORS_DIR = BASE_DIR / "validators"
UTILS_DIR = BASE_DIR / "utils"

# Dossiers de données
TMP_DIR = BASE_DIR / "tmp"
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = BASE_DIR / "logs"

# ============================================================================
# CRÉATION AUTOMATIQUE DES DOSSIERS
# ============================================================================
for d in [TMP_DIR, RESULTS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================================
# VARIABLE D'ENVIRONNEMENT POUR AIRFLOW
# ============================================================================
os.environ.setdefault("DATA_QUALITY_HOME", str(BASE_DIR))

# ============================================================================
# FONCTION POUR AJOUTER LES CHEMINS AU PYTHONPATH
# ============================================================================
def add_to_syspath():
    """Ajoute tous les dossiers importants à sys.path"""
    import sys
    
    paths_to_add = [
        str(BASE_DIR),
        str(BACKEND_DIR),
        str(ORCHESTRATION_DIR),
        str(VALIDATORS_DIR),
        str(UTILS_DIR),
    ]
    
    for path in paths_to_add:
        if path not in sys.path:
            sys.path.insert(0, path)
    
    return paths_to_add

# ============================================================================
# EXPORTS PRATIQUES
# ============================================================================
__all__ = [
    "BASE_DIR",
    "APP_DIR",
    "BACKEND_DIR",
    "FRONTEND_REACT_DIR",
    "ORCHESTRATION_DIR",
    "VALIDATORS_DIR",
    "UTILS_DIR",
    "TMP_DIR",
    "RESULTS_DIR",
    "LOGS_DIR",
    "add_to_syspath",
]
