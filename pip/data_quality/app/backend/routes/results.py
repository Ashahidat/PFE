import os
import json
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from jwt_dependencies import get_current_user

RESULTS_DIR = "/home/ashahi/PFE/pip/data_quality/results"
router = APIRouter()


def flatten_results(data):
    flat_results = []

    # Parcours des catégories (duplicates, regex, etc.)
    for category, tests in data.items():
        if isinstance(tests, list):
            for test in tests:
                test["category"] = category
                flat_results.append(test)
        elif isinstance(tests, dict):
            for subkey, subtests in tests.items():
                if isinstance(subtests, list):
                    for test in subtests:
                        test["category"] = f"{category}.{subkey}"
                        flat_results.append(test)
    return flat_results


@router.get("/results/{dag_run_id}")
def get_results(dag_run_id: str, user=Depends(get_current_user)):
    """
    Retourne les résultats aplatis pour un DAG run spécifique
    """
    result_file = os.path.join(RESULTS_DIR, f"{dag_run_id}_validation.json")
    if not os.path.exists(result_file):
        # Aucun résultat pour ce DAG run
        return JSONResponse(content=[], status_code=200)

    with open(result_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    flat_data = flatten_results(data)
    return flat_data
