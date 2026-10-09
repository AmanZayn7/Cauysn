# Web interface

From the repository root in the configured project environment:

```bash
python web_app.py
```

The local interface runs at http://127.0.0.1:8765. Hosting configuration is documented in [deployment](deployment.md) and [Render/Neon setup](hosting.md).

## Demo and Live

Demo is the default. Three example buttons load recorded November/December 2017 figures or a delivery definition. They make no model request, database query or fresh verification pass. Unsupported demo questions are rejected rather than matched to unrelated examples.

Live uses the configured PostgreSQL reporting database and Gemini model. One investigation runs at a time, without automatic paid retries. Refreshing reconnects to an active job while the server remains running. Each question is independent; browser history is navigation state rather than conversation memory sent to the model.

## Results and exports

Summary cards and charts use successful tool evidence. Full reviewed answers, methodology, evidence and checks remain accessible. Definition questions display their complete answers directly. The workspace includes volume/value breakdown cards, SVG/CSV exports and links to approved HTML charts.

Static assets are self-contained, without external font or chart CDNs. Model credentials stay in backend configuration. Functional checks cover summaries, preserved answers, exports, source tabs and worker integration; desktop/mobile rendering requires browser checks.
