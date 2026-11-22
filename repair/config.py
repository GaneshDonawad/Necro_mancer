"""Configuration and cost budgeting for Necromancer AI Repair.

Free-Tier First Architecture:
- Primary Provider: Google Gemini (gemini-2.0-flash)
- Backup Provider: Groq (llama-3.3-70b-versatile) via OpenAI-compatible endpoint
- Automatic Fallback: Swaps to Groq if Gemini hits rate limits (429), timeouts, or errors.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any

# Standard pricing per 1,000,000 tokens (USD)
PRICING_TABLE: Dict[str, Dict[str, float]] = {
    # Google Gemini (Free tier eligible Flash / Flash-Lite models)
    "gemini-3.8-flash": {"input": 0.10, "output": 0.40},
    "gemini-3.6-flash": {"input": 0.10, "output": 0.40},
    "gemini-3.5-flash-lite": {"input": 0.05, "output": 0.20},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.00},
    # Groq (Free tier supported models)
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "openai/gpt-oss-120b": {"input": 0.15, "output": 0.60},
    "openai/gpt-oss-20b": {"input": 0.05, "output": 0.10},
    "qwen/qwen3.8-27b": {"input": 0.20, "output": 0.20},
    "mixtral-8x7b-32768": {"input": 0.24, "output": 0.24},
    # Anthropic
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    # Fallback conservative default
    "default": {"input": 0.50, "output": 1.50},
}


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculates approximate cost in USD for given token usage."""
    pricing = PRICING_TABLE.get(model.lower())
    if not pricing:
        for key, p in PRICING_TABLE.items():
            if key in model.lower():
                pricing = p
                break
    if not pricing:
        pricing = PRICING_TABLE["default"]

    input_cost = (prompt_tokens / 1_000_000.0) * pricing["input"]
    output_cost = (completion_tokens / 1_000_000.0) * pricing["output"]
    return round(input_cost + output_cost, 6)


@dataclass
class RepairConfig:
    """Configuration for AI repair execution."""

    provider: str = "gemini"
    model: str = "gemini-3.8-flash"
    api_key: str = ""
    base_url: str = ""
    backup_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    enable_fallback: bool = True
    max_attempts: int = 3
    max_cost_usd: float = 0.25
    timeout_seconds: int = 90
    root_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parents[1])

    @classmethod
    def from_env(cls, root_dir: Path = None) -> "RepairConfig":
        """Loads configuration from environment variables and local .env file."""
        if root_dir is None:
            root_dir = Path(__file__).resolve().parents[1]

        # 1. Load from .env if present (zero external dependencies, safe parsing)
        env_vars = dict(os.environ)
        env_file = root_dir / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k not in env_vars or not env_vars[k]:
                    env_vars[k] = v

        # 2. Extract provider and specific keys
        gemini_key = env_vars.get("GEMINI_API_KEY", "").strip() or env_vars.get("GOOGLE_API_KEY", "").strip()
        groq_key = env_vars.get("GROQ_API_KEY", "").strip()
        general_key = env_vars.get("NECROMANCER_LLM_API_KEY", "").strip()

        provider = env_vars.get("NECROMANCER_LLM_PROVIDER", "").strip().lower()
        model = env_vars.get("NECROMANCER_LLM_MODEL", "").strip()
        base_url = env_vars.get("NECROMANCER_LLM_BASE_URL", "").strip()

        groq_model = env_vars.get("NECROMANCER_GROQ_MODEL", "llama-3.3-70b-versatile").strip()
        enable_fallback = env_vars.get("NECROMANCER_ENABLE_FALLBACK", "true").lower() in ("true", "1", "yes")

        # 3. Provider auto-detection (Gemini primary, Groq backup)
        if not provider:
            if gemini_key:
                provider = "gemini"
            elif groq_key:
                provider = "groq"
            elif env_vars.get("OPENAI_API_KEY"):
                provider = "openai"
            elif env_vars.get("ANTHROPIC_API_KEY"):
                provider = "anthropic"
            else:
                provider = "gemini"  # Default intended free-tier provider

        # 4. API Key resolution for selected provider
        api_key = general_key
        if not api_key:
            if provider == "gemini":
                api_key = gemini_key
            elif provider == "groq":
                api_key = groq_key
            elif provider == "openai":
                api_key = env_vars.get("OPENAI_API_KEY", "").strip()
            elif provider == "anthropic":
                api_key = env_vars.get("ANTHROPIC_API_KEY", "").strip()

        # 5. Default model resolution based on provider (strictly free-tier models for Gemini/Groq)
        if not model:
            if provider == "gemini":
                model = "gemini-2.5-flash"
            elif provider == "groq":
                model = groq_model
            elif provider == "openai":
                model = "gpt-4o"
            elif provider == "anthropic":
                model = "claude-3-5-sonnet-20241022"
            else:
                model = "mock-repair"

        # 6. Safety and cost limits
        try:
            max_attempts = int(env_vars.get("NECROMANCER_MAX_REPAIR_ATTEMPTS", "3"))
        except ValueError:
            max_attempts = 3

        try:
            max_cost_usd = float(env_vars.get("NECROMANCER_MAX_REPAIR_COST_USD", "0.25"))
        except ValueError:
            max_cost_usd = 0.25

        try:
            timeout_seconds = int(env_vars.get("NECROMANCER_TIMEOUT_SECONDS", "90"))
        except ValueError:
            timeout_seconds = 90

        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            backup_provider="groq",
            groq_api_key=groq_key,
            groq_model=groq_model,
            enable_fallback=enable_fallback,
            max_attempts=max_attempts,
            max_cost_usd=max_cost_usd,
            timeout_seconds=timeout_seconds,
            root_dir=root_dir,
        )
