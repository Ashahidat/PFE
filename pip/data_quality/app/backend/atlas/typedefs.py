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
                {
                    "name": "dataset",
                    "typeName": "DataSet",
                    "isOptional": False,
                    "cardinality": "SINGLE"
                }
            ]
        },
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
    ],

    "classificationDefs": [
        # Dataset classifications - ONLY TWO
        {
            "name": "RESTRICTED",
            "description": "Accès restreint au département uniquement (par défaut)",
            "superTypes": []
            # NO ATTRIBUTES - just the name indicates department-only
        },
        {
            "name": "PUBLIC",
            "description": "Accès public sans restriction (exception)",
            "superTypes": []
        },
        
        # Column classifications - PII/SENSITIVE only
        {
            "name": "PII",
            "description": "Personally Identifiable Information",
            "superTypes": []
        },
        {
            "name": "SENSITIVE",
            "description": "Données sensibles (médicales, financières, etc.)",
            "superTypes": []
        }
    ]
}