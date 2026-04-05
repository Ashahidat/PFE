# Grafana (MVP) for PFE

This folder adds a minimal Grafana setup focused on monitoring your PostgreSQL `pfe_db`.

## Start

From repo root:

```bash
docker compose -f docker-compose.grafana.yml up -d
```

Grafana UI: `http://localhost:3000`

Default credentials:
- user: `admin`
- password: `admin`

## Data source

Grafana connects to Postgres using the built-in PostgreSQL data source.

If Postgres is running on your host at `localhost:5432`, the container should use:
- `host.docker.internal` (Docker Desktop)
- or `172.17.0.1` (typical Linux Docker bridge)

This repo defaults to `host.docker.internal`. If you are on Linux and it does not resolve, either:
- edit `docker-compose.grafana.yml` and set `GF_POSTGRES_HOST=172.17.0.1`, or
- add Docker's host-gateway mapping (see compose file).

## Dashboards

Provisioned dashboards (starter):
- **PFE - Pipeline Health** (DAG runs + execution times)
- **PFE - Data Quality** (checks results)
- **PFE - Push Atlas** (push_history, similarity score, propagation)

