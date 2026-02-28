# atlas/typedefs.py - Version enrichie

def get_typedefs_payload():
    return {
        "entityDefs": [
            {
                "name": "DataSet",
                "superTypes": ["Asset"],
                "attributeDefs": [
                    {"name": "columnsCount", "typeName": "int", "isOptional": True},
                    {"name": "columnsList", "typeName": "array<string>", "isOptional": True},
                    {"name": "project", "typeName": "string", "isOptional": True}
                
                ]
            },
            {
                "name": "Column",
                "superTypes": ["Asset"],
                "attributeDefs": [
                    {"name": "type", "typeName": "string", "isOptional": True},
                    {"name": "position", "typeName": "int", "isOptional": True},
                    {"name": "logicalColumnId", "typeName": "string", "isOptional": True},
                    {
                        "name": "dataset",
                        "typeName": "DataSet",
                        "isOptional": False,
                        "cardinality": "SINGLE"
                    }
                ]
            },
            {
                "name": "DataQualityCheck",
                "superTypes": ["Asset"],
                "attributeDefs": [
                    {"name": "checkType", "typeName": "string", "isOptional": False},
                    {"name": "columnName", "typeName": "string", "isOptional": True},
                    {"name": "errorCount", "typeName": "int", "isOptional": True},
                    {"name": "ratio", "typeName": "double", "isOptional": True},
                    {"name": "executionDate", "typeName": "date", "isOptional": False},
                    {"name": "dagRunId", "typeName": "string", "isOptional": False},
                    {"name": "examples", "typeName": "string", "isOptional": True},
                    {
                        "name": "column",
                        "typeName": "Column",
                        "isOptional": True,
                        "cardinality": "SINGLE"
                    }
                ]
            }
        ],

        "relationshipDefs": [
            {
                "name": "dataset_columns",
                "typeVersion": "1.0",
                "relationshipCategory": "COMPOSITION",
                "endDef1": {
                    "type": "DataSet",
                    "name": "columns",
                    "isContainer": True,
                    "cardinality": "SET"
                },
                "endDef2": {
                    "type": "Column",
                    "name": "dataset",
                    "isContainer": False,
                    "cardinality": "SINGLE"
                }
            },
            {
                "name": "dataset_versioning",
                "typeVersion": "1.0",
                "relationshipCategory": "ASSOCIATION",
                "endDef1": {
                    "type": "DataSet",
                    "name": "previous",
                    "isContainer": False,
                    "cardinality": "SINGLE"
                },
                "endDef2": {
                    "type": "DataSet",
                    "name": "next",
                    "isContainer": False,
                    "cardinality": "SINGLE"
                }
            },
            {
                "name": "column_versioning",
                "typeVersion": "1.0",
                "relationshipCategory": "ASSOCIATION",
                "endDef1": {
                    "type": "Column",
                    "name": "previous_version",
                    "isContainer": False,
                    "cardinality": "SINGLE"
                },
                "endDef2": {
                    "type": "Column",
                    "name": "next_version",
                    "isContainer": False,
                    "cardinality": "SINGLE"
                }
            },
            {
                "name": "datasetversion_dqchecks",
                "typeVersion": "1.0",
                "relationshipCategory": "COMPOSITION",
                "endDef1": {
                    "type": "DataSet",
                    "name": "dqChecks",
                    "isContainer": True,
                    "cardinality": "SET"
                },
                "endDef2": {
                    "type": "DataQualityCheck",
                    "name": "datasetVersion",
                    "isContainer": False,
                    "cardinality": "SINGLE"
                }
            },
            {
                "name": "column_dqchecks",
                "typeVersion": "1.0",
                "relationshipCategory": "COMPOSITION",
                "endDef1": {
                    "type": "Column",
                    "name": "dqChecks",
                    "isContainer": True,
                    "cardinality": "SET"
                },
                "endDef2": {
                    "type": "DataQualityCheck",
                    "name": "column",
                    "isContainer": False,
                    "cardinality": "SINGLE"
                }
            }
        ],

        "classificationDefs": [
            {
                "name": "RESTRICTED",
                "description": "Accès restreint au département uniquement (par défaut)",
                "superTypes": []
            },
            {
                "name": "PUBLIC",
                "description": "Accès public sans restriction (exception)",
                "superTypes": []
            },
            {
                "name": "PII",
                "description": "Personally Identifiable Information",
                "superTypes": []
            },
            {
                "name": "SENSITIVE",
                "description": "Données sensibles (médicales, financières, etc.)",
                "superTypes": []
            },
            {
                "name": "DQ_SUCCESS",
                "description": "Test de qualité réussi",
                "superTypes": [],
                "attributeDefs": []
            },
            {
                "name": "DQ_FAILED",
                "description": "Test de qualité échoué",
                "superTypes": [],
                "attributeDefs": []
            },
            {
                "name": "DQ_WARNING",
                "description": "Test de qualité avec avertissement",
                "superTypes": [],
                "attributeDefs": []
            },

            # ✅ VERSION SIMPLIFIÉE MAIS STRUCTURÉE
            {
                "name": "DQ_SUMMARY",
                "description": "Résumé global de la qualité des données",
                "superTypes": [],
                "attributeDefs": [
                    {
                        "name": "summary_text",
                        "typeName": "string",
                        "isOptional": False,
                        "displayName": "Résumé qualité"
                    },
                    {
                        "name": "failed_count",
                        "typeName": "int",
                        "isOptional": False,
                        "displayName": "Nombre d'échecs"
                    }
                ]
            }
        ]
    }


typedefs_payload = get_typedefs_payload()