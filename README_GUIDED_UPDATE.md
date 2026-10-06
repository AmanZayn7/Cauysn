# Guided investigations and bounded public Live

This update is based on the uploaded commit `28df1bd22b0c0142af2af9c0a90aa4371207ac80`. It preserves the SVG logo, chart export contrast, existing specialists, model, SDK, database views, and Neon role fixes. No dependencies or database migrations are required.

## What changes

- Four business-oriented entry points with supported date selectors and a visible question preview.
- A dataset introduction explaining the historical scope, BRL, and the meaning of sales.
- Short comparison/ranking summaries, readable category names, and explicit follow-up suggestions.
- Public Live without an access code, using private browser-session cookies. Recorded examples remain zero-API and fixed-date.
- Existing global 20/day and session 5/hour investigation limits, one active investigation, six-hour sessions, and session-scoped chart access remain. New sessions are throttled globally to 60 per 15-minute UTC bucket.

Anonymous sessions are not authenticated identities. Resetting a cookie can bypass a per-session allowance, but cannot reset the global daily allowance. Limits count admitted investigations (including failures), not rupees. This is intentionally a bounded portfolio demo, not unrestricted public chat. Each question is independent; follow-ups include dates and require confirmation.

Guided investigations reuse the existing approved tools; they do not create more agents or unrestricted SQL. Their Live results depend on the model and are not guaranteed by the template alone. The recorded category example contains only the three established leading categories, not a fabricated full ranking. Trend and delivery guides link to related recorded examples, clearly labeled, rather than pretending those examples match selected dates.

## Install on your Mac

Download the ZIP to Downloads. Keep your current `.env` and database untouched. Optionally copy the project folder before applying this update. The ZIP replaces only its named code/document files; it does not remove any other files or revert the project.

```bash
cd ~/Desktop/causyn
unzip -o ~/Downloads/causyn_guided_update.zip -d .
./.venv/bin/python deployment_checks.py
./.venv/bin/python free_hosting_checks.py
./.venv/bin/python guided_checks.py
```

Use a second terminal if the local website is running. Restart the website process to see Python changes. This package does not modify your private `.env`; for local public Live, run `CAUSYN_PUBLIC_LIVE=true ./.venv/bin/python web_app.py`.

## Commit and deploy

```bash
git add deployment_config.py web_access.py web_app.py guided_investigations.py guided_checks.py render.yaml ui/app.js ui/index.html ui/style.css .env.example .github/workflows/checks.yml README.md README_FREE_HOSTING.md README_GUIDED_UPDATE.md
git commit -m "Add guided investigations and bounded public live access"
git push
```

In Render → your service → Environment, add/set **CAUSYN_PUBLIC_LIVE** to **true**, then save/redeploy. Explicitly check this even if using the blueprint: a Git push may not apply blueprint environment changes to an existing service. Leave DATABASE_URL, CAUSYN_STATE_DATABASE_URL, GEMINI_API_KEY, CAUSYN_REQUIRE_DURABLE_STATE, and all passwords unchanged. Keep CAUSYN_LIVE_ENABLED=true. Values entered in Render have no surrounding quotes.

To return to owner-code Live, set CAUSYN_PUBLIC_LIVE=false and retain the existing private CAUSYN_ACCESS_CODE. To stop paid calls entirely, set CAUSYN_LIVE_ENABLED=false. Neither setting deletes data.

## Hosted smoke test (required)

1. Open the deployed website in a fresh browser session. Dataset help and all four guides should work without signing in.
2. Open the categories guide and view its recorded example: no model call, readable top-three labels, fixed Nov–Dec 2017 dates.
3. Run one Live guided category ranking for Nov–Dec 2017. No access-code dialog should appear. Check leading values: watches/gifts 164849.26, health/beauty 138963.15, bed/bath/table 138038.79 BRL. Inspect evidence and review statuses, then open its saved chart.
4. Try a second date range (for example Jan–Mar 2018). Verify question preview, result evidence dates, and chart dates agree. Do not compare this result to the fixed recorded example.
5. End the session: the old private chart must no longer open using that session. A different browser session must not be able to read another visitor's job or private chart URL.
6. Check the mobile landing page, date dialog, results and evidence tabs. Reload once after deployment if old static assets remain cached.

The package was checked offline with 44 deployment/access tests, existing specialist self-tests, JavaScript syntax checks, and simulated DOM interactions (date/group selection, question preview, examples, lazy session creation, and Live confirmation). A rendered browser check could not be completed because the browser download was unavailable. No actual Gemini/Neon investigation was run here. Your hosted smoke test verifies the integration and actual desktop/mobile layout.

## 60-second recruiter walkthrough to record

This is a recording outline, not an included video. Show: dataset help (10 seconds), a month-change recorded example and brief (15 seconds), a category guide with date selectors (10 seconds), one completed Live chart with source evidence and review (20 seconds), and the GitHub link (5 seconds). Record a completed result if the host is slow; disclose recorded examples and do not claim pre-recorded output is a fresh Live run.
