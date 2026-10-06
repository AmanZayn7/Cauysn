# Findings, charts and honest status labels

Apply this after the guided-investigation and period-total fixes. No secrets, environment settings, model, dependencies or database objects are changed. No additional model request is added.

## All six improvements

1. Monthly trend summaries lead with the selected range's merchandise total and unique delivered-order count, followed by the highest-value month from that range. Ties are disclosed. This does not assume a steady decline or hard-code November as the peak.
2. Category summaries show up to three negative and three positive contributions. A diverging chart replaces the two-month bars when matching category-change evidence is present. It labels both signs, includes exact plotted values and exports, and explicitly discloses omitted categories. In the reviewed answer, tool-backed category contributions are inserted before checks and AI review, so an omission is not simply hidden by the UI. Existing wrong claims/prose remain subject to rejection.
3. Trend, comparison and waterfall axes use round 1/2/2.5/5/10 steps and consistent lower-case k / capital M suffixes. Exact monetary labels and original exported values remain unchanged.
4. Category display names consistently use sentence case in summaries, plots and saved-report tables. Raw identifiers remain unchanged in evidence, specifications and CSV exports.
5. Newly generated saved HTML reports use the dark purple theme and a safe Back to Causyn link. Existing stored HTML reports do not change retrospectively; generate a new report after deployment to check this fix.
6. Result badges distinguish Recorded example, Analysis reviewed, Documentation searched, No data queried, No numerical result, and Inspect verification. Documentation searched does not claim a policy was found or that business data was queried. The detailed verification tab still shows the actual checks and AI verdict.

The diverging chart is a deterministic browser view of returned category-change evidence, not a new model-planned chart operation or a new agent. Its SVG and plotted-data CSV exports are available in the dashboard. It does not create a separate persisted HTML report for that category-contribution view. The existing visualization specialist's saved reports keep their original approved source mappings.

## Install and test on Mac

Save `causyn_presentation_polish.zip` in Downloads and use a free project terminal:

```bash
cd ~/Desktop/causyn
unzip -o ~/Downloads/causyn_presentation_polish.zip -d .
./.venv/bin/python presentation_checks.py
./.venv/bin/python answer_completeness_checks.py
./.venv/bin/python deployment_checks.py
```

Optional if Node is already installed: `node presentation_checks.js`. Do not install a new project dependency just to run this optional check. CI runs the JavaScript checks.

Offline Python/JavaScript regressions and simulated DOM tests passed during development. Chart SVGs were rendered and visually inspected using fixtures. No actual Gemini/Neon request was made here; the full rendered website and new saved report still need a hosted check.

## Commit and deploy

```bash
git add ui/app.js ui/presentation.js ui/index.html ui/style.css web_app.py depth_visuals.py visualization_specialist.py chart_presentation.py answer_completeness.py answer_completeness_checks.py presentation_checks.py presentation_checks.js .github/workflows/checks.yml README_PRESENTATION_POLISH.md
git commit -m "Polish findings, chart presentation and result status labels"
git push
```

Wait for the new Render deployment to report Live. Keep CAUSYN_THINKING_LEVEL=low. No new environment variable is required. Refresh the page to load the new presentation script.

## Hosted check

- Open an existing monthly trend in this browser's history, or run a supported trend once: the short summary should lead with its range totals and correct peak month. Check exact totals against evidence.
- Ask for a month comparison with both negative and positive category contributions. Both directions must be visible, with the diverging chart and omitted-category warning. Its selected bars are not claimed to sum to the overall change.
- Generate a new saved chart and open it: dark styling, readable axis labels, exact values, and Back to Causyn should work. Old saved charts retain their original styling.
- Ask a question without necessary dates and an unsupported policy question: the badge must distinguish no data queried from documentation searched. The full verification tab remains inspectable.
- Check the same screens on a phone. Keyboard focus, text escaping, SVG/CSV downloads, and session-scoped saved-chart access remain in place.

When testing is finished, restore the temporary admission allowances to the intended public defaults (five per session/hour and twenty globally/day) if you previously raised them. These limits count admitted investigations, including failures; they are not a monetary cap.
