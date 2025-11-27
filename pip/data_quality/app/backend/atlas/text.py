import os
from difflib import SequenceMatcher

def string_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def extract_base_name(name: str) -> str:
    return os.path.splitext(os.path.basename(name))[0].lower()
