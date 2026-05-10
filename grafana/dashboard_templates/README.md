Ces dashboards sont des **templates certifiés** versionnés dans le repo.

Ils ne sont pas destinés à être importés manuellement via l’UI Grafana.

Usage :
- L’application backend provisionne automatiquement (API Grafana) un folder par projet, puis publie 4 dashboards (Qualité, Lineage, Pipeline, Gouvernance) en clonant ces templates.
- Les placeholders `__PROJECT_ID__` et `__PROJECT_NAME__` sont remplacés à la publication.

Objectif :
- Dashboards “Dashboard as Code”
- Zéro modification depuis l’UI (humains en `Viewer`)
- Séparation stricte des périmètres via folders + permissions

