# Milestone 4 — final evidence and release report

Validated November 23, 2026.

- GitHub: https://github.com/GaneshDonawad/Necro_mancer
- Public dashboard: https://necromancer-proof.vercel.app
- Production deployment: `dpl_8CM8CvUCZNxoVEqCFJXmTxGsP24B`
- Dashboard mode: **Recorded Verification Results**. No live repair is performed by the website.

## Genuine repair evidence

The original live audit could not be recovered from available reports or session history. The superseded mock report matched the deterministic mock workflow test. That test used the real repository as its root and overwrote `repair-report.json`; its model label came from the default configuration even though its provider was mock.

The previous reports and modern source were archived privately before changes. A new genuine Google Gemini request was made with the existing local API configuration, with fallback disabled.

| Measurement | Actual result |
| --- | --- |
| Provider | Google Gemini |
| Actual model | gemini-3.6-flash |
| Run UUID | e176fe6d-e2d8-4255-933c-873fb790caed |
| Initial detected regressions | 1 |
| Repair attempts | 1 |
| Patch security validation | Passed |
| Candidate visible tests | 4/4 passed |
| Candidate held-out tests | 2/2 passed |
| Independent post-application visible replay | 4/4 passed |
| Independent post-application held-out replay | 2/2 passed |
| Final status | REPAIR_VERIFIED |
| Golden-master integrity | Passed; original bytes unchanged |
| Legacy line coverage | Not measured |

The known loose-comparison baseline was restored before the request and actually replayed on PHP 8.3. It failed `guest-string` with four field differences while the other three visible scenarios passed. Gemini generated the correction `$is_walk_in = ((int)$customer == 0);`. The engine validated it, applied it only in a disposable workspace, tested it, and then applied the verified correction to the modern source. No success record or patch was manually authored to replace Gemini's output.

The API response ID and SHA-256 fingerprint are retained in the private audit. The response fingerprint is `9498060c69ea7925047ddc847bfba47b3b27f5cb6b77097d454dd5bf8c7a7f2d`. This is an audit aid, not a digital signature or independent provider attestation.

## Corrections and security

- Workflow tests now write to temporary roots and cannot overwrite the live audit or modern source. Their replay is explicitly mocked for unit testing; the real Docker integration was executed separately above.
- Audits are archived automatically by UUID under ignored `.local-runs/`.
- Reports record the actual response provider/model, including fallback attribution. Gemini uses its returned model version where available.
- The dashboard accepts the genuine diff's valid unprefixed file headers as well as `a/` and `b/` headers, retaining the exact patch text.
- Staged files were scanned for configured credentials and credential-shaped literals before the first push. No secrets were found.
- `.env`, raw audits, private histories, held-out fixtures, original scenario definitions, the private manifest, temporary workspaces, dependencies and build artifacts are excluded from Git. Original evidence remains unchanged locally.
- A public visible-only scenario template explains how to create a new independent local experiment. It does not expose the historical held-out inputs or expected outputs.
- Only 20 allowlisted dashboard source files and the sanitized export were sent to Vercel. No PHP runtime, Docker environment, root fixture tree, `.env` or LLM key was deployed.
- The only application API is the read-only report download. It accepts no shell commands or filesystem paths. No Docker or repair execution endpoint exists.
- The API re-projects allowed snapshot fields. Public JSON privacy checks reject private scenario names, credentials and absolute local paths.

## Final validation

| Check | Result |
| --- | --- |
| Python unit and repair security suite | 26 run: 25 passed, 1 skipped (Windows symlink privilege) |
| Report/privacy/integrity tests | 8 passed |
| Golden-master integrity | Passed; all 8 original protected files unchanged |
| Next.js production build | Passed locally and on Vercel |
| TypeScript | Passed |
| Public browser suite | 16 passed; no browser runtime or console errors |
| Responsive widths | 1440, 1024, 768 and 390 px; no page overflow |
| Stage tabs and keyboard navigation | Passed publicly |
| Unified patch comparison | Exact match with the recorded genuine patch |
| Scenario selection and failing filter | Passed publicly |
| Public navigation anchors | All resolve |
| Public `/`, `/api/report`, `/icon.svg` | HTTP 200 without authentication |
| Public report metrics/privacy | Genuine run ID/provider/model match; held-out details excluded |
| Audit after final unit suite | Genuine run preserved; no mock overwrite |
| GitHub preparation | MIT license, `.kiro/`, source, setup docs and sanitized export committed and pushed |

Public deployment browser evidence:

- [Desktop](screenshots/milestone4-dashboard-desktop.png)
- [Laptop](screenshots/milestone4-dashboard-laptop.png)
- [Tablet](screenshots/milestone4-dashboard-tablet.png)
- [Mobile](screenshots/milestone4-dashboard-mobile.png)
- [Machine-readable browser results](screenshots/milestone4-browser-results.json)

## Remaining issues and Devpost readiness

The application and recorded demonstration are publicly accessible and technically ready for a three-minute demo. The release was uploaded through the authenticated Vercel integration; automatic deployment on Git pushes has not been configured. No additional authentication was needed for this release.

Actual Kiro IDE/agent usage evidence was not recovered. The repository contains Kiro specs and steering files, which Codex consulted, but these are not proof that Kiro performed development. Obtain real Kiro usage evidence if required by the hackathon; do not invent it. The video and final Devpost submission remain to be completed by the entrant.

Code coverage is not measured. Full modern JSON responses, a complete baseline output artifact, and most event-level timestamps are absent from the backend reports; the UI discloses these limits. Standalone verification summaries lack run IDs, so the association caveat remains visible. The system demonstrates one representative invoice application, not universal PHP migration correctness or production migration readiness.

Raw audit history and the original private golden masters remain local. The public repository and deployed export intentionally contain only the reviewed public subset.
