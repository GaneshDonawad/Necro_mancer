"""Necromancer AI Repair Engine package."""

from repair.config import RepairConfig
from repair.validator import validate_patch, ValidationResult
from repair.patcher import apply_patch_to_workspace, PatchApplicationError
from repair.workspace import DisposableWorkspace
from repair.llm_client import get_llm_client, LLMResponse, BaseLLMClient
from repair.reporter import RepairReporter
from repair.runner import run_repair

__all__ = [
    "RepairConfig",
    "validate_patch",
    "ValidationResult",
    "apply_patch_to_workspace",
    "PatchApplicationError",
    "DisposableWorkspace",
    "get_llm_client",
    "LLMResponse",
    "BaseLLMClient",
    "RepairReporter",
    "run_repair",
]
