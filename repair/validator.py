"""Strict security validator for AI-proposed unified diff patches.

Enforces zero-trust rules:
1. Rejects absolute paths, path traversal ('..'), and symbolic links.
2. Allows modifications ONLY to existing files under modern-app/src/*.php.
3. Rejects modifications to verifier, fixtures, allowlist, docker configs, tests, dashboard.
4. Enforces strict byte size and line count bounds.
5. Rejects binary patches and invalid hunk headers.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

MAX_PATCH_SIZE_BYTES = 64 * 1024  # 64 KB limit
MAX_PATCH_LINES = 250
FORBIDDEN_FILE_PATTERNS = [
    r"verifier",
    r"fixtures",
    r"allowlist",
    r"compose",
    r"docker",
    r"tests",
    r"dashboard",
    r"\.kiro",
    r"\.git",
    r"\.env",
]


@dataclass
class ValidationResult:
    """Outcome of patch security validation."""

    valid: bool
    target_rel_path: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    hunk_count: int = 0
    lines_added: int = 0
    lines_removed: int = 0


def _clean_diff_path(path_str: str) -> str:
    """Strips git diff prefixes like a/, b/, ./ from path strings."""
    path_str = path_str.strip()
    # Remove timestamp suffix often found in diffs (e.g. 2026-11-22 00:00:00)
    path_str = re.split(r"\t+|\s{2,}", path_str)[0].strip()
    if path_str.startswith("a/") or path_str.startswith("b/"):
        path_str = path_str[2:]
    if path_str.startswith("./"):
        path_str = path_str[2:]
    return path_str.replace("\\", "/")


def validate_patch(patch_text: str, root_dir: Path) -> ValidationResult:
    """Validates a unified diff patch string against all security constraints."""
    errors = []

    if not isinstance(patch_text, str) or not patch_text.strip():
        return ValidationResult(valid=False, errors=["Empty or non-string patch"])

    # 1. Byte size and line count check
    patch_bytes = patch_text.encode("utf-8")
    if len(patch_bytes) > MAX_PATCH_SIZE_BYTES:
        return ValidationResult(
            valid=False,
            errors=[f"Patch size ({len(patch_bytes)} bytes) exceeds maximum {MAX_PATCH_SIZE_BYTES} bytes"],
        )

    # 2. Binary content check
    if b"\0" in patch_bytes or "GIT binary patch" in patch_text:
        return ValidationResult(valid=False, errors=["Binary patches are strictly forbidden"])

    lines = patch_text.splitlines()
    if len(lines) > MAX_PATCH_LINES:
        return ValidationResult(
            valid=False,
            errors=[f"Patch line count ({len(lines)}) exceeds maximum {MAX_PATCH_LINES} lines"],
        )

    # 3. Parse header paths
    old_path_raw = None
    new_path_raw = None

    for line in lines:
        if line.startswith("--- ") and old_path_raw is None:
            old_path_raw = line[4:].strip()
        elif line.startswith("+++ ") and new_path_raw is None:
            new_path_raw = line[4:].strip()
            break

    if not old_path_raw or not new_path_raw:
        return ValidationResult(valid=False, errors=["Missing unified diff header (--- and +++)"])

    old_clean = _clean_diff_path(old_path_raw)
    new_clean = _clean_diff_path(new_path_raw)

    target_candidate = new_clean if new_clean != "/dev/null" else old_clean
    if not target_candidate or target_candidate == "/dev/null":
        return ValidationResult(valid=False, errors=["Invalid diff target path"])

    # 4. Check for absolute paths
    if (
        target_candidate.startswith("/")
        or target_candidate.startswith("\\")
        or re.match(r"^[A-Za-z]:", target_candidate)
    ):
        errors.append(f"Absolute paths forbidden: {target_candidate}")

    # 5. Check for directory traversal
    path_parts = Path(target_candidate).parts
    if ".." in path_parts or any(p.startswith("..") for p in path_parts):
        errors.append(f"Directory traversal forbidden: {target_candidate}")

    # 6. Check forbidden file patterns
    for pattern in FORBIDDEN_FILE_PATTERNS:
        if re.search(pattern, target_candidate, re.IGNORECASE):
            # Only modern-app/src is allowed; make sure forbidden words aren't touched
            errors.append(f"Target matches forbidden path pattern '{pattern}': {target_candidate}")
            break

    # 7. Normalize target within modern-app/src
    # The diff might specify "modern-app/src/invoice.php" or "src/invoice.php" or "invoice.php"
    norm_path = target_candidate
    if norm_path.startswith("modern-app/"):
        norm_path = norm_path[len("modern-app/") :]
    if not norm_path.startswith("src/"):
        norm_path = "src/" + norm_path

    expected_file_rel = Path("modern-app") / norm_path
    resolved_full = (root_dir / expected_file_rel).resolve()
    allowed_boundary = (root_dir / "modern-app" / "src").resolve()

    # Canonical path boundary containment check
    try:
        resolved_full.relative_to(allowed_boundary)
    except ValueError:
        errors.append(f"Target path {resolved_full} escapes permitted boundary {allowed_boundary}")

    # File extension check
    if resolved_full.suffix.lower() != ".php":
        errors.append(f"Forbidden file extension '{resolved_full.suffix}'. Only .php files permitted.")

    # Target must already exist (no arbitrary file creation)
    if not resolved_full.exists():
        errors.append(f"Target file does not exist: {expected_file_rel}")

    # Symlink check on file and parent directory
    try:
        if resolved_full.is_symlink():
            errors.append(f"Target file is a symbolic link: {expected_file_rel}")
        for parent in resolved_full.parents:
            if parent == root_dir.resolve():
                break
            if parent.is_symlink():
                errors.append(f"Parent directory {parent} is a symbolic link")
                break
    except OSError as e:
        errors.append(f"Filesystem security check failed: {e}")

    # 8. Validate hunk syntax
    hunk_header_regex = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    hunk_count = 0
    lines_added = 0
    lines_removed = 0
    in_hunk = False

    for line in lines:
        if line.startswith("@@"):
            match = hunk_header_regex.match(line)
            if not match:
                errors.append(f"Malformed hunk header: {line}")
            else:
                hunk_count += 1
                in_hunk = True
        elif in_hunk:
            if line.startswith("+"):
                lines_added += 1
            elif line.startswith("-"):
                lines_removed += 1
            elif line.startswith(" ") or line.startswith("\\"):
                pass
            elif line.startswith("---") or line.startswith("+++"):
                pass
            else:
                errors.append(f"Invalid character at start of diff line: {line[:30]!r}")

    if hunk_count == 0:
        errors.append("Patch contains no valid hunks (missing @@ header)")

    if errors:
        return ValidationResult(valid=False, errors=errors)

    return ValidationResult(
        valid=True,
        target_rel_path=str(expected_file_rel.as_posix()),
        hunk_count=hunk_count,
        lines_added=lines_added,
        lines_removed=lines_removed,
    )
