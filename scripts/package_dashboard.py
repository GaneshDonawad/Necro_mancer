"""Produce an allowlisted source-file payload for the Vercel deployment API."""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dashboard = root / "dashboard"
snapshot = json.loads((dashboard / "recorded/run.v1.json").read_text())
assert snapshot["provider"] == "gemini" and snapshot["status"] == "REPAIR_VERIFIED"
assert snapshot["fixtureIntegrity"]["status"] == "passed"
assert snapshot["visible"] == {"passed": 4, "total": 4}
assert snapshot["heldout"] == {"passed": 2, "total": 2}
keys = []
for row in (root / ".env").read_text(encoding="utf-8-sig").splitlines():
    if not row.strip().startswith("#") and "=" in row:
        name, value = row.split("=", 1)
        value = value.strip().strip("\"'")
        if any(k in name for k in ("KEY", "TOKEN", "SECRET")) and len(value) >= 12:
            keys.append(value)
files = []
for folder in ("app", "lib", "recorded"):
    files.extend(p for p in (dashboard / folder).rglob("*") if p.is_file())
files.extend(dashboard / n for n in ("package.json", "package-lock.json", "next.config.ts", "next-env.d.ts", "postcss.config.mjs", "tsconfig.json"))
payload = []
for p in sorted(files):
    assert not p.is_symlink()
    data = p.read_text(encoding="utf-8-sig")
    assert not any(key in data for key in keys), "Credential in " + p.name
    payload.append({"file": p.relative_to(dashboard).as_posix(), "data": data, "encoding": "utf-8"})
public = json.dumps(snapshot)
assert not re.search(r"guest-edge|member-abc|api_key|[A-Z]:\\|/Users/|/home/|/mnt/", public, re.I)
print(json.dumps(payload))
