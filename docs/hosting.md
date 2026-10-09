# Render and Neon hosting

The hosted app uses Render for its Docker service and Neon PostgreSQL for both business reporting and durable web state. `causyn_reader` reads reporting views; `causyn_web` accesses only `app_state`.

## Preflight

From the repository root with the project environment active:

```bash
python deployment_checks.py
python free_hosting_checks.py
python check_database_size.py
```

The first two commands run offline. The size check reads the configured database. Check current provider allowances in their consoles and leave room for indexes and web state; restored database versions can have different storage overhead.

## Application service

Create a Render Blueprint from `AmanZayn7/Causyn` using `render.yaml`. The Docker service initially has Live disabled. Its current blueprint enables `CAUSYN_PUBLIC_LIVE=true` for anonymous visitor sessions once Live is enabled. Recorded demos work without a database connection or model key. Free hosting can introduce cold starts after inactivity.

The app derives its HTTPS origin from `RENDER_EXTERNAL_URL`. Set `CAUSYN_PUBLIC_ORIGIN` only for an explicitly configured origin such as a custom domain. Existing services may require environment changes to be applied separately from a Git push.

## Database and runtime connections

1. Create a managed PostgreSQL project with a version compatible with the export tools. Configure its direct administrator URL locally as `CAUSYN_OWNER_DATABASE_URL`.
2. Follow the [migration procedure](deployment.md#database-migration). Keep the local database and its private export until destination verification completes.
3. Run `python configure_hosted_reader.py` and `python configure_web_state.py`. These administrator operations run in transactions and are not called at application startup.
4. Configure `DATABASE_URL` for `causyn_reader` and `CAUSYN_STATE_DATABASE_URL` for `causyn_web`, preserving provider TLS parameters and URL-encoding passwords as needed. The administrator URL is not a hosting runtime setting.
5. Run `check_runtime_database.py`, `evaluate.py` and `evaluate_depth.py --database` against the hosted database and recheck storage.
6. Configure Render's private environment with the two runtime connections and `GEMINI_API_KEY`. Keep `CAUSYN_REQUIRE_DURABLE_STATE=true`. Enable `CAUSYN_LIVE_ENABLED` after successful preflight.

`CAUSYN_PUBLIC_LIVE=true` uses anonymous sessions. With it false, Live requires the private `CAUSYN_ACCESS_CODE`. Setting `CAUSYN_LIVE_ENABLED=false` disables new investigations in either mode. Configuration values entered in the hosting console have no surrounding quotes.

## Persistence and verification

Session hashes, login/admission counters and approved HTML charts persist in PostgreSQL. Charts are private to the issuing session and expire after 24 hours; sessions last six hours. Expired charts are cleaned up when a subsequent chart is saved.

Running jobs, progress and the last twenty job records remain in memory. Restarts interrupt running work and invalidate job polling links. Approved chart downloads can survive a restart while their issuing session remains valid. There is no automatic model retry.

Hosted checks should cover recorded demos, the selected Live access mode, one supported investigation, chart downloads, logout/session revocation and persistence after restart. Anonymous sessions are not verified identities; cookie replacement cannot reset the global daily allowance. Offline tests do not substitute for actual provider connection and permission checks.
