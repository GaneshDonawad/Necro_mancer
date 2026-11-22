"""Structured JSON report generator for Necromancer AI Repair."""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional


@dataclass
class AttemptRecord:
    """Audit log of a single repair attempt."""

    attempt_number: int
    timestamp: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    duration_seconds: float
    patch_preview: str
    validation_passed: bool
    validation_errors: List[str] = field(default_factory=list)
    visible_tests_passed: int = 0
    visible_tests_total: int = 0
    status: str = "PENDING"
    failing_scenarios: List[str] = field(default_factory=list)
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    response_id: Optional[str] = None
    api_response_sha256: Optional[str] = None


@dataclass
class RepairReport:
    """Comprehensive machine-readable repair run audit."""

    run_id: str
    timestamp: str
    final_status: str
    llm_provider: str
    llm_model: str
    initial_regressions: int
    attempts_used: int
    max_attempts: int
    total_cost_usd: float
    total_tokens: int
    evidence_integrity_verified: bool
    attempts: List[AttemptRecord] = field(default_factory=list)
    heldout_verification: Optional[Dict[str, Any]] = None
    applied_patch: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def write_json(self, path: Path):
        data = self.to_dict()
        # Atomic write
        temp_path = path.with_suffix(".tmp_rep")
        temp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(path)


class RepairReporter:
    """Constructs and persists the repair audit report."""

    def __init__(self, provider: str, model: str, max_attempts: int, initial_regressions: int):
        self.report = RepairReport(
            run_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            final_status="INITIALIZING",
            llm_provider=provider,
            llm_model=model,
            initial_regressions=initial_regressions,
            attempts_used=0,
            max_attempts=max_attempts,
            total_cost_usd=0.0,
            total_tokens=0,
            evidence_integrity_verified=False,
        )
        self.response_provenance = {}

    def add_attempt(self, attempt: AttemptRecord):
        for key, value in self.response_provenance.items():
            setattr(attempt, key, value)
        self.report.attempts.append(attempt)
        self.report.attempts_used = len(self.report.attempts)
        self.report.total_cost_usd = round(
            sum(a.cost_usd for a in self.report.attempts), 6
        )
        self.report.total_tokens = sum(
            a.prompt_tokens + a.completion_tokens for a in self.report.attempts
        )

    def set_heldout_result(self, passed: int, total: int, success: bool):
        # NOTE: Hidden scenario details are NEVER stored here to preserve isolation
        self.report.heldout_verification = {
            "passed": passed,
            "total": total,
            "success": success,
        }

    def finalize(self, final_status: str, integrity_verified: bool, applied_patch: Optional[str] = None):
        self.report.final_status = final_status
        self.report.evidence_integrity_verified = integrity_verified
        if applied_patch:
            self.report.applied_patch = applied_patch

    def save(self, output_path: Path):
        # Preserve each audit under its UUID before updating the latest pointer.
        # Raw local history is deliberately excluded from Git and deployment.
        history = output_path.parent / ".local-runs" / self.report.run_id
        history.mkdir(parents=True, exist_ok=True)
        self.report.write_json(history / "repair-report.json")
        self.report.write_json(output_path)
