# Deployment and database migration

Causyn runs on Starlette/Uvicorn with a Docker image and Python 3.11. The current hosted configuration uses Render and Neon; see [hosted setup](hosting.md). The procedures below also describe local preparation and database migration.

## Local setup

Run from the repository root in the project environment:

```bash
python -m pip install -r requirements.web.txt
python capture_dependencies.py
python deployment_checks.py
python check_runtime_database.py
python evaluate.py
python web_app.py
```

The local interface is available at http://127.0.0.1:8765. Dependency capture records seven installed direct runtime versions. `requirements.runtime.txt` is a direct-version manifest, not a complete transitive hash lock. pandas inspection scripts are development tools rather than serving dependencies. `.env.example` documents configuration; private values belong in an untracked `.env` or the host's environment settings.

## Docker preview

```bash
docker compose up --build -d
docker compose ps
```

Compose serves recorded demos with Live disabled, without a database or API key. It binds port 8765 to loopback and uses a non-root process, read-only image and writable runtime volume. `docker compose down` stops the preview; adding `-v` also removes its volume.

## Hosting configuration

Use one application instance and one Uvicorn process. Job execution remains in memory; multiple replicas require a shared job store and admission coordination. HTTPS terminates at the host's proxy.

| Setting | Purpose |
| --- | --- |
| `CAUSYN_ENV=production` | Enables production configuration checks |
| `CAUSYN_RUNTIME_DIR=/runtime` | Writable runtime directory |
| `CAUSYN_LIVE_ENABLED` | Enables or disables new model investigations |
| `CAUSYN_PUBLIC_LIVE` | Selects anonymous visitor sessions or access-code sessions |
| `CAUSYN_ACCESS_CODE` | Private fallback access code, at least 24 characters |
| `DATABASE_URL` | Restricted analytics reader connection |
| `CAUSYN_STATE_DATABASE_URL` | Separate PostgreSQL web-state connection |
| `CAUSYN_PUBLIC_ORIGIN` | Exact HTTPS origin when explicitly configured |
| `PORT` | Hosting port; defaults to 8765 |

Render can derive the origin from `RENDER_EXTERNAL_URL`. When using SQLite state, `/runtime` requires a persistent volume. Free hosting uses PostgreSQL state and `CAUSYN_REQUIRE_DURABLE_STATE=true`; see [hosting](hosting.md).

Production database URLs must explicitly enable TLS. Provider-supported certificate/hostname verification offers stronger assurance than encryption alone. Credentials, owner connections, access codes and database dumps are not included in the image or served to browsers.

## Database migration

1. Configure `CAUSYN_OWNER_DATABASE_URL` locally with the destination administrator connection and TLS parameters. It is for manual migration, not website runtime.
2. Run `python database_transfer.py export`. It exports raw, staging and analytics schemas, excludes ownership/access assignments and refuses to overwrite an existing dump.
3. Run `python database_transfer.py restore`. It requires a destination without project schemas and restores in a transaction. PostgreSQL client/server versions must be compatible.
4. Run `python configure_hosted_reader.py` and, for hosted PostgreSQL state, `python configure_web_state.py`. Each requests its role password privately. The analytics and state roles remain separate from the administrator.
5. Configure the restricted connections and run `python check_runtime_database.py`, `python evaluate.py` and `python evaluate_depth.py --database` against the destination.
6. Start with Live disabled, check recorded demos, then enable Live and check an investigation, chart access and session expiry.

Business queries use parameterized operations, read-only transactions, a five-second connection timeout and ten-second statement limits. Preflight checks privileges, reporting views and the established baseline without modifying data.

## Sessions and operational limits

Demo responses are recorded and make zero model requests. Live jobs and charts are private to their issuing session. Sessions expire after six hours and are revoked at logout. Public Live creates anonymous sessions; access-code mode requires sign-in. See [guided investigations](guided-investigations.md).

Defaults allow twenty admitted investigations per UTC day globally and five per UTC hour per session, including failed jobs. These limits are not a monetary cap: a timed-out request may still incur provider charges. One Live investigation runs at a time; its worker has an eight-minute outer timeout. At most twenty job records remain in memory for up to 24 hours. A restart interrupts work and invalidates job polling links.

`/healthz` checks service liveness without database or model calls. Offline tests and Docker CI do not establish hosted database availability or model-answer correctness. Host deployment checks should cover access mode, a supported investigation, chart download, expiry and behavior after restart.
