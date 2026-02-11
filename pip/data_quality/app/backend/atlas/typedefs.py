typedefs_payload = {
    "entityDefs": [
        {
            "name": "DataSet",
            "superTypes": ["Asset"],
            "attributeDefs": [
                {"name": "signature", "typeName": "string", "isOptional": True},
                {"name": "columnsCount", "typeName": "int", "isOptional": True},
                {"name": "columnsList", "typeName": "array<string>", "isOptional": True}
            ]
        },
        {
            "name": "Column",
            "superTypes": ["Asset"],
            "attributeDefs": [
                {"name": "type", "typeName": "string", "isOptional": True},
                {"name": "logicalColumnId", "typeName": "string", "isOptional": False},
                {
                    "name": "dataset",
                    "typeName": "DataSet",
                    "isOptional": False,
                    "cardinality": "SINGLE"
                }
            ]
        },

        # 🆕 ENTITÉ HISTORIQUE DE CLASSIFICATION
        {
            "name": "ClassificationHistory",
            "superTypes": ["Asset"],  
            "attributeDefs": [
                {
                    "name": "classificationType",
                    "typeName": "string",
                    "isOptional": False
                },
                {
                    "name": "appliedAt",
                    "typeName": "date",
                    "isOptional": False
                },
                {
                    "name": "appliedBy",
                    "typeName": "string",
                    "isOptional": False
                },
                {
                    "name": "status",
                    "typeName": "string",
                    "isOptional": False  # ACTIVE / INACTIVE
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

        # 🆕 RELATION HISTORIQUE ↔ COLONNE
        {
            "name": "has_classification_history",
            "typeVersion": "1.0",
            "relationshipCategory": "ASSOCIATION",
            "endDef1": {
                "type": "Column",
                "name": "classificationHistory",
                "isContainer": False,
                "cardinality": "SET"
            },
            "endDef2": {
                "type": "ClassificationHistory",
                "name": "appliedToColumn",
                "isContainer": False,
                "cardinality": "SINGLE"
            }
        },

        {
            "name": "classification_history_lineage",
            "typeVersion": "1.0",
            "relationshipCategory": "ASSOCIATION",
            "endDef1": {
                "type": "ClassificationHistory",
                "name": "previous",
                "isContainer": False,
                "cardinality": "SINGLE"
            },
            "endDef2": {
                "type": "ClassificationHistory",
                "name": "next",
                "isContainer": False,
                "cardinality": "SINGLE"
            }
        }
    ],

    "classificationDefs": [
        {"name": "PUBLIC", "description": "Accès public sans restriction", "superTypes": []},
        {"name": "INTERNAL", "description": "Usage interne à l'organisation", "superTypes": []},
        {
            "name": "CONFIDENTIAL",
            "description": "Données confidentielles, accès restreint",
            "superTypes": [],
            "attributeDefs": [
                {
                    "name": "level",
                    "typeName": "string",
                    "isOptional": True,
                    "defaultValue": "1"
                }
            ]
        },
        {
            "name": "RESTRICTED",
            "description": "Données hautement sensibles, accès très contrôlé",
            "superTypes": [],
            "attributeDefs": [
                {"name": "reason", "typeName": "string", "isOptional": True}
            ]
        },
        {"name": "PII_DIRECT", "description": "Identifiants directs", "superTypes": []},
        {"name": "PII_QUASI", "description": "Quasi-identifiants", "superTypes": []},
        {"name": "SENSITIVE", "description": "Données sensibles", "superTypes": []},
        {"name": "ENCRYPTED", "description": "Données chiffrées", "superTypes": []}
    ]
}
