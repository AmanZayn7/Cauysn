# CAUSYN web interface

Copy `web_app.py` and the `ui` folder into your existing CAUSYN project, alongside `agent.py`.

```bash
cd ~/Desktop/causyn
./.venv/bin/python web_app.py
```

Open http://127.0.0.1:8765 in your browser. Leave the terminal running. Ctrl+C stops the web server. No new Python packages are required beyond the existing agent dependencies.

## Demo and live

- **Demo** is the default. The three example buttons load recorded November/December 2017 figures or a late-delivery definition. No API request, database query, or fresh verification runs in demo mode. Arbitrary demo questions are rejected rather than shown unrelated results.
- **Live** runs your existing agent, local PostgreSQL and Gemini configuration. Select Live, then ask a complete question with supported months when needed. API requests remain subject to the agent's shared bounds and usage log.
- This version supports one investigation at a time. It does not automatically retry paid runs. Refreshing reconnects to the active investigation while the server remains running.
- Each question is independent. Session history is a browser navigation aid, not conversation memory sent to the model.
- Insights map the successful tool results to summary cards and chart coordinates. Evidence and check details remain available in a separate tab. The generated chart's own HTML can be opened from the analysis canvas.

## Scope

This is the **local development interface**, bound to your computer's loopback address. Public deployment, hosted database configuration, authentication and service-level spending/rate controls belong to the deployment stage. It does not publish your project or create a public link.

Your API key stays in the backend's existing `.env`; it is not served to the browser. Static assets are self-contained, and no third-party font or chart CDN is required.

## Workspace polish

The landing page keeps the original purple identity. The workspace uses stronger contrast, aligned report typography, three cards for a volume/value breakdown, and SVG/CSV downloads. Numerical comparisons start with a deterministic summary derived from successful tool evidence. The complete model answer remains available under **Full reviewed answer and methodology**; the presentation layer does not replace or change the original reviewed answer. Definition questions continue to show their complete answer directly. Backend agents, API limits, and verification rules are unchanged.

Functional checks cover summaries, preservation of the reviewed answer, exports, source tabs, and worker integration. Visual checks at desktop and mobile sizes still need a real browser on the Mac.
