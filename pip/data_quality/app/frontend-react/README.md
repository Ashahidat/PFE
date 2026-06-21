# React UI (PFE)

Cette UI remplace l'ancienne UI statique et est désormais la seule interface servie par le backend.

## Dev (Vite)

Dans un terminal :

```bash
cd pip/data_quality/app/frontend-react
npm install
npm run dev
```

Puis ouvrir :
- `http://localhost:5173/app/login` (proxy vers le backend via `/api`)

Liens externes:
- Atlas pointe par défaut vers `http://<host>:21001/n/index.html` pour ouvrir la BETA UI
- Grafana pointe par défaut vers le proxy backend `http://<host>/api/grafana/`
- tu peux surcharger ces URL avec `VITE_ATLAS_UI_URL` et `VITE_GRAFANA_DASHBOARDS_URL` avant `npm run build`
- si tu veux utiliser le proxy backend FastAPI pour Grafana, définis explicitement `VITE_GRAFANA_DASHBOARDS_URL=/api/grafana/`

## Build + Serve via FastAPI

```bash
cd pip/data_quality/app/frontend-react
npm install
npm run build
```

Ensuite, lancer le backend FastAPI, et ouvrir :
- `http://localhost:8000/app/login`

Notes :
- le backend sert le build React si `pip/data_quality/app/frontend-react/dist/` existe.
