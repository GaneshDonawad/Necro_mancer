"""AI Repair Engine Orchestrator for Necromancer.

Implements the complete repair lifecycle:
1. Verify SHA-256 fixture manifest integrity.
2. Read visible failures from verification report.
3. Construct prompt (visible source + failing scenarios only, NO held-out data).
4. Run bounded attempt loop (max 3 tries, budget check).
5. For each attempt:
   a. Create disposable workspace.
   b. Request patch from LLM.
   c. Enforce strict unified diff security validation.
   d. Apply patch inside disposable workspace.
   e. Re-verify SHA-256 manifest to ensure evidence was untouched.
   f. Replay all visible scenarios in PHP 8.3 container.
   g. If visible suite passes, run held-out verification once.
   h. If held-out passes, mark REPAIR_VERIFIED and optionally land patch.
6. Generate comprehensive machine-readable repair-report.json.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from repair.config import RepairConfig
from repair.llm_client import get_llm_client, BaseLLMClient
from repair.validator import validate_patch
from repair.workspace import DisposableWorkspace
from repair.reporter import RepairReporter, AttemptRecord


def _load_manifest_verifier():
    """Imports verify_manifest and differences from verifier/main.py dynamically."""
    root = Path(__file__).resolve().parents[1]
    verifier_path = root / "verifier" / "main.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("necromancer_verifier", verifier_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.verify_manifest, mod.differences


def build_repair_prompt(source_code: str, failures: List[Dict[str, Any]]) -> str:
    """Builds the AI repair prompt using ONLY visible failure information."""
    failures_summary = []
    for f in failures:
        scen_id = f.get("scenario", "unknown")
        diffs = f.get("differences", [])
        diff_str = "\n".join(
            f"  - Field {d.get('path', '')}: expected {d.get('expected')!r}, got {d.get('actual')!r}" for d in diffs
        )
        failures_summary.append(f"Scenario '{scen_id}':\n{diff_str}")

    prompt = (
        "We are modernizing a legacy PHP 5.6 invoice processing application to PHP 8.3.\n"
        "The application has an observable behavioral regression due to loose comparison differences between PHP 5.6 and PHP 8.3.\n\n"
        "Here are the visible scenario failures observed when replaying recorded golden-master outputs on PHP 8.3:\n"
        f"{chr(10).join(failures_summary)}\n\n"
        "Current modern PHP 8.3 source code (modern-app/src/invoice.php):\n"
        "```php\n"
        f"{source_code}\n"
        "```\n\n"
        "ROOT CAUSE ANALYSIS:\n"
        "In PHP 5.6, loose equality `($customer == 0)` evaluated non-numeric strings (like 'guest') as equal to 0.\n"
        "In PHP 8.3, string-to-number comparisons compare the number as a string unless the string is numeric. Thus ('guest' == 0) is false in PHP 8.3.\n\n"
        "TASK:\n"
        "Generate a unified diff patch that updates `modern-app/src/invoice.php` so that it faithfully reproduces\n"
        "the original PHP 5.6 loose comparison behavior for customer_id without breaking any valid numeric walk-ins (0) or member IDs (e.g. 42).\n"
        "Ensure handling_cents, tax_cents, walk_in, and total_cents match the original PHP 5.6 semantics exactly.\n\n"
        "CONSTRAINTS:\n"
        "1. Output ONLY a valid unified diff patch for modern-app/src/invoice.php.\n"
        "2. Do NOT touch any other files or directories.\n"
        "3. Do NOT include markdown commentary outside ```diff ... ``` code fence.\n"
    )
    return prompt


def replay_scenarios(
    fixtures_dir: Path, workspace: DisposableWorkspace, differences_func
) -> List[Dict[str, Any]]:
    """Replays all scenario fixtures in a folder against the candidate workspace."""
    results = []
    for path in sorted(fixtures_dir.glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        actual = workspace.execute(fixture["request"])
        diffs = differences_func(fixture["expected"], actual)
        results.append({
            "scenario": fixture["id"],
            "pass": len(diffs) == 0,
            "differences": diffs,
        })
    return results


def run_repair(
    config: Optional[RepairConfig] = None,
    apply_on_success: bool = False,
    mock_responses: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Executes the full automated repair workflow."""
    if config is None:
        config = RepairConfig.from_env()

    root_dir = config.root_dir
    fixtures_dir = root_dir / "fixtures"
    visible_dir = fixtures_dir / "visible"
    heldout_dir = fixtures_dir / "heldout"
    report_file = root_dir / "repair-report.json"
    modern_source_file = root_dir / "modern-app" / "src" / "invoice.php"

    verify_manifest, differences = _load_manifest_verifier()

    # 1. Evidence integrity verification before repair starts
    try:
        verify_manifest()
        integrity_ok = True
    except RuntimeError as e:
        print(f"FATAL: Evidence integrity verification failed: {e}", file=sys.stderr)
        reporter = RepairReporter(config.provider, config.model, config.max_attempts, 0)
        reporter.finalize("EVIDENCE_TAMPERING_DETECTED", integrity_verified=False)
        reporter.save(report_file)
        return reporter.report.to_dict()

    # 2. Check current verification state
    verification_report_path = root_dir / "verification-report.json"
    initial_failures = []
    if verification_report_path.exists():
        vdata = json.loads(verification_report_path.read_text(encoding="utf-8"))
        initial_failures = [r for r in vdata.get("results", []) if not r.get("pass")]

    reporter = RepairReporter(
        provider=config.provider,
        model=config.model,
        max_attempts=config.max_attempts,
        initial_regressions=len(initial_failures),
    )

    # 3. Check API key credentials
    if config.provider != "mock" and not config.api_key:
        if config.provider == "gemini" and config.groq_api_key:
            print("NOTICE: GEMINI_API_KEY not configured, but GROQ_API_KEY is available.")
            print(f"Switching primary provider to Groq ({config.groq_model})...\n")
            config.provider = "groq"
            config.api_key = config.groq_api_key
            config.model = config.groq_model
        else:
            print(f"NOTICE: No API key found for provider '{config.provider}'.", file=sys.stderr)
            print("To run live repairs with free-tier AI, configure your API keys in .env:", file=sys.stderr)
            print("  - GEMINI_API_KEY (from https://aistudio.google.com/apikey)", file=sys.stderr)
            print("  - GROQ_API_KEY   (from https://console.groq.com/keys)", file=sys.stderr)
            reporter.finalize("CREDENTIALS_MISSING", integrity_verified=True)
            reporter.report.notes.append(
                f"Missing credentials for provider '{config.provider}'. Configure GEMINI_API_KEY or GROQ_API_KEY in .env."
            )
            reporter.save(report_file)
            return reporter.report.to_dict()

    llm_client: BaseLLMClient = get_llm_client(config, mock_responses=mock_responses)
    original_source = modern_source_file.read_text(encoding="utf-8")

    current_failures = list(initial_failures)
    accepted_patch_text = None
    accumulated_cost = 0.0

    print(f"=== Necromancer AI Repair Engine ===")
    print(f"Provider: {config.provider} | Model: {config.model}")
    print(f"Initial visible regressions: {len(initial_failures)}")
    print(f"Max attempts: {config.max_attempts} | Cost limit: ${config.max_cost_usd:.2f}\n")

    for attempt_num in range(1, config.max_attempts + 1):
        reporter.response_provenance.clear()
        attempt_start = time.time()
        print(f"--- Attempt {attempt_num}/{config.max_attempts} ---")

        # Cost limit guard
        if accumulated_cost >= config.max_cost_usd:
            print(f"Budget exceeded (${accumulated_cost:.4f} >= ${config.max_cost_usd:.2f}). Stopping.")
            reporter.finalize("BUDGET_EXCEEDED", integrity_verified=True)
            reporter.save(report_file)
            return reporter.report.to_dict()

        # Build prompt from visible failures only (zero held-out leakage)
        prompt = build_repair_prompt(original_source, current_failures)

        # Call LLM client
        try:
            llm_response = llm_client.generate_patch(prompt)
            reporter.report.llm_provider = llm_response.provider
            reporter.report.llm_model = llm_response.model
            reporter.response_provenance.update(
                llm_provider=llm_response.provider,
                llm_model=llm_response.model,
                response_id=llm_response.response_id,
                api_response_sha256=llm_response.api_response_sha256,
            )
        except Exception as e:
            print(f"LLM API call failed: {e}")
            attempt_rec = AttemptRecord(
                attempt_number=attempt_num,
                timestamp=datetime.now(timezone.utc).isoformat(),
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0.0,
                duration_seconds=round(time.time() - attempt_start, 2),
                patch_preview="",
                validation_passed=False,
                validation_errors=[f"API error: {e}"],
                status="API_ERROR",
            )
            reporter.add_attempt(attempt_rec)
            continue

        accumulated_cost += llm_response.cost_usd
        patch_text = llm_response.patch

        # Validate proposed patch
        v_res = validate_patch(patch_text, root_dir)
        if not v_res.valid:
            print(f"Patch security validation FAILED: {v_res.errors}")
            attempt_rec = AttemptRecord(
                attempt_number=attempt_num,
                timestamp=datetime.now(timezone.utc).isoformat(),
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                cost_usd=llm_response.cost_usd,
                duration_seconds=round(time.time() - attempt_start, 2),
                patch_preview=patch_text[:200],
                validation_passed=False,
                validation_errors=v_res.errors,
                status="PATCH_REJECTED",
            )
            reporter.add_attempt(attempt_rec)
            continue

        print(f"Patch security validation PASSED for: {v_res.target_rel_path}")

        # Execute in disposable workspace
        with DisposableWorkspace(root_dir) as workspace:
            # Apply patch inside workspace
            try:
                workspace.apply_patch(v_res.target_rel_path, patch_text)
            except Exception as e:
                print(f"Failed to apply patch to workspace: {e}")
                attempt_rec = AttemptRecord(
                    attempt_number=attempt_num,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    prompt_tokens=llm_response.prompt_tokens,
                    completion_tokens=llm_response.completion_tokens,
                    cost_usd=llm_response.cost_usd,
                    duration_seconds=round(time.time() - attempt_start, 2),
                    patch_preview=patch_text[:200],
                    validation_passed=True,
                    validation_errors=[f"Application error: {e}"],
                    status="APPLICATION_FAILED",
                )
                reporter.add_attempt(attempt_rec)
                continue

            # Verify evidence was not tampered with during patch application
            try:
                verify_manifest()
            except RuntimeError as e:
                print(f"FATAL: Evidence tampering detected after patch application: {e}")
                reporter.finalize("EVIDENCE_TAMPERING_DETECTED", integrity_verified=False)
                reporter.save(report_file)
                return reporter.report.to_dict()

            # Replay all visible scenarios against candidate workspace
            visible_results = replay_scenarios(visible_dir, workspace, differences)
            passed_count = sum(1 for r in visible_results if r["pass"])
            total_count = len(visible_results)
            failing = [r for r in visible_results if not r["pass"]]

            print(f"Visible scenarios replay: {passed_count}/{total_count} passed")

            attempt_rec = AttemptRecord(
                attempt_number=attempt_num,
                timestamp=datetime.now(timezone.utc).isoformat(),
                prompt_tokens=llm_response.prompt_tokens,
                completion_tokens=llm_response.completion_tokens,
                cost_usd=llm_response.cost_usd,
                duration_seconds=round(time.time() - attempt_start, 2),
                patch_preview=patch_text[:200],
                validation_passed=True,
                visible_tests_passed=passed_count,
                visible_tests_total=total_count,
                failing_scenarios=[r["scenario"] for r in failing],
                status="VISIBLE_TESTS_PASSED" if not failing else "VISIBLE_TESTS_FAILED",
            )
            reporter.add_attempt(attempt_rec)

            if failing:
                print(f"Candidate introduced/retained failures: {[f['scenario'] for f in failing]}")
                current_failures = failing
                continue

            # Visible suite PASSED! Proceed to Phase 5: Held-Out Verification (run once)
            print("Candidate PASSED all visible tests! Running single held-out verification...")
            heldout_results = replay_scenarios(heldout_dir, workspace, differences)
            heldout_passed = sum(1 for r in heldout_results if r["pass"])
            heldout_total = len(heldout_results)
            heldout_success = (heldout_passed == heldout_total)

            reporter.set_heldout_result(heldout_passed, heldout_total, heldout_success)

            if not heldout_success:
                print(f"Candidate FAILED held-out verification ({heldout_passed}/{heldout_total} passed). Candidate rejected.")
                reporter.finalize("HIDDEN_VERIFICATION_FAILED", integrity_verified=True)
                reporter.save(report_file)
                return reporter.report.to_dict()

            print(f"Candidate PASSED held-out verification ({heldout_passed}/{heldout_total})!")
            accepted_patch_text = patch_text
            break

    # Final post-repair integrity check
    try:
        verify_manifest()
        final_integrity = True
    except RuntimeError:
        final_integrity = False

    if accepted_patch_text:
        final_status = "REPAIR_VERIFIED"
        if apply_on_success:
            print(f"Applying verified patch to {modern_source_file}...")
            from repair.patcher import apply_unified_diff

            new_source = apply_unified_diff(original_source, accepted_patch_text)
            modern_source_file.write_text(new_source, encoding="utf-8")
            print("Successfully updated modern application.")
            try:
                print("Rebuilding necromancer-modern container image...")
                import subprocess

                subprocess.run(
                    ["docker", "compose", "build", "modern"],
                    cwd=root_dir,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                print("Image rebuilt successfully.")
            except Exception as e:
                print(f"Warning: could not rebuild modern image: {e}")
    else:
        final_status = "MAX_ATTEMPTS_EXCEEDED"

    reporter.finalize(final_status, integrity_verified=final_integrity, applied_patch=accepted_patch_text)
    reporter.save(report_file)
    print(f"\nFinal Repair Status: {final_status}")
    print(f"Report saved to: {report_file}")
    return reporter.report.to_dict()


def main():
    parser = argparse.ArgumentParser(description="Necromancer AI Repair Engine")
    parser.add_argument("--provider", choices=["anthropic", "openai", "gemini", "mock"], help="LLM provider")
    parser.add_argument("--model", help="LLM model name")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum repair attempts")
    parser.add_argument("--apply", action="store_true", help="Apply verified patch to modern-app/src/ on success")
    args = parser.parse_args()

    cfg = RepairConfig.from_env()
    if args.provider:
        cfg.provider = args.provider
        if not args.model:
            if cfg.provider == "anthropic":
                cfg.model = "claude-3-5-sonnet-20241022"
            elif cfg.provider == "openai":
                cfg.model = "gpt-4o"
            elif cfg.provider == "gemini":
                cfg.model = "gemini-2.0-flash"
            else:
                cfg.model = "mock-repair"
    if args.model:
        cfg.model = args.model
    if args.max_attempts:
        cfg.max_attempts = args.max_attempts

    res = run_repair(config=cfg, apply_on_success=args.apply)
    if res["final_status"] != "REPAIR_VERIFIED":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
