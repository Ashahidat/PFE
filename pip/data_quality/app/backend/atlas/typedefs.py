# atlas/typedefs.py - VERSION COMPLÈTE UNIFIÉE

typedefs_payload = {
    "entityDefs": [
        # --------------------------------------------------------------------
        # 1. DataSet - L'entité principale pour les datasets
        # --------------------------------------------------------------------
        {
            "name": "DataSet",
            "superTypes": ["Asset"],
            "attributeDefs": [
                {"name": "signature", "typeName": "string", "isOptional": True},
                {"name": "columnsCount", "typeName": "int", "isOptional": True},
                {"name": "columnsList", "typeName": "array<string>", "isOptional": True},
                # IMPORTANT : sourceUpload est OPTIONNEL pour éviter l'erreur "mandatory attribute"
                {"name": "sourceUpload", "typeName": "FileUploadProcess", "isOptional": True}
            ]
        },
        
        # --------------------------------------------------------------------
        # 2. Column - Les colonnes d'un dataset
        # --------------------------------------------------------------------
        {
            "name": "Column",
            "superTypes": ["Asset"],
            "attributeDefs": [
                {"name": "type", "typeName": "string", "isOptional": True},
                {
                    "name": "dataset",
                    "typeName": "DataSet",
                    "isOptional": False,
                    "cardinality": "SINGLE"
                }
            ]
        },
        
        # --------------------------------------------------------------------
        # 3. FileUploadProcess - Pour le Source Tracking (Upload de fichiers)
        # --------------------------------------------------------------------
        {
            "name": "FileUploadProcess",
            "superTypes": ["Process"],
            "attributeDefs": [
                {"name": "filename", "typeName": "string", "isOptional": True},
                {"name": "uploadedBy", "typeName": "string", "isOptional": True},
                {"name": "uploadTimestamp", "typeName": "date", "isOptional": True}
            ]
        },
        
        # --------------------------------------------------------------------
        # 4. ValidationProcess - Pour le Validation Tracking (Tests de qualité)
        # --------------------------------------------------------------------
        {
            "name": "ValidationProcess",
            "superTypes": ["Process"],
            "attributeDefs": [
                {"name": "dagRunId", "typeName": "string", "isOptional": True},
                {"name": "status", "typeName": "string", "isOptional": True},
                {"name": "executedBy", "typeName": "string", "isOptional": True}
            ]
        },
        
        # --------------------------------------------------------------------
        # 5. ClassificationProcess - Pour le Classification Tracking (Tags PII, etc.)
        # --------------------------------------------------------------------
        {
            "name": "ClassificationProcess",
            "superTypes": ["Process"],
            "attributeDefs": [
                {"name": "classificationType", "typeName": "string", "isOptional": True},
                {"name": "classificationName", "typeName": "string", "isOptional": True},
                {"name": "executedBy", "typeName": "string", "isOptional": True},
                {"name": "executionTimestamp", "typeName": "date", "isOptional": True}
            ]
        }
    ],
    
    "relationshipDefs": [
        # --------------------------------------------------------------------
        # 1. Relation Dataset ↔ Columns (COMPOSITION)
        # Un dataset contient des colonnes
        # --------------------------------------------------------------------
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
        
        # --------------------------------------------------------------------
        # 2. Relation Dataset Versioning
        # Un dataset peut avoir une version précédente/suivante
        # --------------------------------------------------------------------
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
        
        # --------------------------------------------------------------------
        # 3. Source Tracking: Upload → Dataset
        # Un FileUploadProcess produit un DataSet
        # --------------------------------------------------------------------
        {
            "name": "dataset_uploaded_by",
            "typeVersion": "1.0",
            "relationshipCategory": "COMPOSITION",
            "endDef1": {
                "type": "FileUploadProcess",
                "name": "outputDatasets",
                "isContainer": True,
                "cardinality": "SET"
            },
            "endDef2": {
                "type": "DataSet", 
                "name": "sourceUpload",
                "isContainer": False,
                "cardinality": "SINGLE"
            }
        },
        
        # --------------------------------------------------------------------
        # 4. Validation Tracking: Dataset → Validation
        # Un ValidationProcess valide un DataSet
        # --------------------------------------------------------------------
        {
            "name": "dataset_validated_by",
            "typeVersion": "1.0",
            "relationshipCategory": "ASSOCIATION",
            "endDef1": {
                "type": "ValidationProcess",
                "name": "validatedDatasets",
                "isContainer": False,
                "cardinality": "SINGLE"
            },
            "endDef2": {
                "type": "DataSet",
                "name": "validationRuns",
                "isContainer": False,
                "cardinality": "SET"
            }
        },
        
        # --------------------------------------------------------------------
        # 5. Classification Tracking: Dataset → Classification
        # Un ClassificationProcess classe un DataSet
        # --------------------------------------------------------------------
        {
            "name": "dataset_classified_by",
            "typeVersion": "1.0",
            "relationshipCategory": "ASSOCIATION",
            "endDef1": {
                "type": "ClassificationProcess",
                "name": "classifiedDatasets",
                "isContainer": False,
                "cardinality": "SINGLE"
            },
            "endDef2": {
                "type": "DataSet",
                "name": "classificationEvents",
                "isContainer": False,
                "cardinality": "SET"
            }
        },
        
        # --------------------------------------------------------------------
        # 6. Classification Tracking: Column → Classification
        # Un ClassificationProcess classe une Column
        # --------------------------------------------------------------------
        {
            "name": "column_classified_by",
            "typeVersion": "1.0",
            "relationshipCategory": "ASSOCIATION",
            "endDef1": {
                "type": "ClassificationProcess",
                "name": "classifiedColumns",
                "isContainer": False,
                "cardinality": "SINGLE"
            },
            "endDef2": {
                "type": "Column",
                "name": "classificationEvents",
                "isContainer": False,
                "cardinality": "SET"
            }
        }
    ],

    "classificationDefs": [
        # --------------------------------------------------------------------
        # Classifications pour les datasets
        # --------------------------------------------------------------------
        {
            "name": "PUBLIC",
            "description": "Accès public sans restriction",
            "superTypes": []
        },
        {
            "name": "INTERNAL",
            "description": "Usage interne à l'organisation",
            "superTypes": []
        },
        {
            "name": "CONFIDENTIAL",
            "description": "Données confidentielles, accès restreint",
            "superTypes": [],
            "attributeDefs": [
                {"name": "level", "typeName": "string", "isOptional": True, "defaultValue": "1"}
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
        
        # --------------------------------------------------------------------
        # Classifications pour les colonnes
        # --------------------------------------------------------------------
        {
            "name": "PII_DIRECT",
            "description": "Identifiants directs (nom, email, téléphone...)",
            "superTypes": []
        },
        {
            "name": "PII_QUASI",
            "description": "Quasi-identifiants (âge, code postal, profession...)",
            "superTypes": []
        },
        {
            "name": "SENSITIVE",
            "description": "Données sensibles (salaire, santé, opinion...)",
            "superTypes": []
        },
        {
            "name": "ENCRYPTED",
            "description": "Données chiffrées",
            "superTypes": []
        }
    ]
}