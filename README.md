# Projet PFE — Setup & Run (WSL2)

Ce dépôt contient :

- un backend FastAPI & Spark dans `pip/data_quality/app/backend`
- un frontend statique (sans bundle/npm) dans `pip/data_quality/app/frontend`
- des dashboards Grafana prêts à l’emploi dans `grafana/`

## 1. Préparer la machine (WSL2)

1. `bash scripts/bootstrap_wsl.sh` (met à jour `apt`, installe Python, OpenJDK, libpq, curl, etc.)
2. `python3 -m venv env`
3. `source env/bin/activate`
4. `pip install -r pip/data_quality/app/backend/requirements.txt`

> Les scripts `scripts/run_backend.sh` et `scripts/run_frontend.sh` encapsulent les commandes de démarrage et active le bon répertoire.

## 2. Lancer les services principaux

1. **Backend FastAPI**  
   ```bash
   scripts/run_backend.sh
   ```

2. **Frontend statique** (servie par un simple `http.server`)  
   ```bash
   scripts/run_frontend.sh
   ```

3. **Grafana (optionnel, installé nativement)**  
   ```bash
   scripts/install_grafana_native.sh
   scripts/grafana_service.sh start
   ```
   Un service systemd `grafana-server` est également disponible (`status`/`stop` via `scripts/grafana_service.sh`). Grafana écoute sur `http://localhost:3000` avec `admin:admin` par défaut et peut reprendre les dashboards dans `grafana/`.


## 3. Arrêter les services

- Backend : `Ctrl+C` dans le terminal de `scripts/run_backend.sh`  
- Frontend : `Ctrl+C` dans le terminal de `scripts/run_frontend.sh`  
- Grafana : `scripts/grafana_service.sh stop`

## 4. Orchestrateurs (Airflow + Atlas)

### Airflow

- Airflow tourne dans le venv backend (déjà listé dans `pip/data_quality/app/backend/requirements.txt`).  
- Lance le mode autonome (webserver + scheduler) avec `scripts/run_airflow.sh`.  
- L’UI est disponible sur `http://localhost:8080` (identifiants `admin/admin` par défaut).  
- `Ctrl+C` arrête le serveur ; relance en réexécutant le script.

### Apache Atlas

- Atlas vit dans `pip/data_governance/apache-atlas-2.4.0`. Le script `scripts/atlas_service.sh` enveloppe l’ancienne logique de `apache-atlas/bin/atlas_start.py`/`atlas_stop.py` et les démarrages HBase.
- Démarre Atlas via `scripts/atlas_service.sh start` (les logs remontent dans `pip/data_governance/apache-atlas-2.4.0/logs/atlas-stdout.log`). La console Web est en `http://localhost:21000`.
- Stoppe avec `scripts/atlas_service.sh stop`. Utilise `scripts/atlas_service.sh status` pour vérifier et `scripts/atlas_service.sh restart` pour relancer.
- Besoin de repartir de zéro ? `pip/data_governance/reset_atlas.sh` nettoie HBase/Solr.

## 4. Quelques remarques de déploiement

- Les dépendances Python vivent dans `pip/data_quality/app/backend/requirements.txt`; gardez-le synchronisé avec vos `pip install`.  
- Spark est déclenché depuis le backend ; si vous testez sans Spark, commentez les imports/démarrages dans `config.py`/`main.py`.  
- Postgres doit rester accessible sur `localhost:5432`. Airflow/Atlas ont leur propre documentation (`pip/data_quality/orchestration`).  
- Exécutez `bash scripts/bootstrap_wsl.sh` chaque fois que vous redéployez sur une machine propre.
