"""Disposable repair workspace manager.

Creates an isolated copy of modern-app for each repair attempt.
Executes candidate code in an air-gapped container via read-only volume mounts.
Protects the original repository from experimental or broken patches.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any

from repair.patcher import apply_patch_to_workspace


def _to_wsl_path(win_path: Path) -> str:
    """Converts a Windows path (e.g. D:\\Necromancer\\...) to WSL POSIX path (/mnt/d/Necromancer/...)."""
    resolved = win_path.resolve()
    parts = resolved.parts
    if len(parts) > 0 and len(parts[0]) >= 2 and parts[0][1] == ":":
        drive = parts[0][0].lower()
        subpath = "/".join(parts[1:])
        return f"/mnt/{drive}/{subpath}"
    return resolved.as_posix()


def _remove_readonly(func, path, excinfo):
    """Error handler for shutil.rmtree on Windows read-only files."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


class DisposableWorkspace:
    """Manages an isolated temporary workspace for testing candidate repairs."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
        self.modern_app_dir = self.root_dir / "modern-app"
        self.temp_dir: Path = None

    def __enter__(self) -> "DisposableWorkspace":
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def create(self) -> Path:
        """Copies the modern application into a disposable temporary directory."""
        tmp_base = self.root_dir / ".tmp"
        tmp_base.mkdir(parents=True, exist_ok=True)
        temp_dir_path = tempfile.mkdtemp(prefix="necromancer_ws_", dir=tmp_base)
        self.temp_dir = Path(temp_dir_path).resolve()
        shutil.copytree(self.modern_app_dir, self.temp_dir, dirs_exist_ok=True)
        return self.temp_dir

    def apply_patch(self, target_rel_path: str, patch_text: str) -> Path:
        """Applies a validated patch directly inside the disposable workspace."""
        if not self.temp_dir:
            raise RuntimeError("Disposable workspace not initialized")
        return apply_patch_to_workspace(self.temp_dir, target_rel_path, patch_text)

    def execute(self, request_data: Dict[str, Any], timeout: int = 25) -> Dict[str, Any]:
        """Runs the candidate modern app in the disposable workspace using Docker."""
        if not self.temp_dir:
            raise RuntimeError("Disposable workspace not initialized")

        src_dir = self.temp_dir / "src"
        wsl_src = _to_wsl_path(src_dir)

        # Mount the disposable workspace src into /app/src:ro in the PHP 8.3 container
        command = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "-v",
            f"{wsl_src}:/app/src:ro",
            "necromancer-modern:latest",
        ]

        input_bytes = (json.dumps(request_data, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

        result = subprocess.run(
            command,
            cwd=self.root_dir,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )

        if result.returncode != 0:
            err_msg = result.stderr.decode("utf-8", errors="replace")[-500:]
            raise RuntimeError(f"Candidate execution failed (code {result.returncode}): {err_msg}")

        try:
            return json.loads(result.stdout.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"Candidate output was not valid JSON: {exc}")

    def cleanup(self):
        """Safely removes the disposable workspace directory."""
        if self.temp_dir and self.temp_dir.exists():
            try:
                shutil.rmtree(self.temp_dir, onerror=_remove_readonly)
            except Exception:
                pass
            self.temp_dir = None
