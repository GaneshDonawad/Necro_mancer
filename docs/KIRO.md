# How Kiro is used

This project includes structured specs and steering under `.kiro/`. The directory is committed intentionally.

## Milestone 1: Evidence-First Resurrection Architecture
- Specifications created in `.kiro/specs/necromancer/` defining requirements R1-R6, architecture, and task sequencing.
- Golden-master recorder, SHA-256 fixture manifest, and dual-container (PHP 5.6 and PHP 8.3) environment built and verified.
- Genuine loose-comparison regression identified in `guest-string` scenario.

## Milestone 2: Real, Secure, Automated AI Repair Engine
- Designed and implemented the `repair/` module adhering strictly to `.kiro/steering/security.md` zero-trust principles.
- **Model-Agnostic LLM Client**: Supports Anthropic Claude, OpenAI GPT, Google Gemini, and offline Mock providers with per-token cost budgeting and timeouts.
- **Strict Patch Validator**: Pure-Python unified diff security validator rejecting absolute paths, directory traversal (`..`), symlinks, unauthorized files, and modifications outside `modern-app/src/*.php`.
- **Disposable Workspaces**: Each repair attempt executes in an isolated temporary workspace mounted read-only into an air-gapped PHP 8.3 container.
- **Evidence Protection**: SHA-256 fixture manifest checked before and after repair to guarantee that golden-master fixtures and harness code remain immutable.
- **Held-Out Isolation**: Candidate repairs that pass 100% of visible scenarios are verified against held-out scenarios exactly once. Hidden inputs, outputs, and diffs are strictly isolated from the AI prompt.
- **Machine-Readable Audit**: Emits `repair-report.json` with token metrics, costs, attempt logs, and clear audit statuses.

## Milestone 3: Recorded evidence dashboard (2026-11-23)

Codex implemented the Next.js / React / TypeScript / Tailwind dashboard after consulting the Kiro specs and steering files. This document does not claim Kiro IDE or Kiro agent development activity; the repository alone does not establish that provenance for prior milestones either.

The dashboard implements requirement R6 with clearly labeled Recorded Verification Results, three stage tabs, code comparison, scenario inspection, an audit-derived timeline, held-out aggregates, separate behavioural agreement and unresolved regression measures, and an explicit Code coverage not measured state.

The local server-side exporter checks fixture SHA-256 integrity and writes an allowlisted schema-v1 snapshot. Private held-out names, inputs, outputs and differences are excluded; runtime rendering and the download API consume only this snapshot. No live AI request, Docker execution or repair is triggered by the UI. The CLI remains the live-operation interface.

The supplied audit records mock / gemini-3.8-flash, zero initial regressions, one attempt and REPAIR_VERIFIED. Visible and held-out summaries show 4/4 and 2/2. The UI warns that this is not evidence of the live Gemini run described in the brief. Missing full modern responses, baseline reports and event timestamps are disclosed; source drift is flagged. Reports without run IDs cannot independently establish association with the repair.

See MILESTONE-3-VALIDATION.md and screenshots/ for actual validation evidence. The PHP applications, repair engine, verifier and protected fixture evidence were preserved. Existing Python tests ran in an isolated copy to avoid overwriting original reports.

## Milestone 4: genuine repair and release preparation

The prior mock evidence was superseded by an actual Gemini gemini-3.6-flash repair (run e176fe6d-e2d8-4255-933c-873fb790caed): one regression, one attempt, 4/4 visible and 2/2 held-out passes. Fixtures and manifest remained unchanged. Test isolation and actual response-provider attribution were corrected, and UUID-based local audit history was added.

No logs of actual Kiro IDE/agent usage were recovered. Specs and steering files are present and included in Git, but are not claimed as proof of Kiro execution. Codex performed these changes. See MILESTONE-4-REPORT.md for release validation.
