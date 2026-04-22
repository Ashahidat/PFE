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

## 7) Atlas UI en lecture seule (important)

Règle recommandée en prod:
- Atlas est une cible "write" uniquement via notre backend (avec validations et whitelists).
- Les utilisateurs ne doivent pas éditer via l'UI Atlas (sinon ils peuvent créer des classifications/termes hors contrôle applicatif).

Important:
- Si quelqu'un modifie directement dans l'UI Atlas, notre DB ne sera pas mise à jour automatiquement (pas de synchronisation Atlas -> DB dans ce projet actuellement).

## 8) `dataset_versions.atlas_guid = NULL` est-il "OK" ?

Oui: dans notre app, une version peut exister en mode "brouillon metadata":
- `atlas_guid = NULL` = version brouillon (descriptions / termes modifiés depuis l'UI de notre app)
- `atlas_guid != NULL` = version matérialisée dans Atlas (après `push-atlas`)

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

## 9) “PUBLIC + RESTRICTED” en même temps (remplacement classification sécurité)

Symptôme (dans Atlas) :
- le dataset a **deux** classifications sécurité en même temps (`PUBLIC` et `RESTRICTED`)
- et côté app, changer la classification depuis `my-uploads.html` finit par échouer avec :
  - `Echec synchronisation Atlas (security classification)`

Cause typique :
- notre backend “ajoutait” la nouvelle classification sans réussir à **supprimer l’ancienne** (endpoint Atlas de suppression incorrect).

Correctif :
- suppression via Atlas = endpoint **singulier** :
  - `DELETE /api/atlas/v2/entity/guid/{guid}/classification/{classificationName}`
- l’UI doit passer par le backend (route `POST /apply-classification`) qui fait un vrai “replace” (suppression `PUBLIC` + `RESTRICTED`, puis ajout de la nouvelle).

Vérif rapide :
- lister les classifications d’un dataset (remplacer `{GUID}`) :
  - `curl -u admin:admin "http://localhost:21000/api/atlas/v2/entity/guid/{GUID}?minExtInfo=true" | rg -n \"PUBLIC|RESTRICTED\"`

## 10) `GET /api/datasets/{id}/atlas-columns` en 404 (UI “My uploads”)

Symptôme :
- dans la console navigateur :
  - `GET http://localhost:8000/api/datasets/<id>/atlas-columns 404`
- conséquence : l’UI ne peut pas mapper `column_name -> guid` (et les boutons de classification colonne peuvent casser).

Correctif :
- endpoint backend ajouté dans :
  - `pip/data_quality/app/backend/routes/datasets_meta.py`
