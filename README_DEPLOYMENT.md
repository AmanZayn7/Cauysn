# CAUSYN deployment preparation

The analytics, six roles, approved queries, verification gates and Gemini model are unchanged. Decimal output now uses ordinary notation, so PostgreSQL zero rates such as `0E-20` remain valid after JSON saving. This update replaces the local development HTTP server with Starlette/Uvicorn and adds portable reader connection settings, owner-only hosted Live access, private job/chart access, persistent admission limits, a Docker image and offline CI checks.

## First install on the Mac

Save this ZIP to Downloads, stop the current website with Control+C in its server tab, and run:

```bash
unzip -o ~/Downloads/causyn_deployment_prep.zip -d ~/Desktop/causyn
cd ~/Desktop/causyn
./.venv/bin/python -m pip install -r requirements.web.txt
./.venv/bin/python capture_dependencies.py
./.venv/bin/python deployment_checks.py
./.venv/bin/python check_runtime_database.py
./.venv/bin/python evaluate.py
```

The dependency capture records seven installed direct runtime versions, including your already-tested Google SDK. It does not upgrade the SDK, change the model, read secrets or make API calls. Transitive dependencies are resolved by pip; `requirements.runtime.txt` is a direct-version manifest, not a complete hash lock. Use Python 3.11 for the app and container. Existing pandas inspection scripts are local development tools and are not runtime dependencies.

The existing local database defaults still work. Your private `.env`, raw CSV files, database and saved evaluation reports are not replaced by this ZIP. Preserve your existing `.env`; `.env.example` is only a reference. Without a configured access code, the local site keeps its existing Live behavior. Leave the local server on the loopback interface.

Start the website again:

```bash
./.venv/bin/python web_app.py
```

Open http://127.0.0.1:8765. Use another Terminal tab for other commands. Demo and Live retain the same interface. Hosted Live adds a small owner sign-in dialog.

## Docker preview

Install [Docker Desktop for your Mac](https://docs.docker.com/desktop/setup/install/mac-install/) (Apple silicon for M-series chips, Intel for an Intel Mac) and start it. After capturing the runtime dependency versions, stop the local website to free port 8765:

```bash
cd ~/Desktop/causyn
docker compose up --build -d
docker compose ps
```

Open http://127.0.0.1:8765. This Compose preview deliberately runs the public recorded demos with Live disabled. It needs no database or API key. It binds the Mac port to loopback, uses a non-root user, a read-only image and a writable runtime volume. Stop it with `docker compose down`. Do not use `down -v` if you want to keep runtime state.

Docker does not host the website by itself. It packages the tested app consistently; a hosting service will run that image. The provider and public URL still need to be selected. No cloud infrastructure was created by this update.

## Hosting configuration

Use **one app instance, one Uvicorn process and a persistent writable volume** mounted at `/runtime`. The SQLite access store and daily admission counters must survive restarts. Investigations themselves are in memory: a restart stops active workers and removes server-side job access. Browser history can retain a previously displayed answer, but old server links may expire. Do not scale this implementation to multiple replicas or workers; that requires a shared job store and global admission service.

Serve HTTPS through the hosting provider's proxy. Configure these as private host environment values, never in source code or the browser:

- `CAUSYN_ENV=production`
- `CAUSYN_PUBLIC_ORIGIN=https://your-actual-domain` (no trailing path)
- `CAUSYN_ACCESS_CODE`: a random owner access code of at least 24 characters
- `CAUSYN_RUNTIME_DIR=/runtime`
- `CAUSYN_LIVE_ENABLED=false` for the first public demo check
- `PORT`: the host's assigned port (default 8765)

To enable owner Live after migration/preflight, also configure `DATABASE_URL` with the restricted reader credentials, `GEMINI_API_KEY`, and set `CAUSYN_LIVE_ENABLED=true`. Use the database provider's TLS URL, preferring verified certificate/hostname validation (`sslmode=verify-full` and a provider CA certificate when required). Production rejects URLs that do not explicitly enable TLS. `require` encrypts without the same certificate/hostname assurance; use the provider's verified TLS instructions. The image does not contain an API key, owner URL, access code, database dump or `.env`.

Generate random secrets locally using a password manager or `python -c 'import secrets; print(secrets.token_urlsafe(32))'`. Keep the owner access code separate from the database reader password. Do not paste either into chat, commit them or put them into URLs. Credentials stay on the server; the browser receives a random HttpOnly session cookie with Secure and SameSite=Strict in production.

## Database migration after choosing a provider

1. Create an empty managed PostgreSQL database and obtain its private **owner** URL with TLS. Put it in `CAUSYN_OWNER_DATABASE_URL` in your private local `.env`; this variable is for manual migration only.
2. With PostgreSQL client tools on your Mac PATH, run `./.venv/bin/python database_transfer.py export`. It backs up the raw, staging and analytics schemas to `causyn.dump`, refuses to overwrite an existing file, and excludes owner and access-control assignments. The backup is private and Git-ignored.
3. Run `./.venv/bin/python database_transfer.py restore`. It refuses targets that already contain project schemas and restores in a single transaction. No `--clean`, schema deletion or table truncation occurs. Ensure the `pg_dump` client is compatible with the source server and the hosted server can restore that version.
4. Run `./.venv/bin/python configure_hosted_reader.py`. This creates/configures `causyn_reader` and prompts privately for its password. The selected provider must allow the owner's role-management operations. If it does not, configure the equivalent reader through its dashboard; do not substitute the owner credentials in the app.
5. Add the resulting reader URL as `DATABASE_URL`, using correct URL encoding for special password characters and the provider's verified TLS settings. Run `./.venv/bin/python check_runtime_database.py`, then `./.venv/bin/python evaluate.py` and `./.venv/bin/python evaluate_depth.py --database` against that target.
6. Remove the owner URL from the app-host environment; it is never required by the website. Start the hosted app with Live disabled, verify the public demo, then enable owner Live and run a small smoke test.

Runtime database connections have a five-second connection timeout. Queries retain the existing read-only transactions, parameterized SQL and ten-second statement limits. The preflight checks reader privileges, four reporting views and the known 96,211-order / BRL 13,181,027.13 baseline; it does not modify data.

## Live safeguards and limits

Public Demo responses are recorded examples, labeled as such, and make zero Gemini calls. Only an authenticated owner session can start hosted Live work, poll its own jobs or download its own charts. Sessions expire after six hours; logout revokes the session. A global login admission limit permits ten attempts per fifteen-minute bucket; it does not trust forwarded IP headers.

Default admissions are 20 Live investigations per UTC day globally and five per UTC clock hour per session. Change `CAUSYN_DAILY_LIVE_LIMIT` and `CAUSYN_HOURLY_SESSION_LIMIT` in the host environment. Admissions are counted when a job starts, including jobs that later fail. These are investigation-count limits, **not a hard monetary cap**. The agent retains its request/tool limits and soft cost checks. Timed-out work can still incur API charges; killing a worker cannot cancel a request already received by Gemini.

Only one Live job runs at once; Demo stays available while it runs. Workers have an eight-minute outer timeout. At most twenty job records are retained, for up to 24 hours. On deployments with a separate runtime directory, charts older than 24 hours are removed during subsequent requests. Original Mac charts outside that deployment directory are preserved. Usage logs contain metadata rather than questions or answers; manage their retention through the host's volume/log policy. Never publicly serve `/runtime`.

`/healthz` is a service liveness check and makes no external calls. It does not assert database availability. Static assets are allowlisted; credentials and Python files have no download routes. Host and Origin checks, CSP, no-store responses and request-size limits protect the browser endpoints. Production uses HTTPS cookies; make sure the public origin exactly matches the browser's URL. No forwarded headers are trusted by Uvicorn.

## Validation and CI

`deployment_checks.py` makes no database or Gemini calls. It exercises authentication, logout, job/chart isolation, quota persistence, denied origins/hosts, request limits, zero-call Demo and connection configuration. Existing specialist self-tests remain available. The GitHub Actions workflow runs those offline checks and a Docker build after `requirements.runtime.txt` is committed. It does not provision a host or spend Gemini credits.

This package was checked with offline deployment tests, specialist self-tests and replay of saved evaluation reports. A real Docker build, Mac database check and hosted end-to-end smoke test must still run in their actual environments. Docker was not available in the preparation environment; no live Gemini request or database migration was made here.
