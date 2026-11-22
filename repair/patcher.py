"""Safe unified diff patch applicator written in pure Python.

Applies hunks accurately without invoking external shell or patch utilities.
Ensures context matches before applying, and performs atomic file writes.
"""

import re
from pathlib import Path
from typing import List, Tuple


class PatchApplicationError(Exception):
    """Raised when patch application fails."""
    pass


def apply_unified_diff(original_content: str, patch_text: str) -> str:
    """Applies a unified diff patch string to original file content."""
    original_lines = original_content.splitlines(keepends=True)
    patch_lines = patch_text.splitlines()

    hunk_regex = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    # Split patch into hunks
    hunks: List[Tuple[int, int, List[str]]] = []
    current_hunk_lines = None
    current_old_start = 0
    current_old_count = 1

    for line in patch_lines:
        match = hunk_regex.match(line)
        if match:
            if current_hunk_lines is not None:
                hunks.append((current_old_start, current_old_count, current_hunk_lines))
            current_old_start = int(match.group(1))
            current_old_count = int(match.group(2)) if match.group(2) else 1
            current_hunk_lines = []
        elif current_hunk_lines is not None:
            current_hunk_lines.append(line)

    if current_hunk_lines is not None:
        hunks.append((current_old_start, current_old_count, current_hunk_lines))

    if not hunks:
        raise PatchApplicationError("No valid hunks found in patch")

    # Apply hunks in order
    result_lines = list(original_lines)
    # Track line offset caused by additions/deletions in previous hunks
    offset = 0

    for old_start, old_count, hunk_lines in hunks:
        # 1-based to 0-based index
        target_idx = (old_start - 1) + offset

        # Separate expected context/removals and replacements
        expected_old = []
        replacement_new = []

        for hline in hunk_lines:
            if hline.startswith(" "):
                line_text = hline[1:]
                expected_old.append(line_text)
                replacement_new.append(line_text)
            elif hline.startswith("-"):
                expected_old.append(hline[1:])
            elif hline.startswith("+"):
                replacement_new.append(hline[1:])
            elif hline.startswith("\\"):
                # "\ No newline at end of file"
                pass
            else:
                raise PatchApplicationError(f"Unexpected line prefix in hunk: {hline[:30]!r}")

        # Check if expected lines match original content at target_idx
        # Try exact target_idx first; if not matching, search nearby within +/- 5 lines
        match_idx = None
        search_radius = 5
        candidates = [target_idx] + [
            target_idx + d for r in range(1, search_radius + 1) for d in (-r, r)
        ]

        for cand in candidates:
            if cand < 0 or cand + len(expected_old) > len(result_lines):
                continue
            # Compare lines (strip line endings for flexible newline matching)
            matches = True
            for i, exp in enumerate(expected_old):
                actual_line = result_lines[cand + i].rstrip("\r\n")
                if actual_line != exp.rstrip("\r\n"):
                    matches = False
                    break
            if matches:
                match_idx = cand
                break

        if match_idx is None:
            raise PatchApplicationError(
                f"Patch hunk failed to match context at line {old_start} (attempted index {target_idx})"
            )

        # Detect newline convention
        newline = "\n"
        if result_lines and result_lines[0].endswith("\r\n"):
            newline = "\r\n"

        # Format replacements with correct newline
        formatted_replacements = [
            (r if r.endswith("\n") or r.endswith("\r\n") else r + newline)
            for r in replacement_new
        ]

        # Splice into result
        result_lines[match_idx : match_idx + len(expected_old)] = formatted_replacements
        # Update offset
        offset += len(replacement_new) - len(expected_old)

    return "".join(result_lines)


def apply_patch_to_workspace(workspace_dir: Path, target_rel_path: str, patch_text: str) -> Path:
    """Applies patch to target file inside workspace atomically."""
    # Normalize relative path to locate inside workspace
    rel = Path(target_rel_path)
    # If path starts with modern-app, strip it since workspace root contains modern-app contents
    if rel.parts and rel.parts[0] == "modern-app":
        rel = Path(*rel.parts[1:])

    target_file = (workspace_dir / rel).resolve()
    if not target_file.exists():
        raise PatchApplicationError(f"Target file does not exist in workspace: {target_file}")

    original_content = target_file.read_text(encoding="utf-8")
    new_content = apply_unified_diff(original_content, patch_text)

    # Atomic write via temp file
    temp_target = target_file.with_suffix(".tmp_patch")
    temp_target.write_text(new_content, encoding="utf-8")
    temp_target.replace(target_file)

    return target_file
