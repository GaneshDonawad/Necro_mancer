# Tasks — implement in order

- [x] 1. Create a NEW GitHub repository (started after Oct 30, 2026), commit MIT license and `.kiro` directory, and install Docker Desktop and Python 3.11+.
- [x] 2. Verify Docker Compose V2 and run `docker compose build`; record any PHP 5.6 image compatibility issue.
- [x] 3. Run `python verifier/main.py record` to collect the actual outputs from PHP 5.6.
- [x] 4. Run `python verifier/main.py verify` and confirm a genuine regression for `customer_id: "guest"` against naive PHP 8.3.
- [x] 5. Prove fixture protection: edit a visible fixture, verify checksum rejection, then restore the original fixture.
- [ ] 6. Test optional Xdebug 2.5.x legacy coverage in a separate image. Do NOT block the main verifier if unsupported.
- [ ] 7. Deploy dashboard placeholder early; verify on mobile and desktop.
- [x] 8. Build model-agnostic patch generator with explicit per-run API budget, timeout, and max 3 tries.
- [x] 9. Add stringent unified-diff patch validation; tests for path traversal, absolute paths, symlink escape, oversized changes, and forbidden files.
- [x] 10. Apply each patch only to disposable modern source, rerun *entire* visible suite, and record accept/reject reason.
- [x] 11. Run held-out verification once for final selected candidate; never return held-out details to model.
- [x] 12. Add transparent dashboard results: observed pass rate, real measured code coverage if available, and unresolved failures separately.
- [ ] 13. Create demo video <3 minutes, add screenshots, public repo, real demo URL and actual Kiro evidence to Devpost.

## Milestone 3 — recorded evidence dashboard

- [x] Inspect existing reports, manifest, PHP source, specs and steering.
- [x] Build read-only Next.js / React / TypeScript / Tailwind command center.
- [x] Implement Exhume / Resurrect / Verify tabs, code diff, scenarios and audit timeline.
- [x] Generate schema-v1 allowlisted deployment snapshot; keep held-out details private.
- [x] Surface mock-provider provenance, missing baseline/modern outputs and source drift honestly.
- [x] Separate behavioural agreement, unresolved regressions, line coverage and evidence integrity.
- [x] Validate production build, TypeScript, original Python suite and report privacy/integrity tests.
- [x] Capture desktop, laptop, tablet and mobile browser evidence.
- [x] Run a new genuine Gemini repair; preserve raw history privately and export its actual verified results.
- [ ] Publish hosting and complete the Devpost/video submission; no deployment claimed here.

Milestone 3 implementation was performed with Codex. Committed Kiro specs/steering were consulted; this does not establish Kiro IDE or agent execution.

## Milestone 4

- [x] Diagnose mock report overwrite and isolate workflow test writes.
- [x] Run genuine Gemini 3.6 Flash repair with fallback disabled; 4/4 visible and 2/2 held-out passes.
- [x] Independently replay the applied patch and verify unchanged golden masters.
- [x] Exclude private fixtures, secrets and development artifacts from Git and deployment.
- [x] Prepare the requested GitHub remote and Vercel dashboard-only release.
