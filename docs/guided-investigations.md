# Guided investigations and public Live

Four guided entry points provide supported date selectors and a question preview. Dataset help explains the historical window, BRL units and merchandise-value definition. Comparison and ranking summaries use readable category names and explicit follow-up suggestions.

Guides reuse the approved analytics tools. They do not add agents or permit arbitrary SQL. Each question is independent; follow-ups include dates and require confirmation.

## Recorded and Live behavior

Recorded examples use fixed dates and make no model requests. The category example contains three established leading categories rather than a full ranking. Trend and delivery guides identify related recordings explicitly; these recordings do not change to match selected dates.

Live runs a new model investigation using the selected period. A guide constrains question construction but does not guarantee the resulting answer is correct.

## Access configuration

`CAUSYN_PUBLIC_LIVE=true` enables anonymous visitor sessions without an access code. With it false, the private access code is required. `CAUSYN_LIVE_ENABLED=false` disables new model investigations in either access mode. Render environment changes may require an explicit save/redeployment even after a repository push.

Defaults permit twenty admitted investigations per UTC day globally, five per session/hour and one active investigation. Sessions last six hours; new anonymous sessions are limited to sixty per fifteen-minute UTC bucket. Cookie replacement can bypass a session allowance but not the shared daily allowance. Failed investigations count toward limits; these are not monetary caps.

## Verification

```bash
python deployment_checks.py
python free_hosting_checks.py
python guided_checks.py
```

Offline checks exercise guide selection, date handling, previews, recorded examples, session creation and Live confirmation. They do not establish current Gemini/Neon availability or actual browser rendering.

Hosted checks cover guide navigation, recorded-example labels, evidence dates, chart dates and isolation between sessions. For a November–December 2017 category ranking, the established leading values are watches/gifts 164,849.26, health/beauty 138,963.15 and bed/bath/table 138,038.79 BRL. Other periods must be checked against their own evidence rather than the fixed example.

Logout must revoke the session's chart access. Desktop and mobile checks should include the landing page, date controls, results, evidence tabs and downloads. Screen recordings should distinguish recorded examples from new Live investigations.
