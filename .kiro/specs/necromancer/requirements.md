# Requirements — Necromancer

## Scope
Hackathon MVP: one purpose-built representative legacy PHP 5.6 invoicing program, one PHP 8.3 modernization, and reproducible proof of behavioral equivalence. Never claim universal conversion.

## User stories and acceptance criteria

### R1 — Record reality
As a developer, I want to capture actual outputs from the old runtime so modern behavior can be compared with evidence.
- WHEN I run the golden-master recorder with a scenario set, THE SYSTEM SHALL execute scenarios on PHP 5.6 and save each request and observed response in a fixture.
- WHEN recording completes, THE SYSTEM SHALL create a SHA-256 manifest covering fixtures, the allowlist, and scenario definition.
- IF fixtures already exist, THE SYSTEM SHALL refuse to overwrite them without an explicit operator action.

### R2 — Replay reliably
As a developer, I want equal inputs in clean environments so comparisons reveal real regressions.
- WHEN I replay against PHP 8.3, THE SYSTEM SHALL use the same input and deterministic state as each recorded scenario.
- WHEN outputs differ, THE SYSTEM SHALL report the differing structured fields and mark the scenario failed unless a reviewed allowlist rule permits the difference.
- IF fixture integrity fails, THE SYSTEM SHALL stop without running the comparison.

### R3 — Protect the evidence
As a judge, I want assurance that the AI cannot edit evidence to make itself look successful.
- IF any fixture, allowlist, or harness hash is unexpectedly modified, THE SYSTEM SHALL invalidate the run.
- WHEN repair code runs, THE SYSTEM SHALL allow writes only to a disposable modern-app/source workspace; legacy source, fixtures, allowlist, and harness SHALL be unavailable for modification.

### R4 — Repair with bounded attempts (future milestone)
As a developer, I want AI to suggest verifiable patches without unrestricted execution rights.
- WHEN visible verification fails, THE SYSTEM SHALL give the model only relevant source and visible diffs, and request a unified diff.
- WHEN a patch is received, THE SYSTEM SHALL reject absolute paths, traversal, symlinks, unexpected paths/files, and oversized edits.
- WHEN a patch is accepted, THE SYSTEM SHALL run the whole visible suite, reject new failures, and log the attempt.
- AFTER at most three attempts, THE SYSTEM SHALL stop and report final status.

### R5 — Held-out verification (future milestone)
- WHEN a final candidate passes the visible suite, THE SYSTEM SHALL run held-out scenarios once and record only an aggregated result.
- THE SYSTEM SHALL never send held-out request data, outputs, or detailed failures to the repair model.
- IF held-out verification fails, THE SYSTEM SHALL mark the candidate rejected and SHALL NOT use that result to generate another repair attempt.

### R6 — Transparent presentation
- WHEN a judge opens the public dashboard, THE SYSTEM SHALL clearly indicate whether results are recorded or live.
- THE SYSTEM SHALL show pass/fail by module, measured legacy coverage with denominator when implemented, and unresolved regressions as separate measures.
- THE SYSTEM SHALL disclose that the legacy program is a representative app built for this hackathon.

## Non-goals
Universal legacy conversion, production migrations, public PHP 5.6 hosting, arbitrary untrusted code uploads, and autonomous shell access.
