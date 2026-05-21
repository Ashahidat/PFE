# Atlas UI read-only (local, single machine)

Goal:
- Humans can browse Atlas UI, but cannot create/update/delete anything from Atlas UI.
- The application remains the only write-capable path into Atlas.

This repo implements that by running:
1) Atlas internally on `127.0.0.1:21002` (write-capable, reachable only locally)
2) Nginx proxy on `:21001` (human entrypoint, read-only enforcement at the API level)

The browser UI also disables write requests when it is opened on `21001`, so
users should only ever browse Atlas through the public proxy.

## 1) Start Atlas on the internal port

Option A (helper script):

```bash
./pip/data_governance/run_atlas_internal.sh
```

Option B (manual), from `pip/data_governance/apache-atlas-2.4.0/bin`:

```bash
./atlas_stop.py || true
./atlas_start.py -port 21002
```

Validate:

```bash
curl -u admin:admin http://127.0.0.1:21002/api/atlas/admin/version
```

## 2) Start Nginx with the read-only proxy config

The Nginx config lives at:
- `pip/data_governance/nginx/atlas_readonly.conf`

Run Nginx in a local directory (so pid/log files stay under this repo):

```bash
mkdir -p /tmp/nginx-atlas-ro
nginx -p /tmp/nginx-atlas-ro -c /home/ashahi/PFE/pip/data_governance/nginx/atlas_readonly.conf
```

Or use the helper script:

```bash
./pip/data_governance/run_nginx_atlas_readonly.sh
```

Stop the proxy:

```bash
./pip/data_governance/stop_nginx_atlas_readonly.sh
```

## Optional: load shell aliases

This repo ships a small alias file:
- `pip/data_governance/aliases.sh`

Load it in your shell:

```bash
source /home/ashahi/PFE/pip/data_governance/aliases.sh
```

Handy commands:
- `atlas-ro-start` / `atlas-ro-stop`
- `atlas-ui-start` / `atlas-ui-stop`
- `atlas-internal-start` / `atlas-internal-stop`

Atlas UI for humans:
- http://<machine>:21001

Do not use `21002` in a browser. That port is for the local Atlas backend and
remains write-capable for the application.

## 3) Point the app to the internal Atlas port

Backend code now uses `ATLAS_REST_ADDRESS` (default `http://127.0.0.1:21002`).

If needed, export:

```bash
export ATLAS_REST_ADDRESS=http://127.0.0.1:21002
export ATLAS_USERNAME=admin
export ATLAS_PASSWORD=admin
```

## Notes

- The proxy blocks all write methods to `/api/atlas/*` except it still allows search endpoints
  (`POST` to `/api/atlas/v2/search/*`) because the UI might use POST for read-only searches.
- If you later need to allow other read-only POST endpoints, add them explicitly in Nginx
  (keep everything else read-only).
