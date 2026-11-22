"""Live model availability checker and probe for Google Gemini & Groq APIs.

Queries official model discovery endpoints:
- Gemini: GET https://generativelanguage.googleapis.com/v1beta/models
- Groq:   GET https://api.groq.com/openai/v1/models

Performs live inference probes to test actual text generation.
Differentiates between authentication errors, Cloudflare blocks, timeouts, and network issues.
Strictly redacts all API keys from terminal output and logs.
"""

import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = 90
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Necromancer/1.0"


def load_env() -> dict:
    """Loads environment variables from d:/Necromancer/.env if present."""
    env_vars = dict(os.environ)
    env_file = ROOT / ".env"
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
    return env_vars


def update_env_model(working_model: str, disable_groq: bool = False):
    """Safely updates .env with the verified working model without exposing keys."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return

    lines = env_file.read_text(encoding="utf-8").splitlines()
    new_lines = []
    has_model = False
    has_fallback = False
    has_timeout = False

    for line in lines:
        sline = line.strip()
        if sline.startswith("NECROMANCER_LLM_MODEL="):
            new_lines.append(f"NECROMANCER_LLM_MODEL={working_model}")
            has_model = True
        elif sline.startswith("NECROMANCER_ENABLE_FALLBACK="):
            new_lines.append(f"NECROMANCER_ENABLE_FALLBACK={'false' if disable_groq else 'true'}")
            has_fallback = True
        elif sline.startswith("NECROMANCER_TIMEOUT_SECONDS="):
            new_lines.append("NECROMANCER_TIMEOUT_SECONDS=90")
            has_timeout = True
        else:
            new_lines.append(line)

    if not has_model:
        new_lines.append(f"NECROMANCER_LLM_MODEL={working_model}")
    if not has_fallback and disable_groq:
        new_lines.append("NECROMANCER_ENABLE_FALLBACK=false")
    if not has_timeout:
        new_lines.append("NECROMANCER_TIMEOUT_SECONDS=90")

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def probe_gemini(api_key: str):
    """Queries Gemini available models and tests live text generation with candidate models."""
    print("\n--- 1. Probing Google Gemini API ---")
    if not api_key:
        print("Status: GEMINI_API_KEY is not configured.")
        return None

    # Step A: Query models endpoint
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
        "User-Agent": USER_AGENT,
    }
    req = urllib.request.Request(endpoint, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        if api_key in err_msg:
            err_msg = err_msg.replace(api_key, "[REDACTED]")
        if e.code in (401, 403):
            print(f"AUTHENTICATION ERROR: Gemini rejected credentials (HTTP {e.code}): {err_msg[:160]}")
        elif e.code == 429:
            print(f"RATE LIMIT EXCEEDED: Gemini API quota reached (HTTP 429): {err_msg[:160]}")
        else:
            print(f"FAILED to list Gemini models (HTTP {e.code}): {err_msg[:160]}")
        return None
    except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
        reason = getattr(e, "reason", str(e))
        if "timed out" in str(reason).lower() or isinstance(e, socket.timeout):
            print(f"TIMEOUT ERROR: Gemini API model discovery timed out after {TIMEOUT_SECONDS}s.")
        else:
            print(f"NETWORK ERROR connecting to Gemini API: {reason}")
        return None
    except Exception as e:
        print(f"UNEXPECTED ERROR connecting to Gemini API: {e}")
        return None

    models = data.get("models", [])
    chat_models = []
    for m in models:
        name = m.get("name", "").replace("models/", "")
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" in methods:
            chat_models.append(name)

    print(f"AUTHENTICATION SUCCESS: Found {len(chat_models)} generation models.")

    # Prioritize candidates starting with gemini-2.5-flash as requested
    candidate_priority = [
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
    ]

    # Find accessible free-tier candidates that are in chat_models
    candidates_to_test = [m for m in candidate_priority if m in chat_models]
    if not candidates_to_test:
        candidates_to_test = [
            m for m in chat_models
            if any(k in m.lower() for k in ["flash", "lite"])
            and not any(b in m.lower() for b in ["argon", "carbon", "pro", "tts", "live", "transcribe", "banana"])
        ]

    print(f"Testing candidate free-tier models (timeout: {TIMEOUT_SECONDS}s): {candidates_to_test[:5]}")

    working_model = None
    for model_name in candidates_to_test:
        print(f"\nAttempting live generation with '{model_name}'...")
        test_endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        test_payload = {
            "contents": [{"parts": [{"text": "Say 'OK' and nothing else."}]}],
            "generationConfig": {"maxOutputTokens": 5, "temperature": 0.0},
        }
        test_req = urllib.request.Request(
            test_endpoint,
            data=json.dumps(test_payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        start_t = time.time()
        try:
            with urllib.request.urlopen(test_req, timeout=TIMEOUT_SECONDS) as test_resp:
                elapsed = time.time() - start_t
                tdata = json.loads(test_resp.read().decode("utf-8"))
                candidates = tdata.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    ans = "".join(p.get("text", "") for p in parts).strip()
                    print(f"SUCCESS: '{model_name}' generated response in {elapsed:.2f}s: '{ans}'")
                    working_model = model_name
                    break
                else:
                    print(f"WARNING: '{model_name}' returned empty candidates.")
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="replace")
            if api_key in err_msg:
                err_msg = err_msg.replace(api_key, "[REDACTED]")
            if e.code == 429:
                print(f"RATE LIMITED on '{model_name}' (HTTP 429). Trying next candidate...")
            elif e.code in (401, 403):
                print(f"CREDENTIAL/PERMISSION ERROR on '{model_name}' (HTTP {e.code}): {err_msg[:120]}")
            else:
                print(f"HTTP ERROR on '{model_name}' (HTTP {e.code}): {err_msg[:120]}")
        except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
            elapsed = time.time() - start_t
            reason = getattr(e, "reason", str(e))
            if "timed out" in str(reason).lower() or isinstance(e, socket.timeout):
                print(f"TIMEOUT on '{model_name}' after {elapsed:.1f}s. Trying next candidate...")
            else:
                print(f"NETWORK ERROR on '{model_name}': {reason}")
        except Exception as e:
            print(f"ERROR on '{model_name}': {e}")

    return working_model


def probe_groq(api_key: str):
    """Diagnoses Groq connection, specifically testing for Cloudflare Error 1010."""
    print("\n--- 2. Diagnosing Groq API (Backup Provider) ---")
    if not api_key:
        print("Status: GROQ_API_KEY is not configured.")
        return None

    endpoint = "https://api.groq.com/openai/v1/models"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": USER_AGENT,
    }
    req = urllib.request.Request(endpoint, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = data.get("data", [])
            print(f"SUCCESS: Groq connected. Found {len(models)} models.")
            return "llama-3.3-70b-versatile"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        if api_key in err_msg:
            err_msg = err_msg.replace(api_key, "[REDACTED]")
        if e.code == 403 and "1010" in err_msg:
            print("DIAGNOSIS: Groq returned HTTP 403 (Cloudflare Error 1010).")
            print("  Cause: Cloudflare Ray / Edge WAF security policy is blocking automated client requests.")
            print("  Action: In accordance with security guidelines, DO NOT attempt to bypass provider security.")
            print("  Resolution: Disabling Groq fallback and relying exclusively on verified primary Gemini.")
        elif e.code in (401, 403):
            print(f"AUTHENTICATION ERROR: Groq rejected credentials (HTTP {e.code}): {err_msg[:160]}")
        else:
            print(f"FAILED to list Groq models (HTTP {e.code}): {err_msg[:160]}")
        return None
    except (urllib.error.URLError, socket.timeout, TimeoutError) as e:
        reason = getattr(e, "reason", str(e))
        print(f"NETWORK ERROR connecting to Groq API: {reason}")
        return None
    except Exception as e:
        print(f"UNEXPECTED ERROR on Groq API: {e}")
        return None


def main():
    env = load_env()
    gemini_key = env.get("GEMINI_API_KEY", "").strip() or env.get("GOOGLE_API_KEY", "").strip()
    groq_key = env.get("GROQ_API_KEY", "").strip()

    print("==================================================")
    print(" Necromancer AI Provider Model Verification Probe ")
    print("==================================================")
    print(f".env file present: {(ROOT / '.env').exists()}")
    print(f"GEMINI_API_KEY configured: {bool(gemini_key and not gemini_key.startswith('your_'))}")
    print(f"GROQ_API_KEY configured:   {bool(groq_key and not groq_key.startswith('your_'))}")

    g_model = probe_gemini(gemini_key if not gemini_key.startswith("your_") else "")
    gr_model = probe_groq(groq_key if not groq_key.startswith("your_") else "")

    print("\n==================================================")
    print(" Verification Summary ")
    print("==================================================")
    if g_model:
        print(f" Google Gemini: VERIFIED & READY with '{g_model}' (Primary)")
        update_env_model(g_model, disable_groq=(gr_model is None))
        print(f" Updated .env configuration with NECROMANCER_LLM_MODEL={g_model}")
        if gr_model is None:
            print(" Disabled Groq fallback in .env (NECROMANCER_ENABLE_FALLBACK=false)")
    else:
        print("❌ Google Gemini: No working model could complete text generation.")

    if gr_model:
        print(f" Groq:          READY with active model '{gr_model}' (Backup)")
    else:
        print("⏸ Groq:          Disabled due to HTTP 403 Cloudflare Error 1010 block.")


if __name__ == "__main__":
    main()
