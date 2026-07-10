# Guide de deploiement

Ce projet peut etre deployee comme une stack locale "production-like" ou comme une demo de soutenance.
L'objectif ici est d'avoir un chemin clair, reproductible, et documente.

## 1. Prerequis

- Python 3.10+ avec `pip`
- Node.js 18+ avec `npm`
- PostgreSQL
- Java compatible avec Apache Atlas
- Grafana si tu veux les dashboards
- `nginx` si tu veux les proxies read-only Atlas/Grafana

## 2. Variables d'environnement

Les valeurs par defaut permettent de demarrer en local, mais pour un deploiement propre il faut definir au minimum:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `ATLAS_REST_ADDRESS`
- `ATLAS_USERNAME`
- `ATLAS_PASSWORD`

Recommandes aussi:

- `ATLAS_APPLICATION_LOG`
- `GRAFANA_URL`
- `GRAFANA_SERVICE_TOKEN`
- `GRAFANA_ADMIN_USER`
- `GRAFANA_ADMIN_PASSWORD`
- `GRAFANA_PROVISIONING_ENABLED`

## 3. Base de donnees

Le backend attend PostgreSQL avec la base et les tables du projet.

Le chemin le plus simple est:

1. Creer la base `pfe_db`.
2. Executer les scripts dans `db_tables/`.
3. Verifier que l'utilisateur DB utilise dans `DATABASE_URL` a bien les droits sur la base.

Exemple de connexion locale:

```bash
DATABASE_URL=postgresql://pfe_user:12345@localhost:5432/pfe_db
```

## 4. Backend FastAPI

Le backend vit dans `pip/data_quality/app/backend/`.

### Dependances Python

Le depot centralise les dependances dans `librairies.txt`.

```bash
pip install -r librairies.txt
```

### Lancement

Pour un deploiement, evite le mode reload:

```bash
cd pip/data_quality/app/backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

Le backend sert aussi le build React si `pip/data_quality/app/frontend-react/dist/` existe.

## 5. Frontend React

```bash
cd pip/data_quality/app/frontend-react
npm install
npm run build
```

En mode dev seulement:

```bash
npm run dev
```

L'UI de production est ensuite servie par FastAPI sur `http://<host>:8000/`.

## 6. Atlas

Deux couches sont utilisees:

- Atlas interne pour les ecritures: `http://127.0.0.1:21002`
- Atlas read-only pour les humains: `http://<host>:21001`

Les scripts utiles:

- `pip/data_governance/start_atlas_readonly_stack.sh`
- `pip/data_governance/stop_atlas_readonly_stack.sh`
- `pip/data_governance/check_atlas_ports.sh`

Si tu changes l'URL ou les identifiants Atlas, pense a mettre a jour:

- `ATLAS_REST_ADDRESS`
- `ATLAS_USERNAME`
- `ATLAS_PASSWORD`

## 7. Grafana

Le backend expose le proxy Grafana sur:

- `http://localhost:8000/api/grafana/`

Le demarrage local passe par:

- `pip/data_governance/start_grafana_readonly_stack.sh`

Le provisioning depend de:

- `GRAFANA_URL`
- `GRAFANA_SERVICE_TOKEN` ou `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`
- `GRAFANA_DASHBOARD_TEMPLATES_DIR`

## 8. Ordre recommande de demarrage

1. PostgreSQL
2. Atlas interne
3. Backend FastAPI
4. Build React
5. Grafana
6. Nginx read-only Atlas si tu veux l'interface publique Atlas

## 9. Verification

Une fois tout lance:

- ouvrir `http://localhost:8000/app/login`
- verifier `http://localhost:8000/openapi.json`
- verifier Atlas via le port read-only ou interne selon le besoin
- verifier Grafana via `http://localhost:8000/api/grafana/`

## 10. Ce qu'il faut presenter a l'encadrant

Si tu dois resumer le projet en une phrase:

- l'application permet de gerer la data quality, de synchroniser certaines metadonnees vers Atlas, et d'exposer des dashboards Grafana avec un backend FastAPI et une UI React.

Si tu dois resumer le deploiement:

- PostgreSQL stocke les donnees applicatives
- FastAPI sert l'API et l'UI compilee
- Atlas est accessible en interne pour les ecritures et en read-only pour la consultation
- Grafana est proxye via le backend

