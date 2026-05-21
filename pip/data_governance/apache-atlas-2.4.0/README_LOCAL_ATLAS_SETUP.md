# Apache Atlas (local) - Setup + __AtlasUserProfile issue

This repo vendors an Apache Atlas 2.4.0 distribution under:
`pip/data_governance/apache-atlas-2.4.0/`

This note documents a recurring issue where Atlas returns HTTP 500 on write
operations (ex: `PUT /api/atlas/v2/entity`) and the fix applied in this repo,
so it can be reproduced on another machine and rolled back safely.

## Symptoms

- Backend/UI shows errors like:
  - `Atlas PUT error 500: There was an error processing your request. It has been logged (ID ...)`
- In Atlas logs (`logs/application.log`) you see:
  - `AtlasBaseException: Instance __AtlasUserProfile with unique attribute {name=admin} does not exist`
- After enabling setup-on-start, Atlas UI may show `HTTP 503 Service Unavailable` if setup cannot acquire its ZooKeeper lock.

## Root cause

1. Atlas expects an internal entity `__AtlasUserProfile` for the authenticated user
   (here `admin`, because clients use basic auth `admin/admin`).
2. The distribution was started without running Atlas setup steps, so the internal
   `__AtlasUserProfile` instance(s) were never created.
3. Attempting to run `./bin/atlas_start.py -setup` did not work because the script
   tried to launch a non-existent main class:
   `org.apache.atlas.web.setup.AtlasSetup` (ClassNotFoundException).
4. Setup steps need ZooKeeper to take a lock (`/apache_atlas/setup_lock`). If
   `atlas.server.ha.zookeeper.connect` is not set, Atlas falls back to
   `atlas.kafka.zookeeper.connect` (often `localhost:9026`), which may not be running,
   causing setup to fail and the webapp to become unavailable (503).

## Project-specific note (Data Quality backend)

This repository's data-quality backend syncs dataset/column descriptions to Atlas.
Make sure it targets the correct Atlas endpoint:

- Use `POST /api/atlas/v2/entity/bulk` with payload shape `{"entities":[...]}`
- Do not send `{"entities":[...]}` to `PUT /api/atlas/v2/entity` (single-entity endpoint),
  as it can result in server-side errors.

Atlas 2.4.0 does ship `org.apache.atlas.web.setup.SetupSteps`, but it is executed
by the server when setup-on-start is enabled (property below), not via the missing
`AtlasSetup` main class.

## What we changed in this repo

1. Enabled setup-on-start:
   - File: `conf/atlas-application.properties`
   - Change: set `atlas.server.run.setup.on.start=true`

2. Pointed setup lock to a running ZooKeeper:
   - File: `conf/atlas-application.properties`
   - Change: set `atlas.server.ha.zookeeper.connect=localhost:2181`

3. Fixed `-setup` behavior:
   - File: `bin/atlas_start.py`
   - Change: `-setup` no longer tries to run `org.apache.atlas.web.setup.AtlasSetup`.
     Instead it starts Atlas with `-Datlas.server.run.setup.on.start=true` and
     tells you to check `logs/application.log` for setup-step logs.

## How to run (local)

From `pip/data_governance/apache-atlas-2.4.0/bin`:

1. Stop Atlas if running:
   - `./atlas_stop.py`

2. Start Atlas normally:
   - `./atlas_start.py`
   - (or your shell alias that calls it)

Atlas uses local HBase and local Solr in this distro; the scripts will start them.

## Auto-create admin profile (recommended)

This repo includes a best-effort helper that runs automatically after `atlas_start.py`
finishes starting the server:

- Script: `bin/atlas_ensure_admin_profile.sh`
- It checks whether `__AtlasUserProfile(name=admin)` exists and creates it if missing.
- Disable it by setting: `ATLAS_ENSURE_ADMIN_PROFILE=false`

You can also run it manually:
- `./atlas_ensure_admin_profile.sh`

## How to validate it worked

1. Atlas should be reachable on the internal write port `21002`:
   - `curl -u admin:admin http://localhost:21002/api/atlas/admin/version`

2. Setup should have executed (first start after enabling it):
   - In `logs/application.log`, look for lines like:
     - `Running setup step: ...`

3. The previous error should disappear:
   - `logs/application.log` should stop showing:
     - `Instance __AtlasUserProfile with unique attribute {name=admin} does not exist`

4. If Atlas is up but you *still* see `__AtlasUserProfile(name=admin) does not exist`:
   - Create the missing internal profile entity once via the write-capable listener:
   - `curl -u admin:admin -H "Content-Type: application/json" -X POST http://localhost:21002/api/atlas/v2/entity -d '{"entities":[{"typeName":"__AtlasUserProfile","guid":"-1","attributes":{"name":"admin","fullName":"admin"}}]}'`
   - Then verify:
   - `curl -u admin:admin "http://localhost:21002/api/atlas/v2/entity/uniqueAttribute/type/__AtlasUserProfile?attr:name=admin"`

4. Optional: verify the typedef lookup path (Atlas v2):
   - `curl -u admin:admin "http://localhost:21001/api/atlas/v2/types/typedefs?name=__AtlasUserProfile&type=entity"`
   - Note: `GET /api/atlas/v2/types/typedef/__AtlasUserProfile` can return 404 depending on Atlas version/routes.

6. Then re-run the action that used to fail (example from this project):
   - Backend calls Atlas via the internal write endpoint `http://localhost:21002/api/atlas/v2/entity`
   - If Atlas is healthy, the dataset/column metadata sync should no longer return 500.

## Rollback (go back easily)

If you need to revert the behavior:

1. In `conf/atlas-application.properties`, remove or comment out:
   - `atlas.server.run.setup.on.start=true`

2. In `bin/atlas_start.py`, revert the custom `-setup` behavior to the upstream
   version (the block that attempted to run `org.apache.atlas.web.setup.AtlasSetup`).

Then restart Atlas with `./atlas_stop.py` then `./atlas_start.py`.

## Deployment notes

- In a real deployment (docker/k8s), the same concept applies:
  enable `atlas.server.run.setup.on.start=true` via config, then restart once.
- If you do not want setup to run on every restart, set it back to false after
  the first successful boot where setup steps completed (verify via logs).
