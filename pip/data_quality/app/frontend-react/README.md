# React UI (PFE)

Cette UI remplace progressivement l'ancienne UI statique (`pip/data_quality/app/frontend/`).

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
- l'ancienne UI reste accessible via `http://localhost:8000/ui`.

