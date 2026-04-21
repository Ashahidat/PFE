# Atlas & Data Quality — Notes de debug (local)

Ce document sert à **comprendre** les erreurs (au lieu de “corriger à l’aveugle”) et à pouvoir **rejouer** les étapes facilement sur une autre machine.

## 1) Démarrage Atlas (local)

Dans ce repo, Atlas est dans `pip/data_governance/apache-atlas-2.4.0/`.

- Setup + start (une fois si besoin) :
  - `cd pip/data_governance/apache-atlas-2.4.0/bin && ./atlas_start.py -setup`
- Start (normal) :
  - `cd pip/data_governance/apache-atlas-2.4.0/bin && ./atlas_start.py`

Logs Atlas :
- `pip/data_governance/apache-atlas-2.4.0/logs/application.log`
- `pip/data_governance/apache-atlas-2.4.0/logs/atlas.*.out` / `atlas.*.err`

## 2) Vérifications “Atlas est OK”

### 2.1 API version (doit renvoyer 200)

- `curl -i -u admin:admin http://localhost:21000/api/atlas/admin/version`

Si vous avez un `503 Service Unavailable`, Atlas n’est pas prêt (ou vient de redémarrer). Attendre un peu et regarder `application.log`.

### 2.2 Profil utilisateur Atlas (`__AtlasUserProfile`)

Symptôme typique :
- `There was an error processing your request. It has been logged (ID ....)` sur certaines routes
- et dans `application.log` : `Instance __AtlasUserProfile with unique attribute {name=admin} does not exist`

Vérifier :
- `curl -u admin:admin "http://localhost:21000/api/atlas/v2/entity/uniqueAttribute/type/__AtlasUserProfile?attr:name=admin"`

Créer (si absent) :
- `curl -u admin:admin -H "Content-Type: application/json" -X POST http://localhost:21000/api/atlas/v2/entity -d '{"entity":{"typeName":"__AtlasUserProfile","attributes":{"name":"admin","qualifiedName":"admin@atlas"}}}'`

Automatique après reset (script) :
- `./scripts/atlas_ensure_admin_profile.sh`

## 3) Erreurs “setup_lock” / ZooKeeper

Dans `application.log`, si vous voyez :
- `Error running setup steps`
- `ConnectionLossException ... /apache_atlas/setup_lock`
- `You do not own the lock: /apache_atlas/setup_lock`

Ça pointe vers un **problème de lock ZooKeeper** (Atlas n’arrive pas à exécuter ses setup steps).
Dans ce cas, la priorité est d’inspecter `application.log` + les logs `atlas.*.err` et de stabiliser le démarrage (plutôt que d’augmenter la RAM à l’aveugle).

## 4) Pourquoi Atlas affiche un “résumé qualité” mais la DB reste vide ?

Dans le backend, le résumé “qualité” envoyé à Atlas est calculé à partir des JSON dans `pip/data_quality/results/`.
Il est possible d’avoir :
- résumé ajouté dans Atlas
- MAIS rien inséré dans `data_quality_results`

Cause fréquente : l’étape “sauvegarde PostgreSQL” n’a pas été exécutée (exception côté backend).

Correctif appliqué :
- `pip/data_quality/app/backend/routes/push_atlas.py` importe maintenant explicitement :
  - `create_data_quality_checks_from_json` (envoi vers Atlas)
  - `save_data_quality_results_from_json` (insert en DB)
- et la sauvegarde DB est rendue **indépendante** de l’envoi Atlas (si Atlas plante, la DB peut quand même être remplie, et inversement).

## 5) Pourquoi `data_quality_results` n’est pas rempli avec `/run-dag-v2` ?

`/run-dag-v2` :
- déclenche le DAG Airflow
- enregistre un enregistrement dans `dag_runs`
- écrit un fichier JSON de résultats dans `pip/data_quality/results/{dag_run_id}_validation.json`

Mais **ne peut pas remplir `data_quality_results`** tout seul, car la table `data_quality_results` exige `dataset_version_id` (non-null), et aujourd’hui `dataset_versions.atlas_guid` est non-null : une “version” est créée lors du `push-atlas` (quand Atlas est impliqué).

Donc, avec le modèle actuel :
- pour remplir `data_quality_results`, il faut passer par `POST /push-atlas/{dataset_id}` (qui a un `DatasetVersion`).

## 6) Où chercher quand Atlas renvoie “It has been logged (ID …)”

1. Récupérer l’ID exact depuis l’erreur (ex: `3d2871b5b1de824e`)
2. Rechercher dans :
   - `pip/data_governance/apache-atlas-2.4.0/logs/application.log` avec `rg "3d2871b5b1de824e"`
