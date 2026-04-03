# validators/deequ_validator.py
from typing import List, Dict, Any
import os
os.environ["SPARK_VERSION"] = "3.3"
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pydeequ.verification import VerificationSuite, VerificationResult 
from pydeequ.checks import Check, CheckLevel  


def run(spark: SparkSession, df: DataFrame, constraints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validateur Deequ pour contraintes de qualité
    
    Format des contraintes:
    [
        {"type": "completeness", "column": "email", "threshold": 0.95},
        {"type": "min", "column": "age", "threshold": 18},
        {"type": "max", "column": "age", "threshold": 120},
        {"type": "allowed_values", "column": "status", "values": ["ACTIF", "INACTIF"]}
    ]
    """
    results = []
    
    if not constraints:
        return results
    
    total_rows = df.count()
    
    for constraint in constraints:
        constraint_type = constraint.get("type")
        column = constraint.get("column")
        
        # Validation de base
        if not column:
            results.append({
                "type de test": f"deequ_{constraint_type}",
                "statut": "ignoré",
                "colonne testée": "N/A",
                "nombre": 0,
                "ratio": f"0/{total_rows}",
                "exemples": ["Colonne non spécifiée"]
            })
            continue
        
        if column not in df.columns:
            results.append({
                "type de test": f"deequ_{constraint_type}",
                "statut": "ignoré",
                "colonne testée": column,
                "nombre": 0,
                "ratio": f"0/{total_rows}",
                "exemples": [f"Colonne '{column}' inexistante"]
            })
            continue
        
        try:
            # Construire le check Deequ
            check = Check(spark, CheckLevel.Error, f"{constraint_type}_{column}")
            
            if constraint_type == "completeness":
                threshold = constraint.get("threshold", 1.0)
                check = check.hasCompleteness(column, lambda c: c >= threshold)
                description = f"Taux de complétude >= {threshold*100}%"
                
            elif constraint_type == "min":
                threshold = constraint.get("threshold")
                check = check.hasMin(column, lambda c: c >= threshold)
                description = f"Valeur min >= {threshold}"
                
            elif constraint_type == "max":
                threshold = constraint.get("threshold")
                check = check.hasMax(column, lambda c: c <= threshold)
                description = f"Valeur max <= {threshold}"
                
            elif constraint_type == "allowed_values":
                values = constraint.get("values", [])
                check = check.isContainedIn(column, values)
                description = f"Valeurs autorisées: {values}"
                
            else:
                results.append({
                    "type de test": f"deequ_{constraint_type}",
                    "statut": "ignoré",
                    "colonne testée": column,
                    "nombre": 0,
                    "ratio": f"0/{total_rows}",
                    "exemples": [f"Type '{constraint_type}' non supporté"]
                })
                continue
            
            # Exécuter la vérification
            verification_result = VerificationSuite(spark) \
                .onData(df) \
                .addCheck(check) \
                .run()
            
            # Extraire le résultat
            success = verification_result.status == "Success"
            
            # pydeequ retourne checkResults en JSON (dict/list), pas en objets Python attributés
            check_results_json = verification_result.checkResults
            
            if success:
                results.append({
                    "type de test": f"deequ_{constraint_type}",
                    "statut": "réussi",
                    "colonne testée": column,
                    "nombre": 0,
                    "ratio": f"0/{total_rows}",
                    "description": description
                })
            else:
                actual_value = None
                error_count = 1

                # Uniformiser la sémantique du ratio avec le reste: x/total_rows
                if constraint_type == "completeness":
                    error_count = df.filter(
                        F.col(column).isNull() | (F.trim(F.col(column).cast("string")) == "")
                    ).count()
                elif constraint_type == "min":
                    error_count = df.filter(
                        F.col(column).isNotNull() & (F.col(column) < F.lit(threshold))
                    ).count()
                elif constraint_type == "max":
                    error_count = df.filter(
                        F.col(column).isNotNull() & (F.col(column) > F.lit(threshold))
                    ).count()
                elif constraint_type == "allowed_values":
                    error_count = df.filter(
                        F.col(column).isNull() | (~F.col(column).isin(values))
                    ).count()
                
                results.append({
                    "alerte": f"Contrainte non respectée: {description}",
                    "type de test": f"deequ_{constraint_type}",
                    "statut": "échoué",
                    "colonne testée": column,
                    "nombre": error_count,
                    "ratio": f"{error_count}/{total_rows}",
                    "description": description,
                    "valeur_actuelle": actual_value,
                    "exemples": [
                        "La contrainte n'a pas été satisfaite",
                        str(check_results_json)[:200]
                    ]
                })
                
        except Exception as e:
            results.append({
                "alerte": f"Erreur technique Deequ: {str(e)[:150]}",
                "type de test": f"deequ_{constraint_type}",
                "statut": "échoué",
                "colonne testée": column,
                "nombre": total_rows,
                "ratio": f"{total_rows}/{total_rows}",
                "exemples": [str(e)[:200]]
            })
    
    return results
