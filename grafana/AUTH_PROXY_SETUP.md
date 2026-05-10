# Grafana OSS – Auth Proxy + Dashboards certifiés (PFE)

Objectif : accès **lecture seule** pour tous les humains, visibilité selon rôle / département, et dashboards **pilotés par le code** (templates Git + provisioning via l’API Grafana par le backend).

## 1) Pré-requis

- Grafana OSS installé via APT (comme ton alias `grafana-start`)
- URL Grafana : `http://localhost:3000`
- Backend FastAPI qui délivre un JWT (`Authorization: Bearer ...`)

## 2) Config Grafana (`/etc/grafana/grafana.ini`)

Dans Grafana, activer l’auth proxy et forcer le rôle par défaut :

```ini
[users]
default_role = Viewer
allow_sign_up = false

[auth]
disable_login_form = true

[auth.proxy]
enabled = true
header_name = X-WEBAUTH-USER
header_property = username
auto_sign_up = true
headers = Name:X-WEBAUTH-NAME Role:X-WEBAUTH-ROLE
enable_login_token = false
```

Notes :
- `default_role = Viewer` garantit qu’un user créé automatiquement n’a pas de droits d’édition.
- En PFE, garde un accès admin “break-glass” local uniquement pour bootstrap.

## 3) Reverse-proxy (Nginx) : Grafana “derrière l’app”

Le principe : l’utilisateur appelle Grafana via Nginx, Nginx appelle ton backend en `auth_request` pour valider le JWT et récupérer les headers à injecter (user/role/department).

Exemple (simplifié) :

```nginx
server {
  listen 8080;

  location /grafana/ {
    proxy_pass http://127.0.0.1:3000/;

    # Auth : appel backend (doit retourner 200 si token OK)
    auth_request /_auth_grafana;
    auth_request_set $webauth_user $upstream_http_x_webauth_user;
    auth_request_set $webauth_name $upstream_http_x_webauth_name;
    auth_request_set $webauth_role $upstream_http_x_webauth_role;

    proxy_set_header X-WEBAUTH-USER $webauth_user;
    proxy_set_header X-WEBAUTH-NAME $webauth_name;
    proxy_set_header X-WEBAUTH-ROLE $webauth_role;
  }

  location = /_auth_grafana {
    internal;
    proxy_pass http://127.0.0.1:8000/grafana/auth;
    proxy_set_header Authorization $http_authorization;
  }
}
```

Tu accèdes ensuite à Grafana via : `http://localhost:8080/grafana/`

## 3bis) Alternative sans Nginx : reverse-proxy dans le backend FastAPI

Si tu ne veux pas de Nginx, le backend peut exposer un reverse-proxy `GET/POST/... /grafana/*` vers Grafana, après validation du JWT.

Implémentation :
- le `/login` met maintenant le JWT dans un cookie httpOnly `access_token` (en plus du JSON `access_token`)
- `/grafana/*` valide le JWT (header `Authorization: Bearer ...` **ou** cookie `access_token`)
- puis forwarde vers Grafana en injectant `X-WEBAUTH-USER` / `X-WEBAUTH-NAME` / `X-WEBAUTH-ROLE`

Accès navigateur :
- login via `http://localhost:8000/ui` (cookie posé par le backend)
- Grafana via `http://localhost:8000/grafana/`

Important (Grafana derrière un sous-chemin) : dans `/etc/grafana/grafana.ini`, ajoute aussi :

```ini
[server]
root_url = http://localhost:8000/grafana/
serve_from_sub_path = true
```

## 4) Backend : variables d’environnement (provisioning)

Le backend provisionne folders/permissions/dashboards via l’API Grafana.

Variables :
- `GRAFANA_URL=http://localhost:3000`
- `GRAFANA_PROVISIONING_ENABLED=true`
- `GRAFANA_DASHBOARD_TEMPLATES_DIR=grafana/dashboard_templates`

Pour la synchro users/teams + création user Grafana (admin endpoints), configurer :
- `GRAFANA_ADMIN_USER=admin`
- `GRAFANA_ADMIN_PASSWORD=admin`

## 5) Dashboards certifiés

Templates versionnés :
- `grafana/dashboard_templates/pfe-template-quality.json`
- `grafana/dashboard_templates/pfe-template-lineage.json`
- `grafana/dashboard_templates/pfe-template-pipeline.json`
- `grafana/dashboard_templates/pfe-template-governance.json`

À chaque création de projet (`POST /projects/`), le backend :
- crée un folder `PFE - <project_name>`
- applique les permissions (PUBLIC → Viewer, DEPARTMENT → team département)
- publie les 4 dashboards instanciés (requêtes filtrées par `project_id`)
