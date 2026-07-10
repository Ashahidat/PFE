# PFE Data Quality and Governance

Application de data quality et data governance avec:

- un backend FastAPI
- une UI React/Vite servie par le backend
- PostgreSQL pour la persistence
- Apache Atlas pour la gouvernance
- Grafana pour le pilotage et les dashboards
- Airflow et des scripts de validation/orchestration

## Architecture

- `pip/data_quality/app/backend/` expose l'API `FastAPI`
- `pip/data_quality/app/frontend-react/` contient l'interface React
- `pip/data_governance/` contient Atlas, Nginx et les helpers de stack
- `db_tables/` contient les scripts SQL d'initialisation et de mise a jour
- `grafana/` contient les dashboards et la configuration de provisioning

## Dossier de reference

La documentation la plus utile pour le rendu est:

- [Guide de deploiement](DEPLOYMENT.md)
- [Problemes Atlas](README_TROUBLESHOOTING_ATLAS.md)
- [UI Atlas read-only](pip/data_governance/README_ATLAS_READONLY_UI.md)
- [Proxy Grafana](grafana/AUTH_PROXY_SETUP.md)

## Lancement rapide en local

1. Preparer PostgreSQL et creer la base `pfe_db`.
2. Installer les dependances Python depuis `librairies.txt`.
3. Installer les dependances frontend dans `pip/data_quality/app/frontend-react`.
4. Construire l'UI React avec `npm run build`.
5. Lancer Atlas en lecture/criture sur le port interne `21002`.
6. Lancer le backend FastAPI sur `8000`.
7. Lancer Grafana si tu veux les dashboards.

Une fois le build React genere, le backend sert l'application sur:

- `http://localhost:8000/`
- `http://localhost:8000/app/login`

## Variables d'environnement utiles

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `ATLAS_REST_ADDRESS`
- `ATLAS_USERNAME`
- `ATLAS_PASSWORD`
- `ATLAS_APPLICATION_LOG`
- `GRAFANA_URL`
- `GRAFANA_SERVICE_TOKEN`
- `GRAFANA_ADMIN_USER`
- `GRAFANA_ADMIN_PASSWORD`
- `GRAFANA_DASHBOARD_TEMPLATES_DIR`
- `GRAFANA_PROVISIONING_ENABLED`

## Ports principaux

- `8000` backend FastAPI
- `5173` frontend Vite en dev
- `21001` Atlas read-only pour les humains
- `21002` Atlas interne pour les ecritures
- `3000` Grafana par defaut

## Notes de deploiement

- Le build frontend doit etre genere avant le lancement du backend si tu veux servir l'UI depuis FastAPI.
- Le backend parle a Atlas via `ATLAS_REST_ADDRESS`, par defaut `http://127.0.0.1:21002`.
- Le JWT et la base de donnees sont maintenant parametrables via variables d'environnement.
- Les scripts dans `pip/data_governance/` demarrent des stacks locales, pas une stack cloud "production-ready" cle en main.

## Commandes utiles

```bash
cd pip/data_quality/app/frontend-react
npm install
npm run build

cd ../backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

