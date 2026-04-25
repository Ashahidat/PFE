# Alignement visibilité Dataset ↔ Atlas (PUBLIC / DEPARTMENT)

## Problème initial

La visibilité d'un dataset était déterminée à **deux endroits** avec des règles différentes :

- **UI / PostgreSQL** : `Dataset.classification` était forcée à `project.visibility` lors de l'upload.
- **Atlas** : la classification de sécurité était appliquée au moment du push (`/push-atlas/{dataset_id}`) via le paramètre `is_public` et/ou le département de l'utilisateur qui pousse.

Conséquence : un dataset pouvait être **PUBLIC en UI** (visible à tous) mais **RESTRICTED/DEPARTMENT dans Atlas**, ou l'inverse.

## Décision (règle produit)

La **source de vérité unique** devient :

- `Dataset.classification` (PUBLIC ou DEPARTMENT), choisie au niveau dataset (override possible par rapport au projet).

Atlas doit refléter cette valeur lors du push :

- `PUBLIC` → classification Atlas `PUBLIC` avec `visibility_scope=ENTERPRISE`
- `DEPARTMENT` → classification Atlas `RESTRICTED` avec `visibility_scope=DEPARTMENT` et `department=<dept du owner>`

## Modifications effectuées

### 1) Upload backend

Fichier : `pip/data_quality/app/backend/routes/upload.py`

- Ajout du champ de formulaire `dataset_visibility` (optionnel).
- Si absent : valeur par défaut = `project.visibility`
- Validation stricte : `PUBLIC` ou `DEPARTMENT`
- `Dataset.classification` est désormais enregistrée avec cette valeur.
- La réponse `/upload` inclut `dataset_visibility`.

### 2) Push Atlas backend

Fichier : `pip/data_quality/app/backend/routes/push_atlas.py`

- La classification de sécurité appliquée dans Atlas est déterminée à partir de `dataset.classification`.
- Le département utilisé pour `RESTRICTED` est celui du **owner** (priorité `dataset.owner_employee_id`, fallback `dataset.project.owner_employee_id`), **pas** celui de l'utilisateur qui push.
- Le paramètre `is_public` est conservé pour compatibilité API, mais n'est plus la source de vérité (il sert uniquement de fallback si `dataset.classification` est vide).

### 3) UI Upload

Fichiers :

- `pip/data_quality/app/frontend/upload.html`
- `pip/data_quality/app/frontend/js/upload.js`

- Ajout d'un sélecteur "Visibilité du dataset"
- Envoi du champ `dataset_visibility` dans le `FormData` vers `/upload`

## Test plan (manuel)

1. Créer un projet **PUBLIC**
2. Upload d'un CSV en choisissant :
   - Visibilité dataset = **DEPARTMENT**
3. Vérifier côté UI :
   - l'accès au dataset est restreint aux utilisateurs du même département (routes preview/get-columns/etc.)
4. Lancer le push Atlas sur ce dataset
5. Vérifier dans Atlas :
   - classification `RESTRICTED` présente
   - attributs : `visibility_scope=DEPARTMENT`, `department=<dept du owner>`

Puis refaire avec dataset_visibility = **PUBLIC** et vérifier que Atlas reçoit `PUBLIC` + `visibility_scope=ENTERPRISE`.

## Notes / Migration des données existantes

Avant ce changement, `Dataset.classification` était copié depuis `project.visibility` à l'upload.
Si tu as déjà des datasets dans des projets PUBLIC qui devraient être DEPARTMENT, il faudra les corriger en base (script SQL) puis re-push (ou re-synchroniser) pour que la classification Atlas reflète la nouvelle source de vérité.

