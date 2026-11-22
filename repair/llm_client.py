"""Multi-provider LLM client for Necromancer AI Repair.

Free-Tier First Architecture:
- Google Gemini (gemini-2.0-flash) as Primary Provider
- Groq (llama-3.3-70b-versatile via OpenAI-compatible endpoint) as Backup Provider
- Automatic FallbackClient: Seamlessly falls back from Gemini to Groq on rate limits or errors
- Zero external pip dependencies: built strictly on Python's urllib.request
- MockClient: Deterministic, configurable responses for unit tests and offline CI
"""

import abc
import hashlib
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from repair.config import RepairConfig, calculate_cost


@dataclass
class LLMResponse:
    """Standardized response from LLM."""

    patch: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    model: str
    provider: str
    raw_response: str
    error: Optional[str] = None
    response_id: Optional[str] = None
    api_response_sha256: Optional[str] = None


class BaseLLMClient(abc.ABC):
    """Abstract base class for repair LLM clients."""

    def __init__(self, config: RepairConfig):
        self.config = config

    @abc.abstractmethod
    def generate_patch(self, prompt: str) -> LLMResponse:
        """Sends the repair prompt to the LLM and returns the structured response."""
        pass


def extract_diff(text: str) -> str:
    """Extracts unified diff patch from markdown or raw text response."""
    # Look for ```diff ... ``` or ```patch ... ``` code blocks
    pattern = r"```(?:diff|patch)?\s*\n(---.*?\n\+\+\+.*?\n@@[\s\S]*?)```"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()

    # Look for raw unified diff starting with --- and +++
    lines = text.splitlines()
    diff_lines = []
    recording = False
    for line in lines:
        if line.startswith("--- "):
            recording = True
        if recording:
            diff_lines.append(line)

    if diff_lines:
        return "\n".join(diff_lines).strip()

    return text.strip()


class GeminiClient(BaseLLMClient):
    """Client for Google Gemini models (Free-Tier Eligible)."""

    def generate_patch(self, prompt: str) -> LLMResponse:
        if not self.config.api_key:
            raise ValueError("Gemini API key is required (set GEMINI_API_KEY in .env)")

        # Use header authentication for security so key is never in the URL
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.model}:generateContent"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "You are an expert PHP systems engineer specializing in PHP 5.6 to PHP 8.3 migration. "
                            "Fix the behavioral regression between PHP 5.6 and PHP 8.3. "
                            "Output ONLY a valid unified diff patch for modern-app/src/invoice.php inside a ```diff code block. "
                            "Do NOT include conversational filler or explanations."
                        )
                    }
                ]
            },
            "generationConfig": {"temperature": 0.0},
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.config.api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Necromancer/1.0",
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            # Strip key if it appears anywhere in error
            if self.config.api_key and self.config.api_key in err_body:
                err_body = err_body.replace(self.config.api_key, "[REDACTED]")
            raise RuntimeError(f"Gemini API error (status {e.code}): {err_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Gemini connection error: {e.reason}")

        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        raw_text = "".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)

        cost = calculate_cost(self.config.model, prompt_tokens, completion_tokens)
        patch = extract_diff(raw_text)

        return LLMResponse(
            patch=patch,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            model=data.get("modelVersion", self.config.model),
            provider="gemini",
            raw_response=raw_text,
            response_id=data.get("responseId"),
            api_response_sha256=hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest(),
        )


class GroqClient(BaseLLMClient):
    """Client for Groq's fast inference API using OpenAI-compatible interface (Free-Tier Eligible)."""

    def generate_patch(self, prompt: str) -> LLMResponse:
        if not self.config.api_key:
            raise ValueError("Groq API key is required (set GROQ_API_KEY in .env)")

        endpoint = self.config.base_url or "https://api.groq.com/openai/v1/chat/completions"

        payload = {
            "model": self.config.model,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert PHP systems engineer specializing in PHP 5.6 to PHP 8.3 migration. "
                        "Fix the behavioral regression between PHP 5.6 and PHP 8.3. "
                        "Output ONLY a valid unified diff patch for modern-app/src/invoice.php inside a ```diff code block. "
                        "Do NOT include explanations."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Necromancer/1.0",
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            if self.config.api_key and self.config.api_key in err_body:
                err_body = err_body.replace(self.config.api_key, "[REDACTED]")
            raise RuntimeError(f"Groq API error (status {e.code}): {err_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Groq network connection error: {e.reason}")

        raw_text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        cost = calculate_cost(self.config.model, prompt_tokens, completion_tokens)
        patch = extract_diff(raw_text)

        return LLMResponse(
            patch=patch,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            model=self.config.model,
            provider="groq",
            raw_response=raw_text,
        )


class FallbackClient(BaseLLMClient):
    """Orchestrates seamless automatic fallback from Gemini to Groq on free-tier rate limits or errors."""

    def __init__(self, primary: BaseLLMClient, backup: BaseLLMClient, config: RepairConfig):
        super().__init__(config)
        self.primary = primary
        self.backup = backup

    def generate_patch(self, prompt: str) -> LLMResponse:
        try:
            return self.primary.generate_patch(prompt)
        except Exception as e:
            err_msg = str(e)
            if self.primary.config.api_key and self.primary.config.api_key in err_msg:
                err_msg = err_msg.replace(self.primary.config.api_key, "[REDACTED]")

            print(
                f"\n[AI-PROVIDER-FALLBACK] Primary provider '{self.primary.config.provider}' ({self.primary.config.model}) unavailable:"
            )
            print(f"  Reason: {err_msg[:120]}")
            print(
                f"[AI-PROVIDER-FALLBACK] Seamlessly falling back to backup provider '{self.backup.config.provider}' ({self.backup.config.model})...\n"
            )

            try:
                resp = self.backup.generate_patch(prompt)
                return resp
            except Exception as backup_err:
                b_msg = str(backup_err)
                if self.backup.config.api_key and self.backup.config.api_key in b_msg:
                    b_msg = b_msg.replace(self.backup.config.api_key, "[REDACTED]")
                raise RuntimeError(
                    f"Both primary provider '{self.primary.config.provider}' and backup "
                    f"provider '{self.backup.config.provider}' failed.\n"
                    f"Primary error: {err_msg[:100]}\nBackup error: {b_msg[:100]}"
                )


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic Claude models."""

    def generate_patch(self, prompt: str) -> LLMResponse:
        if not self.config.api_key:
            raise ValueError("Anthropic API key is required (set ANTHROPIC_API_KEY in .env)")

        base_url = self.config.base_url or "https://api.anthropic.com"
        endpoint = f"{base_url.rstrip('/')}/v1/messages"

        payload = {
            "model": self.config.model,
            "max_tokens": 2048,
            "temperature": 0.0,
            "system": (
                "You are an expert PHP systems engineer specializing in PHP 5.6 to PHP 8.3 migration. "
                "Output ONLY a valid unified diff patch for modern-app/src/invoice.php inside a ```diff code block. "
                "Do NOT include conversational filler."
            ),
            "messages": [{"role": "user", "content": prompt}],
        }

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            if self.config.api_key and self.config.api_key in err_body:
                err_body = err_body.replace(self.config.api_key, "[REDACTED]")
            raise RuntimeError(f"Anthropic API error (status {e.code}): {err_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Anthropic network connection failed: {e.reason}")

        content_blocks = data.get("content", [])
        raw_text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
        usage = data.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)

        cost = calculate_cost(self.config.model, prompt_tokens, completion_tokens)
        patch = extract_diff(raw_text)

        return LLMResponse(
            patch=patch,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            model=self.config.model,
            provider="anthropic",
            raw_response=raw_text,
        )


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI and compatible models."""

    def generate_patch(self, prompt: str) -> LLMResponse:
        if not self.config.api_key:
            raise ValueError("OpenAI API key is required (set OPENAI_API_KEY in .env)")

        base_url = self.config.base_url or "https://api.openai.com/v1"
        endpoint = f"{base_url.rstrip('/')}/chat/completions"

        payload = {
            "model": self.config.model,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert PHP engineer. "
                        "Respond ONLY with a unified diff patch for modern-app/src/invoice.php inside a ```diff code block. "
                        "Do not include explanation."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Necromancer/1.0",
        }

        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            if self.config.api_key and self.config.api_key in err_body:
                err_body = err_body.replace(self.config.api_key, "[REDACTED]")
            raise RuntimeError(f"OpenAI API error (status {e.code}): {err_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"OpenAI connection error: {e.reason}")

        raw_text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        cost = calculate_cost(self.config.model, prompt_tokens, completion_tokens)
        patch = extract_diff(raw_text)

        return LLMResponse(
            patch=patch,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            model=self.config.model,
            provider="openai",
            raw_response=raw_text,
        )


class MockClient(BaseLLMClient):
    """Deterministic mock client for testing and offline verification."""

    CORRECT_PATCH = (
        "--- a/modern-app/src/invoice.php\n"
        "+++ b/modern-app/src/invoice.php\n"
        "@@ -14,3 +14,3 @@\n"
        " }\n"
        "-$is_walk_in = ($customer == 0);\n"
        "+$is_walk_in = ($customer === 0 || $customer === '0' || (!is_numeric($customer) && is_string($customer)));\n"
        " $handling = $is_walk_in ? 0 : 50;\n"
    )

    def __init__(self, config: RepairConfig, responses=None):
        super().__init__(config)
        self.responses = responses or [self.CORRECT_PATCH]
        self.call_count = 0

    def generate_patch(self, prompt: str) -> LLMResponse:
        idx = min(self.call_count, len(self.responses) - 1)
        resp_text = self.responses[idx]
        self.call_count += 1

        if resp_text == "__TIMEOUT__":
            raise TimeoutError("Mock LLM request timed out after 30s")
        if resp_text == "__ERROR__":
            raise RuntimeError("Mock LLM service unavailable (HTTP 503)")
        if resp_text == "__RATE_LIMIT__":
            raise RuntimeError("Mock LLM rate limit reached (HTTP 429 Too Many Requests)")

        patch = extract_diff(resp_text)
        return LLMResponse(
            patch=patch,
            prompt_tokens=320,
            completion_tokens=95,
            cost_usd=0.0001,
            model=self.config.model,
            provider=self.config.provider,
            raw_response=resp_text,
        )


def get_llm_client(config: RepairConfig, mock_responses=None) -> BaseLLMClient:
    """Factory to instantiate the appropriate LLM client with automatic fallback support."""
    provider = config.provider.lower()

    if provider == "mock":
        return MockClient(config, responses=mock_responses)
    elif provider == "gemini":
        gemini_client = GeminiClient(config)
        # Automatic fallback to Groq if groq_api_key is available
        if config.enable_fallback and config.groq_api_key:
            groq_config = RepairConfig(
                provider="groq",
                model=config.groq_model,
                api_key=config.groq_api_key,
                timeout_seconds=config.timeout_seconds,
                root_dir=config.root_dir,
            )
            groq_client = GroqClient(groq_config)
            return FallbackClient(primary=gemini_client, backup=groq_client, config=config)
        return gemini_client
    elif provider == "groq":
        return GroqClient(config)
    elif provider == "anthropic":
        return AnthropicClient(config)
    elif provider == "openai":
        return OpenAIClient(config)
    else:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")
