#!/usr/bin/env python3
"""Necromancer milestone 1: record real old-runtime outputs, replay on new.

Only standard-library Python is required. Docker Compose V2 is required for
record/verify. The fixture hash manifest protects outputs after recording.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
MANIFEST = FIXTURES / "manifest.sha256"
ALLOWLIST = ROOT / "allowlist.yml"
SCENARIOS = FIXTURES / "scenarios.json"


def encode(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def protected_files():
    return sorted(list((FIXTURES / "visible").glob("*.json")) +
                  list((FIXTURES / "heldout").glob("*.json")) +
                  [ALLOWLIST, SCENARIOS], key=lambda p: str(p.relative_to(ROOT)))


def write_manifest():
    entries = ["{}  {}".format(digest(p), p.relative_to(ROOT).as_posix()) for p in protected_files()]
    MANIFEST.write_text("\n".join(entries) + "\n", encoding="utf-8")


def verify_manifest():
    if not MANIFEST.exists():
        raise RuntimeError("Missing fixtures/manifest.sha256. Run 'record' first.")
    expected = {}
    for row in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not row.strip():
            continue
        hash_value, rel = row.split("  ", 1)
        if len(hash_value) != 64 or rel in expected or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise RuntimeError("Invalid manifest entry")
        expected[rel] = hash_value
    current = {p.relative_to(ROOT).as_posix(): digest(p) for p in protected_files()}
    if current != expected:
        raise RuntimeError("Evidence integrity check failed: manifest hashes or file list differ")


def execute(service, request):
    command = ["docker", "compose", "run", "--rm", "-T", "--no-deps", service]
    result = subprocess.run(command, cwd=ROOT, input=encode(request),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=25, check=False)
    if result.returncode != 0:
        raise RuntimeError("{} failed (exit {}): {}".format(service, result.returncode,
                                                           result.stderr.decode(errors="replace")[-700:]))
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError("{} produced invalid JSON: {}".format(service, exc))


def record(force=False):
    if MANIFEST.exists() and not force:
        raise RuntimeError("Evidence already exists. Refusing to overwrite. Use --force ONLY to intentionally regenerate.")
    scenario_sets = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    for split in ("visible", "heldout"):
        folder = FIXTURES / split
        folder.mkdir(parents=True, exist_ok=True)
        # Never silently leave obsolete files in the manifest.
        if force:
            for p in folder.glob("*.json"):
                p.unlink()
        for item in scenario_sets[split]:
            fixture = {"id": item["id"], "request": item["input"],
                       "expected": execute("legacy", item["input"])}
            path = folder / (item["id"] + ".json")
            path.write_bytes(encode(fixture))
            print("recorded", split, item["id"])
    write_manifest()
    verify_manifest()
    print("Saved SHA-256 manifest:", MANIFEST)


def differences(a, b, prefix="$", out=None):
    if out is None:
        out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            path = prefix + "." + key
            if key not in a or key not in b:
                out.append({"path": path, "expected": a.get(key, "<missing>"), "actual": b.get(key, "<missing>")})
            else:
                differences(a[key], b[key], path, out)
    elif type(a) is not type(b) or a != b:
        out.append({"path": prefix, "expected": a, "actual": b})
    return out


def verify(split):
    verify_manifest()
    folder = FIXTURES / split
    results = []
    for path in sorted(folder.glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        actual = execute("modern", fixture["request"])
        diffs = differences(fixture["expected"], actual)
        results.append({"scenario": fixture["id"], "pass": not diffs, "differences": diffs})
        print(("PASS" if not diffs else "FAIL"), fixture["id"])
        if split == "visible":
            for d in diffs:
                print("  {}: expected {!r}, got {!r}".format(d["path"], d["expected"], d["actual"]))
    report = {"split": split, "passed": sum(x["pass"] for x in results),
              "total": len(results), "results": results if split == "visible" else None}
    output = ROOT / "verification-report.json" if split == "visible" else ROOT / "heldout-summary.json"
    output.write_bytes(encode(report))
    print("Summary: {}/{} passed".format(report["passed"], report["total"]))
    if split == "heldout":
        print("Held-out input and detailed diffs are not emitted to the repair process.")
    return all(x["pass"] for x in results)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["record", "verify", "final-check", "integrity", "repair", "check-models"])
    p.add_argument("--force", action="store_true", help="Intentional evidence regeneration; record only")
    p.add_argument("--apply", action="store_true", help="Apply verified repair patch to modern-app/src on success")
    p.add_argument("--provider", choices=["gemini", "groq", "anthropic", "openai", "mock"], help="LLM provider")
    p.add_argument("--model", help="LLM model name")
    p.add_argument("--max-attempts", type=int, default=3, help="Maximum repair attempts")
    args = p.parse_args()
    try:
        if args.command == "record":
            record(force=args.force)
        elif args.command == "integrity":
            verify_manifest()
            print("All fixture and allowlist SHA-256 checks passed")
        elif args.command == "verify":
            if not verify("visible"):
                sys.exit(1)
        elif args.command == "final-check":
            if not verify("heldout"):
                sys.exit(1)
        elif args.command == "check-models":
            sys.path.insert(0, str(ROOT))
            from repair.check_models import main as run_check_models
            run_check_models()
        elif args.command == "repair":
            sys.path.insert(0, str(ROOT))
            from repair.config import RepairConfig
            from repair.runner import run_repair

            cfg = RepairConfig.from_env()
            if args.provider:
                cfg.provider = args.provider
                if not args.model:
                    if cfg.provider == "gemini":
                        cfg.model = "gemini-2.0-flash"
                    elif cfg.provider == "groq":
                        cfg.model = "llama-3.3-70b-versatile"
                    elif cfg.provider == "anthropic":
                        cfg.model = "claude-3-5-sonnet-20241022"
                    elif cfg.provider == "openai":
                        cfg.model = "gpt-4o"
                    else:
                        cfg.model = "mock-repair"
            if args.model:
                cfg.model = args.model
            if args.max_attempts:
                cfg.max_attempts = args.max_attempts

            rep = run_repair(config=cfg, apply_on_success=args.apply)
            if rep["final_status"] != "REPAIR_VERIFIED":
                sys.exit(1)
    except (RuntimeError, subprocess.TimeoutExpired, FileNotFoundError, KeyError, ValueError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
