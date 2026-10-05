# Render Free + Neon Free

This adapter moves authentication sessions, login throttling, Live admission counters and approved HTML charts to PostgreSQL. Business queries still use the read-only `causyn_reader` role. Control state uses a separate `causyn_web` role, with access only to `app_state`. No new Python dependency, model change or analytical feature is introduced.

## Install and measure first

```bash
cd ~/Desktop/causyn
unzip -o ~/Downloads/causyn_free_hosting_update.zip -d .
./.venv/bin/python deployment_checks.py
./.venv/bin/python free_hosting_checks.py
./.venv/bin/python check_database_size.py
```

The two suites run offline. The size check is a read-only local database query. Neon currently publishes 1 GB storage per free project and 100 CU-hours/month. Confirm the actual allowance in the Neon console and leave room for restored tables/indexes and web state. Local database size is an estimate: restored PostgreSQL versions can have different overheads. Measure the hosted size again after restore. Neither test suite above proves the actual hosted PostgreSQL connection or grants work; run the migration and hosted smoke tests before enabling Live.

## Commit the adapter

```bash
git add web_access.py web_app.py deployment_config.py configure_web_state.py check_database_size.py free_hosting_checks.py render.yaml README_FREE_HOSTING.md .github/workflows/checks.yml
git commit -m "Support Render and Neon free hosting"
git push
```

Wait for the GitHub offline checks and Docker build. This patch does not overwrite your private `.env`, data or captured runtime dependency versions.

## Get a public Demo online

Sign into Render with GitHub and create a **Blueprint** from your `AmanZayn7/Cauysn` repository, using `render.yaml`. Confirm the service plan is **Free**. The blueprint builds the existing Dockerfile, generates an owner access code and starts with **Live disabled**. The app discovers its HTTPS URL from Render's `RENDER_EXTERNAL_URL`, so there is no need to guess a domain before the initial deployment. Do not set `CAUSYN_PUBLIC_ORIGIN` unless using a custom domain; when set, it must match exactly.

The first build takes time and can vary. Once it is live, open the generated URL and test all three recorded examples. Demo uses no Gemini calls and requires no Neon connection. Render Free can sleep after fifteen minutes idle; expect a cold-start wait on a later visit. There is no paid disk in this blueprint.

## Set up Neon and enable protected Live

1. Create a Neon Free PostgreSQL project. Choose a PostgreSQL version compatible with the local `pg_dump` and a region near the chosen Render region. Keep the **direct owner** connection URL private, including its provider TLS parameters. Put it in `CAUSYN_OWNER_DATABASE_URL` in your existing private local `.env`. Do not paste URLs/passwords into chat.
2. Use the existing `database_transfer.py export` and `database_transfer.py restore` commands described in `README_DEPLOYMENT.md`. The restore guard requires a target without `raw`, `staging` or `analytics` schemas. Retain the local database and backup.
3. Run `./.venv/bin/python configure_hosted_reader.py` to set up the analytics reader, then `./.venv/bin/python configure_web_state.py` to create the separate web-state schema and role. Each prompts privately for a different password. They run transactions and are never called at website startup. If the provider blocks role creation, stop and resolve it; do not replace the restricted roles with the owner.
4. Build two private TLS URLs from the provider's direct endpoint: `DATABASE_URL` uses **causyn_reader**; `CAUSYN_STATE_DATABASE_URL` uses **causyn_web**. URL-encode special characters in passwords. Preserve the provider's TLS parameters. The owner URL is only for manual migration and setup and must not be added to Render.
5. Add the reader URL to your local private `.env` and run `check_runtime_database.py`, `evaluate.py`, and `evaluate_depth.py --database` against Neon. Confirm the validated metrics and charts still reconcile. Check database size again.
6. In Render's private environment settings, add `DATABASE_URL`, `CAUSYN_STATE_DATABASE_URL`, and `GEMINI_API_KEY`. Keep the generated `CAUSYN_ACCESS_CODE`; copy it privately from Render for owner sign-in. Set `CAUSYN_LIVE_ENABLED=true` only after the database checks pass. `CAUSYN_REQUIRE_DURABLE_STATE=true` prevents free-hosted Live from silently using ephemeral SQLite counters.
7. Redeploy. Test owner sign-in, one supported-month investigation, a chart download, logout, and denial of unauthenticated Live. Verify chart downloads/session state after a subsequent restart. Check errors if Neo schema grants or queries fail; do not call the hosted app complete until the actual smoke tests pass.

## What persists and what does not

The data, authenticated session hashes, login/admission counters and approved HTML chart files persist in Neon. Only an approved result's chart is uploaded to state storage. Chart retrieval is scoped to the issuing owner session and expires after 24 hours; session expiry remains six hours. Expired charts are physically cleaned up when a later chart is saved.

Running jobs, progress and the last twenty completed job records remain in server memory, as before. A restart interrupts running work and invalidates those job polling links; there is no automatic API retry. Browser session history can retain answers already displayed. Persistent approved chart downloads can survive a restart when the owner session remains valid. The interactive in-page SVG and CSV exports continue working.

Usage metadata logs are local and **not durable on Render Free**. Google billing is authoritative. Live admission counters remain durable in Neon; they are investigation-count limits, not a monetary cap. Gemini usage still costs money. The app stays at one instance/one process and permits one active Live investigation. Neon and Render free-plan quotas and sleep behavior still apply; test actual memory, latency and storage before relying on the link for a live interview.
