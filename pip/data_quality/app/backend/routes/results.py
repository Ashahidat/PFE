import os
import json
from fastapi import APIRouter
from fastapi.responses import JSONResponse

RESULTS_DIR = "/home/ashahi/PFE/pip/data_quality/results"
router = APIRouter()

def flatten_results(data):
    flat_results = []

    # Parcours des catégories (duplicates, regex, etc.)
    for category, tests in data.items():
        if isinstance(tests, list):
            # parfois tests est déjà une liste
            for test in tests:
                test["category"] = category
                flat_results.append(test)
        elif isinstance(tests, dict):
            # ex: {"duplicates": [...], "regex": [...]}
            for subkey, subtests in tests.items():
                if isinstance(subtests, list):
                    for test in subtests:
                        test["category"] = f"{category}.{subkey}"
                        flat_results.append(test)
    return flat_results

@router.get("/results")
def get_results():
    result_file = os.path.join(RESULTS_DIR, "validation.json")
    if not os.path.exists(result_file):
        return JSONResponse(content=[], status_code=200)

    with open(result_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    flat_data = flatten_results(data)
    return flat_data
