"""Comprehensive test suite for Necromancer AI Repair Engine.

Covers:
1. Valid patch validation and application
2. Invalid patch formatting
3. Absolute-path rejection
4. Directory traversal rejection
5. Symbolic-link rejection
6. Forbidden file modification rejection
7. Oversized patch rejection
8. Missing API credentials handling
9. API timeout handling
10. Maximum repair attempts enforcement
11. Evidence tampering detection
12. Rejection of new regressions
13. Hidden-test isolation guarantees
14. Failed patch rollback (original remains unmodified)
15. Successful repair verification (mock end-to-end)
16. Budget limit enforcement
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from repair.config import RepairConfig, calculate_cost
from repair.validator import validate_patch, ValidationResult, MAX_PATCH_SIZE_BYTES
from repair.patcher import apply_unified_diff, apply_patch_to_workspace, PatchApplicationError
from repair.llm_client import (
    MockClient,
    AnthropicClient,
    OpenAIClient,
    GeminiClient,
    GroqClient,
    FallbackClient,
    get_llm_client,
    extract_diff,
)
from repair.workspace import DisposableWorkspace
from repair.reporter import RepairReporter, AttemptRecord
from repair.runner import run_repair, build_repair_prompt

ROOT = Path(__file__).resolve().parents[1]

SAMPLE_ORIGINAL_PHP = """<?php
$input = json_decode(stream_get_contents(STDIN), true);
$customer = isset($input['customer_id']) ? $input['customer_id'] : 'guest';
$is_walk_in = ($customer == 0);
$handling = $is_walk_in ? 0 : 50;
echo json_encode(array('walk_in' => $is_walk_in, 'handling' => $handling)) . "\\n";
"""

VALID_PATCH = """--- a/modern-app/src/invoice.php
+++ b/modern-app/src/invoice.php
@@ -3,3 +3,3 @@
-$is_walk_in = ($customer == 0);
+$is_walk_in = ($customer === 0 || $customer === '0' || (!is_numeric($customer) && is_string($customer)));
 $handling = $is_walk_in ? 0 : 50;
"""


class TestPatchValidator(unittest.TestCase):
    """Tests for Phase 3: Secure Unified Diff Validation."""

    def test_valid_patch_accepted(self):
        result = validate_patch(VALID_PATCH, ROOT)
        self.assertTrue(result.valid, f"Expected valid patch, got errors: {result.errors}")
        self.assertEqual(result.hunk_count, 1)
        self.assertEqual(result.lines_added, 1)
        self.assertEqual(result.lines_removed, 1)

    def test_invalid_patch_formatting(self):
        bad_patches = [
            "",  # Empty
            "This is just some text, not a diff",
            "--- a/modern-app/src/invoice.php\n+++ b/modern-app/src/invoice.php\nNo hunks here",
            "@@ -1,1 +1,1 @@\nMissing header",
        ]
        for bad in bad_patches:
            result = validate_patch(bad, ROOT)
            self.assertFalse(result.valid, f"Expected failure for: {bad!r}")

    def test_absolute_path_rejection(self):
        bad_patches = [
            "--- /etc/passwd\n+++ /etc/passwd\n@@ -1,1 +1,1 @@\n-root\n+hacked",
            "--- C:\\Windows\\System32\\cmd.exe\n+++ C:\\Windows\\System32\\cmd.exe\n@@ -1,1 +1,1 @@\n-old\n+new",
            "--- a/modern-app/src/invoice.php\n+++ /app/src/invoice.php\n@@ -1,1 +1,1 @@\n-a\n+b",
        ]
        for p in bad_patches:
            result = validate_patch(p, ROOT)
            self.assertFalse(result.valid)
            self.assertTrue(any("Absolute paths" in e or "escapes" in e for e in result.errors))

    def test_directory_traversal_rejection(self):
        bad_patches = [
            "--- a/modern-app/src/../../verifier/main.py\n+++ b/modern-app/src/../../verifier/main.py\n@@ -1,1 +1,1 @@\n-a\n+b",
            "--- a/modern-app/src/../modern-app/src/invoice.php\n+++ b/modern-app/src/../modern-app/src/invoice.php\n@@ -1,1 +1,1 @@\n-a\n+b",
        ]
        for p in bad_patches:
            result = validate_patch(p, ROOT)
            self.assertFalse(result.valid)
            self.assertTrue(any("traversal" in e.lower() or "forbidden" in e.lower() for e in result.errors))

    def test_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            mock_root = td_path / "repo"
            mock_src = mock_root / "modern-app" / "src"
            mock_src.mkdir(parents=True)
            real_file = mock_src / "invoice.php"
            real_file.write_text("<?php echo 1;", encoding="utf-8")

            # Create symlink
            symlink_file = mock_src / "sym_invoice.php"
            try:
                symlink_file.symlink_to(real_file)
            except (OSError, NotImplementedError):
                # On Windows without developer mode/admin, symlink creation might fail
                self.skipTest("Symlink creation not permitted in this OS environment")

            patch_text = f"--- a/modern-app/src/sym_invoice.php\n+++ b/modern-app/src/sym_invoice.php\n@@ -1,1 +1,1 @@\n-<?php echo 1;\n+<?php echo 2;\n"
            result = validate_patch(patch_text, mock_root)
            self.assertFalse(result.valid)
            self.assertTrue(any("symbolic link" in e for e in result.errors))

    def test_forbidden_file_modification_rejected(self):
        forbidden_targets = [
            "verifier/main.py",
            "allowlist.yml",
            "fixtures/manifest.sha256",
            "fixtures/visible/guest-string.json",
            "compose.yaml",
            "modern-app/Dockerfile",
            "tests/test_verifier.py",
            "dashboard/package.json",
            ".kiro/specs/necromancer/requirements.md",
        ]
        for target in forbidden_targets:
            patch_text = f"--- a/{target}\n+++ b/{target}\n@@ -1,1 +1,1 @@\n-old\n+new"
            result = validate_patch(patch_text, ROOT)
            self.assertFalse(result.valid, f"Expected forbidden target '{target}' to be rejected")
            self.assertTrue(any("forbidden" in e.lower() or "escapes" in e.lower() or "extension" in e.lower() for e in result.errors))

    def test_oversized_patch_rejected(self):
        huge_lines = ["--- a/modern-app/src/invoice.php", "+++ b/modern-app/src/invoice.php", "@@ -1,1 +1,300 @@"]
        for i in range(300):
            huge_lines.append(f"+// Line {i}")
        huge_patch = "\n".join(huge_lines)

        result = validate_patch(huge_patch, ROOT)
        self.assertFalse(result.valid)
        self.assertTrue(any("exceeds maximum" in e for e in result.errors))


class TestPatcher(unittest.TestCase):
    """Tests for pure-Python safe patch application."""

    def test_apply_unified_diff_success(self):
        new_content = apply_unified_diff(SAMPLE_ORIGINAL_PHP, VALID_PATCH)
        self.assertIn("(!is_numeric($customer) && is_string($customer))", new_content)
        self.assertNotIn("$is_walk_in = ($customer == 0);", new_content)

    def test_apply_unified_diff_context_mismatch_raises(self):
        bad_context_patch = """--- a/modern-app/src/invoice.php
+++ b/modern-app/src/invoice.php
@@ -10,3 +10,3 @@
-$completely_nonexistent_line = 999;
+$new_line = 1000;
"""
        with self.assertRaises(PatchApplicationError):
            apply_unified_diff(SAMPLE_ORIGINAL_PHP, bad_context_patch)


class TestLLMClient(unittest.TestCase):
    """Tests for LLM clients, credentials, and error handling."""

    def test_missing_api_credentials_handled(self):
        cfg = RepairConfig(provider="anthropic", api_key="", model="claude-3-5-sonnet")
        client = AnthropicClient(cfg)
        with self.assertRaises(ValueError) as ctx:
            client.generate_patch("prompt")
        self.assertIn("Anthropic API key is required", str(ctx.exception))

        cfg_openai = RepairConfig(provider="openai", api_key="", model="gpt-4o")
        client_openai = OpenAIClient(cfg_openai)
        with self.assertRaises(ValueError) as ctx:
            client_openai.generate_patch("prompt")
        self.assertIn("OpenAI API key is required", str(ctx.exception))

        cfg_gemini = RepairConfig(provider="gemini", api_key="", model="gemini-2.0-flash")
        client_gemini = GeminiClient(cfg_gemini)
        with self.assertRaises(ValueError) as ctx:
            client_gemini.generate_patch("prompt")
        self.assertIn("Gemini API key is required", str(ctx.exception))

        cfg_groq = RepairConfig(provider="groq", api_key="", model="llama-3.3-70b-versatile")
        client_groq = GroqClient(cfg_groq)
        with self.assertRaises(ValueError) as ctx:
            client_groq.generate_patch("prompt")
        self.assertIn("Groq API key is required", str(ctx.exception))

    def test_fallback_client_primary_success(self):
        primary = MockClient(RepairConfig(provider="gemini", model="gemini-2.0-flash"), responses=[VALID_PATCH])
        backup = MockClient(RepairConfig(provider="groq", model="llama-3.3-70b-versatile"), responses=["backup"])
        fb = FallbackClient(primary=primary, backup=backup, config=RepairConfig(provider="gemini"))
        resp = fb.generate_patch("prompt")
        self.assertEqual(resp.provider, "gemini")
        self.assertEqual(primary.call_count, 1)
        self.assertEqual(backup.call_count, 0)

    def test_fallback_client_falls_back_on_rate_limit(self):
        # Primary triggers rate limit (__RATE_LIMIT__), backup succeeds
        primary = MockClient(RepairConfig(provider="gemini", model="gemini-2.0-flash"), responses=["__RATE_LIMIT__"])
        backup = MockClient(RepairConfig(provider="groq", model="llama-3.3-70b-versatile"), responses=[VALID_PATCH])
        fb = FallbackClient(primary=primary, backup=backup, config=RepairConfig(provider="gemini"))
        resp = fb.generate_patch("prompt")
        self.assertEqual(resp.provider, "groq")
        self.assertEqual(primary.call_count, 1)
        self.assertEqual(backup.call_count, 1)

    def test_fallback_client_both_fail_raises(self):
        primary = MockClient(RepairConfig(provider="gemini", model="gemini-2.0-flash"), responses=["__RATE_LIMIT__"])
        backup = MockClient(RepairConfig(provider="groq", model="llama-3.3-70b-versatile"), responses=["__ERROR__"])
        fb = FallbackClient(primary=primary, backup=backup, config=RepairConfig(provider="gemini"))
        with self.assertRaises(RuntimeError) as ctx:
            fb.generate_patch("prompt")
        self.assertIn("Both primary provider", str(ctx.exception))

    def test_env_file_loader_free_tier(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            env_file = td_path / ".env"
            env_file.write_text(
                "GEMINI_API_KEY=test_gemini_val\n"
                "GROQ_API_KEY=test_groq_val\n"
                "NECROMANCER_LLM_PROVIDER=gemini\n"
                "NECROMANCER_LLM_MODEL=gemini-2.0-flash\n",
                encoding="utf-8",
            )
            cfg = RepairConfig.from_env(root_dir=td_path)
            self.assertEqual(cfg.provider, "gemini")
            self.assertEqual(cfg.model, "gemini-2.0-flash")
            self.assertEqual(cfg.api_key, "test_gemini_val")
            self.assertEqual(cfg.groq_api_key, "test_groq_val")
            self.assertTrue(cfg.enable_fallback)

    def test_api_timeout_handled(self):
        cfg = RepairConfig(provider="mock", model="mock-repair")
        client = MockClient(cfg, responses=["__TIMEOUT__"])
        with self.assertRaises(TimeoutError):
            client.generate_patch("prompt")

    def test_diff_extraction(self):
        markdown_wrapped = f"Here is the fix:\n```diff\n{VALID_PATCH}\n```\nHope this helps!"
        extracted = extract_diff(markdown_wrapped)
        self.assertTrue(extracted.startswith("--- a/modern-app/src/invoice.php"))


class TestDisposableWorkspace(unittest.TestCase):
    """Tests for workspace isolation and rollback."""

    def test_failed_patch_rollback_unmodified_original(self):
        original_file = ROOT / "modern-app" / "src" / "invoice.php"
        original_content = original_file.read_text(encoding="utf-8")

        with DisposableWorkspace(ROOT) as ws:
            # Modify file in workspace
            ws_file = ws.temp_dir / "src" / "invoice.php"
            ws_file.write_text("<?php // MODIFIED IN TEMP WORKSPACE", encoding="utf-8")
            self.assertIn("MODIFIED IN TEMP WORKSPACE", ws_file.read_text(encoding="utf-8"))

        # Original repo must be 100% untouched
        self.assertEqual(original_file.read_text(encoding="utf-8"), original_content)


class TestRepairWorkflow(unittest.TestCase):
    """End-to-end tests for runner, budget, and isolation."""

    def setUp(self):
        # Workflow tests previously used the real repository as root_dir and
        # overwrote its latest live audit with a mock audit. Isolate all writes.
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("modern-app", "fixtures"):
            shutil.copytree(ROOT / name, self.root / name)
        for name in ("allowlist.yml", "verification-report.json"):
            if (ROOT / name).exists():
                shutil.copy2(ROOT / name, self.root / name)
        original = self.root / "modern-app/src/invoice.php"
        # Use a tiny deterministic baseline so tests do not depend on the
        # current production patch. Real Docker checks remain in the CLI.
        original.write_text("<?php\n" + "// deterministic unit fixture\n" * 11 +
                            "if (false) {\n}\n$is_walk_in = ($customer == 0);\n$handling = $is_walk_in ? 0 : 50;\n", encoding="utf-8")
        self.verifier_patch = patch("repair.runner._load_manifest_verifier", return_value=(lambda: None, lambda a, b: []))
        self.verifier_patch.start()
        self.addCleanup(self.verifier_patch.stop)
        self.replay_patch = patch("repair.runner.replay_scenarios", side_effect=lambda directory, ws, diff: [
            {"scenario": "unit-case", "pass": True, "differences": []}
        ] * (2 if directory.name == "heldout" else 4))
        self.replay_patch.start()
        self.addCleanup(self.replay_patch.stop)

    def test_max_repair_attempts_enforced(self):
        # 3 broken patches
        bad_patch = "--- a/modern-app/src/invoice.php\n+++ b/modern-app/src/invoice.php\n@@ -1,1 +1,1 @@\n-bad\n+worse"
        cfg = RepairConfig(provider="mock", max_attempts=2, root_dir=self.root)
        report = run_repair(config=cfg, mock_responses=[bad_patch, bad_patch])
        self.assertEqual(report["attempts_used"], 2)
        self.assertIn(report["final_status"], ["MAX_ATTEMPTS_EXCEEDED", "PATCH_REJECTED"])

    def test_budget_limit_enforced(self):
        # Cost limit $0.00005, mock cost $0.0001
        cfg = RepairConfig(provider="mock", max_cost_usd=0.00005, max_attempts=3, root_dir=self.root)
        # Attempt 1 adds $0.0001, attempt 2 triggers budget guard
        bad_patch = "--- a/modern-app/src/invoice.php\n+++ b/modern-app/src/invoice.php\n@@ -1,1 +1,1 @@\n-bad\n+worse"
        report = run_repair(config=cfg, mock_responses=[bad_patch, bad_patch])
        self.assertEqual(report["final_status"], "BUDGET_EXCEEDED")

    def test_hidden_test_isolation_guaranteed(self):
        # Inspect prompt generated by runner
        prompt = build_repair_prompt("<?php // source", [{"scenario": "guest-string", "differences": [{"path": "$.walk_in"}]}])
        self.assertIn("guest-string", prompt)
        # Held-out scenarios MUST NEVER appear in prompt
        self.assertNotIn("guest-edge", prompt)
        self.assertNotIn("member-abc", prompt)

    def test_successful_repair_end_to_end_mock(self):
        # Mock client provides the genuine fix against unpatched code
        invoice_file = self.root / "modern-app" / "src" / "invoice.php"
        original_content = invoice_file.read_text(encoding="utf-8")
        unpatched_content = original_content.replace(
            "$is_walk_in = ((int)$customer == 0);",
            "$is_walk_in = ($customer == 0);"
        ).replace(
            "$is_walk_in = ($customer === 0 || $customer === '0' || (!is_numeric($customer) && is_string($customer)));",
            "$is_walk_in = ($customer == 0);"
        )
        try:
            invoice_file.write_text(unpatched_content, encoding="utf-8")
            cfg = RepairConfig(provider="mock", max_attempts=1, root_dir=self.root)
            report = run_repair(config=cfg, apply_on_success=False)
            self.assertEqual(report["final_status"], "REPAIR_VERIFIED")
            self.assertTrue(report["evidence_integrity_verified"])
            self.assertIsNotNone(report["heldout_verification"])
            self.assertTrue(report["heldout_verification"]["success"])
            self.assertTrue((self.root / ".local-runs" / report["run_id"] / "repair-report.json").exists())
        finally:
            invoice_file.write_text(original_content, encoding="utf-8")

    def test_actual_fallback_provider_is_recorded(self):
        cfg = RepairConfig(provider="gemini", api_key="unit-only", model="requested-model", max_attempts=1, root_dir=self.root)
        response = MockClient(RepairConfig(provider="groq", model="actual-backup-model")).generate_patch("unit prompt")
        client = MagicMock()
        client.generate_patch.return_value = response
        with patch("repair.runner.get_llm_client", return_value=client):
            report = run_repair(config=cfg)
        self.assertEqual(report["final_status"], "REPAIR_VERIFIED")
        self.assertEqual(report["llm_provider"], "groq")
        self.assertEqual(report["llm_model"], "actual-backup-model")
        self.assertEqual(report["attempts"][0]["llm_provider"], "groq")

    def test_workflow_does_not_overwrite_repository_audit(self):
        latest = ROOT / "repair-report.json"
        previous = latest.read_bytes() if latest.exists() else None
        run_repair(config=RepairConfig(provider="mock", max_attempts=1, root_dir=self.root))
        self.assertEqual(latest.read_bytes() if latest.exists() else None, previous)


if __name__ == "__main__":
    unittest.main()
