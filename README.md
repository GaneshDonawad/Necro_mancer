# Necromancer — Resurrection with Proof

An original Kiroween 2026 hackathon project demonstrating **PHP 5.6 → PHP 8.3 modernization with observable behavioral evidence and a zero-trust, free-tier AI repair engine**.

**Live dashboard:** https://necromancer-proof.vercel.app

**Source:** https://github.com/GaneshDonawad/Necro_mancer

[Final evidence and release report](docs/MILESTONE-4-REPORT.md)

---

## Quick start (Windows + VS Code)

The public repository excludes private held-out fixtures, scenario definitions, raw reports and the original manifest. See fixtures/README.md before recording a new local experiment. The dashboard works immediately with the sanitized recorded export.

### 1. Prerequisites
- **Docker Desktop** (or Docker Engine via WSL 2, Linux containers enabled)
- **Python 3.11+**
- **Node.js 22.18+** (Node 24 recommended for the native TypeScript export command)

### 2. Milestone 1 — Record, Verify, and Detect Regression
From the repository root:

```powershell
# Build PHP 5.6 and PHP 8.3 container images
docker compose build

# Record golden-master outputs from PHP 5.6 into fixtures/ + generate SHA-256 manifest
python verifier/main.py record

# Verify fixture integrity
python verifier/main.py integrity

# Replay visible scenarios against naive PHP 8.3 port
python verifier/main.py verify
```

`verify` will report **FAIL** for `guest-string`: PHP 5.6 and PHP 8.3 actually differ on loose string-to-number comparison (`"guest" == 0`). This produces four differing fields: `handling_cents`, `tax_cents`, `total_cents`, and `walk_in`.

---

## Free-Tier AI Repair Engine (Google Gemini + Groq)

Necromancer includes an automated AI repair engine (`repair/`) optimized for **100% free-tier AI services**:

- **Primary Provider**: **Google Gemini** (`gemini-2.0-flash`) via direct REST API with header-based key authentication.
- **Backup Provider**: **Groq** (`llama-3.3-70b-versatile`) via ultra-fast OpenAI-compatible endpoint.
- **Automatic Fallback**: If Gemini encounters rate limits (HTTP 429), timeouts, or service unavailability, the system automatically and seamlessly delegates the repair attempt to Groq without operator intervention.
- **Zero-Trust Security**: Unified diffs are strictly validated before application. Rejects absolute paths, directory traversal (`..`), symlinks, binary patches, and changes outside `modern-app/src/*.php`.
- **Disposable Workspaces**: Each repair attempt executes inside a temporary isolated workspace mounted read-only into an air-gapped Docker container (`--network none`, `--read-only`, `--cap-drop ALL`).
- **Evidence Protection**: SHA-256 fixture manifest (`fixtures/manifest.sha256`) is verified before and after each attempt. Golden-master evidence remains immutable.
- **Held-Out Test Isolation**: The AI never sees hidden test scenarios (`guest-edge`, `member-abc`). Held-out verification is executed exactly once on candidates that pass 100% of the visible suite.

### Step 1: Configure Your Free API Keys

1. Copy `.env.example` to `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Open `.env` and paste your free API keys:
   - **Google Gemini**: Get a free key at [Google AI Studio](https://aistudio.google.com/apikey) (15 RPM / 1,500 requests/day at zero cost).
   - **Groq**: Get a free key at [Groq Console](https://console.groq.com/keys) (30 RPM / 14,400 requests/day with Llama 3.3 70B at zero cost).

```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
GROQ_API_KEY=your_actual_groq_api_key_here
NECROMANCER_LLM_PROVIDER=gemini
NECROMANCER_LLM_MODEL=gemini-2.0-flash
NECROMANCER_GROQ_MODEL=llama-3.3-70b-versatile
NECROMANCER_ENABLE_FALLBACK=true
```

*(Note: `.env` is listed in `.gitignore` and will never be committed to source control).*

### Step 2: Run AI Repair

```powershell
# Run repair and automatically apply the verified patch if all visible and held-out tests pass:
python verifier/main.py repair --apply

# Or test in dry-run mode (runs verification in disposable workspace without modifying host source):
python verifier/main.py repair

# To force Groq explicitly:
python verifier/main.py repair --provider groq --apply
```

### Step 3: Inspect Audit Report

Every repair run persists a machine-readable audit report in `repair-report.json`:
```powershell
cat repair-report.json
```
The report includes run UUIDs, timestamps, LLM provider/model, token usage, cost, attempt logs, and evidence verification status.

---

## Automated Test Suite

```powershell
# Run diff engine unit tests
python -m unittest tests/test_verifier.py -v

# Run AI repair engine security, provider, fallback & workflow tests (22 comprehensive tests)
python -m unittest tests/test_repair.py -v
```

---

## Dashboard — Milestone 3

The Next.js / React / TypeScript / Tailwind dashboard is a read-only command center. It displays **Recorded Verification Results**. No API keys are required to run or deploy it.

```powershell
cd dashboard
npm ci
# Generate a snapshot from existing local reports and visible fixtures:
npm run export:run
npm test
npm run typecheck
npm run build
npm start
```

Open http://localhost:3000 (the validation server uses http://127.0.0.1:3000).

- EXHUME: representative PHP 5.6 invoice app, visible golden masters, fixture integrity.
- RESURRECT: actual audit patch, split/unified diff, provider/model and attempt details.
- VERIFY: scenario selection and pass/fail filters, original JSON, reported modern agreement and field differences.
- Eight-event audit timeline; only report-confirmed events are marked confirmed. Individual event timestamps appear only where retained.
- Behavioural agreement, unresolved visible failures, held-out aggregate and SHA-256 evidence status are separate measurements. **Code coverage not measured** is explicit.
- Responsive keyboard-accessible interface, reduced-motion support, loading/error states and sanitized JSON download.

### Validated live evidence ? Milestone 4

The original live report could not be recovered. The prior mock audit matched the workflow test, which wrote to the same latest-report path. That test now runs in a temporary root, and reports are archived automatically by run UUID.

A new real Google Gemini request using **gemini-3.6-flash** completed successfully: **one detected regression, one repair attempt, 4/4 visible tests, 2/2 held-out tests, and fixture integrity passed**. Run ID: e176fe6d-e2d8-4255-933c-873fb790caed. The API response ID and response hash are retained in the private audit. No fallback was enabled. The generated patch was security-validated, applied in a disposable workspace, verified, and then applied to modern source. Independent post-application replay also passed.

The dashboard exports that genuine recorded run. Code coverage is not measured. Full modern responses and most event-level timestamps are not retained; the UI discloses these limits. Standalone verification summaries lack run IDs, so the UI retains an association caveat.

### Docker-free deployment

`npm run export:run` reads `verification-report.json`, `repair-report.json`, `heldout-summary.json`, the manifest, and visible fixtures on the local server. It verifies all eight protected file hashes, including private files, without exporting private fixture names or contents. The allowlisted artifact is `dashboard/recorded/run.v1.json` (schema v1). Review and commit that artifact with the dashboard; regenerate it and rebuild after an intentional new run.

Deploy **only `dashboard/`**, using `npm ci`, build command `npm run build`, and start command `npm start`. The API file trace explicitly includes the snapshot. Do not ship root `.env`, fixtures, raw reports or PHP runtimes. Runtime rendering and `/api/report` read only the versioned snapshot and re-project allowed fields; missing or invalid exports produce unavailable states. The deployment needs no Docker, external API, database, or secrets. See docs/MILESTONE-4-REPORT.md for the current GitHub and deployment status.

SHA-256 is a local integrity check against a manifest, not a signature or proof of live model provenance. The export records the time hashes were checked, not a continuous integrity check of a remote backend.

### Validation and three-minute demo

See [Milestone 3 validation](docs/MILESTONE-3-VALIDATION.md) and [screenshots](docs/screenshots/). Begin with recorded/mock provenance, show Exhume and golden-master output, inspect split/unified patch views, select scenarios, then show coverage boundaries and export evidence. Live repair remains the local CLI documented above.


---

## Repository Structure

- `.kiro/` — source specifications and steering files.
- `legacy-app/` — isolated PHP 5.6 executable.
- `modern-app/` — PHP 8.3 port (naive port exhibits loose comparison regression).
- `verifier/` — golden-master evidence collection, SHA-256 verification, structured diff.
- `repair/` — AI repair engine: Gemini client, Groq client, fallback client, strict validator, patcher, workspace manager, reporter.
- `fixtures/` — visible and held-out scenario recordings with `manifest.sha256`.
- `tests/` — unit and integration tests for verifier and repair engine.
- `dashboard/` — deployable Next.js dashboard.
- `docs/` — documentation and Kiro integration notes.

---

## Security Model

- **Air-Gapped Runtimes**: PHP 5.6 and PHP 8.3 execute with `network_mode: none`, `read_only: true`, `cap_drop: [ALL]`, and `no-new-privileges: true`.
- **Zero-Trust AI**: The model has zero shell access. Output is treated as untrusted text, validated by pure-Python security rules before application.
- **Held-Out Guarantee**: Hidden scenarios are never exposed to the repair agent.
- **Immutable Evidence**: SHA-256 digests ensure evidence cannot be modified to fabricate passing results.

---

## License
MIT.
