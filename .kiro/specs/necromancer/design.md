# Design — Necromancer

## Overview
A CLI evidence pipeline drives two air-gapped PHP runtimes. A Next.js dashboard is deployed separately and initially displays a plainly labeled placeholder, later verified recorded run summaries. A future host-side LLM call generates patch text; a restricted harness validates and applies it.

## Pipeline
1. `fixtures/scenarios.json` defines deterministic requests with visible and held-out partitions.
2. `python verifier/main.py record` calls `docker compose run` on the PHP 5.6 service and captures actual JSON outputs.
3. Recorder writes immutable-in-practice fixture snapshots and SHA-256 entries for each file; verification checks the manifest.
4. `verify` runs PHP 8.3 with the same inputs and produces field-level visible diffs.
5. Later: repair model proposes a unified diff, validated by a host-side patch validator and applied only in a disposable copied modern app workspace; visible suite reruns, at most three times.
6. Later: held-out verification runs once on the final candidate without providing details to the model.

## Modules
- `legacy-app`: representative PHP 5.6 invoice program with old loose-comparison semantics.
- `modern-app`: initial naive port demonstrating the semantic regression.
- `verifier`: Python standard-library evidence recorder, manifest validator, and JSON comparator.
- `fixtures`: generated evidence and scenario definitions; an allowlist sits at repository root.
- `dashboard`: Next.js placeholder, later real report viewer.
- `repair-agent` (to implement): model client + structured prompt + schema check.

## Security model
- PHP 5.6 runs with no network, no published ports, read-only root filesystem, dropped capabilities, and unprivileged user.
- Docker invocation does not mount host credentials, fixture storage, or Docker socket inside the runtime.
- The model has no shell tools; model output is untrusted text. Validate strict patch paths, symlinks, byte limits, and allowed extensions, and re-check affected files after patch application.
- Secrets remain host-side in environment variables and are excluded from git.
- SHA-256 manifest detects accidental/unauthorized edits but is not a digital signature against a malicious host user able to edit both evidence and manifest. For stronger provenance, later sign the manifest or compare with a trusted git commit.
- Held-out fixtures are kept outside model-readable contexts. In a public repo they are not secret from humans; the claim is merely agent isolation.

## Determinism and comparison
The MVP handles stateless JSON requests and integer cents. Later, use seeded SQLite copies per scenario. Freeze time/randomness if introduced. Default is exact structured JSON match, zero allowable differences. A reviewed narrow allowlist requires reasons and hashing.

## Coverage
Optional legacy line coverage via Xdebug 2.5.x in PHP 5.6; verify build compatibility before claiming coverage. PCOV does not support PHP 5.6. Never invent coverage metrics.

## Deployment limitations
Dashboard can be deployed to Vercel. Docker execution and the future live LLM repair workflow remain local unless a separately secured backend is deployed. Never present recorded output as live cloud execution.
