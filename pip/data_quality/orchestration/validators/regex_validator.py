# validators/regex_validator.py
from typing import List, Dict, Any
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, trim
from great_expectations.dataset import SparkDFDataset

DEFAULT_REGEX = {
    "email": r"^[\w\.-]+@[\w\.-]+\.\w+$",
    "phone": r"^\+?\d{8,15}$",
    "postal_code": r"^\d{5}$",
    "numeric": r"^\d+$",
    "alphanumeric": r"^[a-zA-Z0-9]+$",
    "date": r"^\d{4}-\d{2}-\d{2}$",
    "ip": r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
    # Ajoutez d'autres règles selon vos besoins
}

def run(df: DataFrame, user_selection: Dict[str, Any]) -> Dict:
    """
    Validateur de colonnes via regex (GE + Spark).
    
    user_selection peut être:
    
    Format 1 (liste): [
        {"column": "email", "rule_type": "email"},
        {"column": "telephone", "rule_type": "phone"},
        {"column": "nom", "rule_type": "alphanumeric"}
    ]
    
    Format 2 (objet dict pour compatibilité): {"email": ["email"], "telephone": ["phone"]}
    """
    results = []
    max_examples = 5
    
    # Détection du format
    rules_list = []
    
    if isinstance(user_selection, list):
        # Format 1: Liste de dictionnaires
        rules_list = user_selection
    elif isinstance(user_selection, dict):
        # Format 2: Ancien format dict
        known_regex_types = set(DEFAULT_REGEX.keys())
        is_format_2 = any(key in known_regex_types for key in user_selection.keys())
        
        if is_format_2:
            # Convertir format 2 vers format 1
            for rule_type, columns in user_selection.items():
                for col_name in columns:
                    rules_list.append({
                        "column": col_name,
                        "rule_type": rule_type
                    })
        else:
            # Format 3: {colonne: [rules]}
            for col_name, rule_types in user_selection.items():
                for rule_type in rule_types:
                    rules_list.append({
                        "column": col_name,
                        "rule_type": rule_type
                    })
    
    # Exécuter chaque validation individuellement
    for rule_config in rules_list:
        col_name = rule_config.get("column")
        rule_type = rule_config.get("rule_type")
        
        # Vérifier si la colonne existe
        if col_name not in df.columns:
            results.append({
                "alerte": f"La colonne '{col_name}' n'existe pas dans le dataset",
                "type de test": f"regex_{rule_type}",
                "statut": "ignoré",
                "colonne testée": col_name,
                "nombre": 0,
                "ratio": "0/0",
                "exemples": [],
                "erreur": f"Colonne '{col_name}' non trouvée"
            })
            continue
        
        # Vérifier si la règle existe
        pattern = DEFAULT_REGEX.get(rule_type)
        if pattern is None:
            results.append({
                "alerte": f"Type de regex '{rule_type}' non supporté. Types disponibles: {list(DEFAULT_REGEX.keys())}",
                "type de test": f"regex_{rule_type}",
                "statut": "ignoré",
                "colonne testée": col_name,
                "nombre": 0,
                "ratio": "0/0",
                "exemples": []
            })
            continue
        
        # Nettoyer et filtrer les valeurs non nulles
        non_empty_df = df.withColumn(col_name, trim(col(col_name))) \
                         .filter(
                             (col(col_name).isNotNull()) &
                             (col(col_name) != "") &
                             (col(col_name) != "NULL")
                         )
        
        total_count = non_empty_df.count()
        
        if total_count == 0:
            results.append({
                "alerte": f"Aucune donnée à valider pour la colonne '{col_name}'",
                "type de test": f"regex_{rule_type}",
                "statut": "réussi",
                "colonne testée": col_name,
                "nombre": 0,
                "ratio": "0/0",
                "exemples": []
            })
            continue
        
        validator = SparkDFDataset(non_empty_df)
        
        try:
            result = validator.expect_column_values_to_match_regex(
                column=col_name,
                regex=pattern,
                meta={"rule": f"{col_name}_{rule_type}_check"}
            )
            
            unexpected_count = result.result.get("unexpected_count", 0)
            examples = result.result.get("partial_unexpected_list", [])[:max_examples]
            statut = "réussi" if result.success else "échoué"
            
            if not result.success:
                entry = {
                    "alerte": f"Des valeurs non conformes ont été détectées sur la colonne '{col_name}' avec la règle '{rule_type}'",
                    "type de test": f"regex_{rule_type}",
                    "statut": "échoué",
                    "colonne testée": col_name,
                    "nombre": unexpected_count,
                    "ratio": f"{unexpected_count}/{total_count}",
                    "exemples": examples
                }
            else:
                entry = {
                    "type de test": f"regex_{rule_type}",
                    "statut": "réussi",
                    "colonne testée": col_name,
                    "nombre": unexpected_count,
                    "ratio": f"{unexpected_count}/{total_count}",
                }
            
            results.append(entry)
            
        except Exception as e:
            results.append({
                "alerte": f"Échec technique de la validation de la colonne '{col_name}'",
                "type de test": f"regex_{rule_type}",
                "statut": "échoué",
                "colonne testée": col_name,
                "nombre": total_count,
                "ratio": f"{total_count}/{total_count}",
                "exemples": ["Validation failed"],
                "error": str(e)
            })
    
    return {"regex": results}