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
