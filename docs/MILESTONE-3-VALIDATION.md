# Milestone 3 validation

Validated locally for the November 23, 2026 milestone. Implementation used Codex and consulted the repository's Kiro specs and steering; no Kiro development activity is claimed.

## Implemented

The dashboard uses the existing Next.js 15 / React 19 / TypeScript application with Tailwind CSS 4. It includes a charcoal, purple and emerald command center, responsive navigation, Exhume / Resurrect / Verify tabs, keyboard tab navigation, split/unified patch inspection, attempt details, scenario selection/filtering, original golden-master JSON, field differences, held-out aggregate results, eight-event audit timeline, integrity evidence and a downloadable versioned report. Loading/error states, focus outlines and reduced-motion support are included.

All activity is labeled **Recorded Verification Results**. No dashboard control executes PHP, Docker, a repair, or an external AI request. `npm run export:run` is the local server-side report integration: it reads raw reports, checks fixture hashes, and writes the allowlisted schema-v1 snapshot. Runtime page rendering and the download API consume that snapshot only, and project allowed fields again.

## Actual validation results

| Check | Result |
| --- | --- |
| `npm run build` | Passed; optimized production build completed |
| `npm run typecheck` | Passed; no TypeScript errors |
| `npm test` | 8 report/privacy/integrity tests passed |
| Existing `python -m unittest discover -s tests -v` | 24 tests run: 23 passed, 1 skipped; no failures |
| Python skip | Symlink creation unavailable on Windows |
| `python verifier/main.py integrity` | Passed; all 8 protected file hashes match |
| `node scripts/browser-check.mjs` | 16 assertions passed; browser errors: none |
| Desktop / laptop / tablet / mobile | 1440 / 1024 / 768 / 390 px widths; no page overflow |
| In-page links | All resolve to existing sections |
| Evidence download | HTTP 200; 4/4 visible and 2/2 held-out match original JSON |
| Source preservation | PHP apps, repair engine, verifier and original tests byte-compared with pre-test isolated copy; unchanged |
| Privacy | Snapshot, rendered HTML and client bundles scanned; configured API keys and private scenario identifiers absent |
| Deployment file tracing | Sanitized snapshot included; private fixtures and root `.env` excluded |

The original Python suite runs in `.tmp/python-validation`, an isolated copy with no credentials. This avoids its repair workflow tests overwriting the original `repair-report.json` or modifying original source during tests. Its passing mock-provider integration test is not presented as a new live AI request.

Report tests verify original metric/patch fidelity, missing-report handling, private-detail exclusion, detection of modified fixtures, traversal-manifest rejection, malformed snapshot handling, snapshot field allowlisting and invalid-count rejection.

Browser checks cover recorded/mock disclosure, vertical JSON rendering, Exhume/Verify tab content, keyboard navigation, exact unified-diff hunk, scenario selection, empty failing filter, navigation anchors, export accuracy/privacy, four responsive layouts and absence of console/runtime errors. A missing favicon and incorrectly horizontal code lines found during QA were fixed before the final passing run.

## Screenshots

- [Desktop, 1440 px](screenshots/dashboard-desktop.png)
- [Laptop, 1024 px](screenshots/dashboard-laptop.png)
- [Tablet, 768 px](screenshots/dashboard-tablet.png)
- [Mobile, 390 px](screenshots/dashboard-mobile.png)
- [Machine-readable browser result](screenshots/browser-results.json)

## Observed report values and remaining evidence gaps

| Field | Supplied report value |
| --- | --- |
| Provider | mock |
| Model | gemini-3.8-flash |
| Audit final status | REPAIR_VERIFIED |
| Initial regressions | 0 |
| Attempts | 1 |
| Visible agreement | 4/4 |
| Held-out agreement | 2/2 |
| Unresolved visible failures | 0 |
| Fixture integrity | Passed |
| Legacy line coverage | Not measured |

These supplied files do not establish the live `gemini-3.6-flash` request described in the brief. The current modern source also differs from the retained patch. Both facts are surfaced in the UI. Original reports were preserved; no successful repair was synthesized to match the brief.

The original reports lack full modern responses, pre-repair output reports, a separate workspace-creation audit event, and most individual event timestamps. The UI explicitly shows unavailable evidence rather than inventing outputs or event completion. Standalone verification summaries lack run IDs and timestamps; their association with the repair cannot be independently proven. SHA-256 verifies local evidence against its manifest, not AI provenance or a signed historical record.

## Local use and deployment readiness

The tested production URL was **http://127.0.0.1:3000**. The QA server was stopped after validation; restart with:

```powershell
cd D:\Necromancer\dashboard
npm start -- --hostname 127.0.0.1
```

The dashboard is ready for deployment as a **recorded-results viewer**, using only the `dashboard/` directory and its checked schema-v1 export. Use Node 22.18+ (validated on Node 24), `npm ci`, `npm run build` and `npm start`. Do not run `export:run` in a deployment without the local source reports; the reviewed snapshot is already included. Refresh the snapshot and rebuild only after a deliberate new run.

No hosting deployment was requested or performed. Before presenting this as genuine live AI repair evidence, supply a traceable completed live-provider audit and regenerate the export. Docker execution and live repair remain local CLI operations. Universal PHP compatibility, measured line coverage, and production migration readiness are not claimed.
