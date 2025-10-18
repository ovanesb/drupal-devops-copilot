# copilot/ai/llm.py
from __future__ import annotations
import os
import json
import time
from typing import Optional, Dict, Any, List
import requests

# -----------------------
# Env helpers
# -----------------------
def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v not in (None, "") else default

def is_disabled() -> bool:
    return _env("COPILOT_DISABLE_LLM", "0") == "1"

def _provider_from_env() -> str:
    """
    Provider precedence:
      1) LLM_PROVIDER if set (openai | ollama | openai_compat)
      2) If OPENAI_BASE_URL set -> openai_compat (Ollama/vLLM/OpenRouter-compatible /v1)
      3) If OLLAMA_HOST set -> ollama
      4) If OPENAI_API_KEY set -> openai
      5) default -> ollama
    """
    p = (_env("LLM_PROVIDER") or "").strip().lower()
    if p in ("openai", "ollama", "openai_compat"):
        return p
    if _env("OPENAI_BASE_URL"):
        return "openai_compat"
    if _env("OLLAMA_HOST"):
        return "ollama"
    if _env("OPENAI_API_KEY"):
        return "openai"
    return "ollama"

def _default_model(provider: str) -> str:
    if m := _env("LLM_MODEL"):
        return m
    if provider in ("ollama", "openai_compat"):
        return "qwen2.5-coder:7b-instruct-q4_0"
    return "gpt-4o-mini"

# -----------------------
# Latency/robustness knobs (env-tunable)
# -----------------------
# Overall request timeout (seconds)
REQUEST_TIMEOUT_S = int(float(_env("LLM_REQUEST_TIMEOUT", "120")))
# Retries for transient failures
MAX_RETRIES = int(_env("LLM_MAX_RETRIES", "2"))
BACKOFF_BASE_S = float(_env("LLM_BACKOFF_BASE_S", "2.0"))

# Ollama knobs
OLLAMA_HOST = (_env("OLLAMA_HOST", "http://127.0.0.1:11434") or "").rstrip("/")
OLLAMA_KEEP_ALIVE = _env("OLLAMA_KEEP_ALIVE", "15m")
OLLAMA_NUM_PREDICT = int(_env("OLLAMA_NUM_PREDICT", "600"))   # keep responses short
OLLAMA_NUM_CTX = int(_env("OLLAMA_NUM_CTX", "4096"))          # safe headroom for Qwen 7B
OLLAMA_TEMPERATURE = float(_env("OLLAMA_TEMPERATURE", "0.2"))
OLLAMA_TOP_P = float(_env("OLLAMA_TOP_P", "0.9"))
OLLAMA_TOP_K = int(_env("OLLAMA_TOP_K", "40"))
OLLAMA_REPEAT_PENALTY = float(_env("OLLAMA_REPEAT_PENALTY", "1.1"))

# Prompt trimming
PROMPT_MAX_CHARS = int(_env("LLM_PROMPT_MAX_CHARS", "12000"))  # heuristic budget to avoid ctx overflow

# OpenAI/OpenAI-compat defaults
OPENAI_TEMPERATURE_DEFAULT = float(_env("OPENAI_TEMPERATURE", "0.2"))

# Stop sequences (optional) to encourage concise code blocks
DEFAULT_STOPS: List[str] = [
    "\n```end\n",
    "\nDONE\n",
]

# -----------------------
# Utilities
# -----------------------
def _trim_text(s: str, max_chars: int) -> str:
    if len(s) <= max_chars:
        return s
    # keep head and tail, mark trimmed in the middle
    head = s[: int(max_chars * 0.7)]
    tail = s[-int(max_chars * 0.2):]
    return head + "\n\n[...PROMPT TRIMMED...]\n\n" + tail

def _trim_messages(messages: List[Dict[str, str]], max_chars: int) -> List[Dict[str, str]]:
    # Simple heuristic: join contents, trim, then keep roles intact proportionally.
    # For robustness we just trim the last user message first.
    total = sum(len(m.get("content", "")) for m in messages)
    if total <= max_chars:
        return messages
    out = messages.copy()
    # Prefer trimming the user message
    for i in reversed(range(len(out))):
        if out[i].get("role") == "user":
            out[i]["content"] = _trim_text(out[i].get("content", ""), max_chars)
            break
    return out

def _prewarm_ollama(model: str) -> None:
    """Cheap 1-token call to keep model resident on GPU (avoid cold starts)."""
    try:
        requests.post(
            f"{OLLAMA_HOST}/api/generate",
            data=json.dumps({
                "model": model,
                "prompt": "ok",
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": {"num_predict": 1, "temperature": 0}
            }),
            timeout=10,
        )
    except Exception:
        # best-effort only
        pass

# -----------------------
# Main entry point
# -----------------------
def complete(
    *,
    system: Optional[str],
    user: str,
    model: Optional[str] = None,
    temperature: float = OPENAI_TEMPERATURE_DEFAULT,
    provider: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """
    Simple, non-streaming text completion across:
      - openai (real OpenAI)
      - openai_compat (OpenAI-compatible /v1, e.g. Ollama at OPENAI_BASE_URL)
      - ollama (native /api/chat)
    Adds:
      - retries with exponential backoff
      - keep_alive (Ollama)
      - prompt trimming (char heuristic)
      - num_predict/num_ctx for Ollama
      - lower-latency defaults
    """
    if is_disabled():
        raise RuntimeError("LLM disabled via COPILOT_DISABLE_LLM=1")

    prov = (provider or _provider_from_env()).lower()
    mdl = model or _default_model(prov)

    # Assemble & trim messages
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    messages = _trim_messages(messages, PROMPT_MAX_CHARS)

    # Retry loop
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            if prov == "openai":
                base = "https://api.openai.com/v1"
                key = _env("OPENAI_API_KEY")
                if not key:
                    raise RuntimeError("OPENAI_API_KEY not set")
                url = f"{base}/chat/completions"
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload: Dict[str, Any] = {
                    "model": mdl,
                    "messages": messages,
                    "temperature": float(temperature),
                    # Ask for concise outputs
                    "stop": DEFAULT_STOPS or None,
                }
                if max_tokens:
                    payload["max_tokens"] = int(max_tokens)
                r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=REQUEST_TIMEOUT_S)
                if r.status_code != 200:
                    raise RuntimeError(f"OpenAI error {r.status_code}: {r.text}")
                return (r.json().get("choices", [{}])[0].get("message", {}) or {}).get("content", "")

            if prov == "openai_compat":
                base = _env("OPENAI_BASE_URL")
                if not base:
                    raise RuntimeError("OPENAI_BASE_URL not set for openai_compat provider")
                base = base.rstrip("/")
                key = _env("OPENAI_API_KEY", "ollama")  # many compat servers ignore it, but header must exist
                url = f"{base}/chat/completions"
                headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
                payload: Dict[str, Any] = {
                    "model": mdl,
                    "messages": messages,
                    "temperature": float(temperature),
                    "stop": DEFAULT_STOPS or None,
                }
                if max_tokens:
                    payload["max_tokens"] = int(max_tokens)
                r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=REQUEST_TIMEOUT_S)
                if r.status_code != 200:
                    # normalize common 4xx bodies
                    try:
                        j = r.json()
                    except Exception:
                        j = {"raw": r.text}
                    err = j.get("error") or j
                    code = getattr(r, "status_code", "NA")
                    raise RuntimeError(f"OpenAI-compatible error {code}: {json.dumps(err)}")
                data = r.json()
                return (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "")

            # ---- OLLAMA native ----
            # prewarm/keep-alive
            _prewarm_ollama(mdl)

            url = f"{OLLAMA_HOST}/api/chat"
            payload = {
                "model": mdl,
                "messages": messages,
                "stream": False,
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": {
                    "temperature": float(temperature if temperature is not None else OLLAMA_TEMPERATURE),
                    "num_predict": OLLAMA_NUM_PREDICT,
                    "num_ctx": OLLAMA_NUM_CTX,
                    "top_p": OLLAMA_TOP_P,
                    "top_k": OLLAMA_TOP_K,
                    "repeat_penalty": OLLAMA_REPEAT_PENALTY,
                    "stop": DEFAULT_STOPS,
                },
            }
            # If caller provided max_tokens, prefer it
            if max_tokens is not None:
                try:
                    payload["options"]["num_predict"] = int(max_tokens)
                except Exception:
                    pass

            r = requests.post(url, data=json.dumps(payload), timeout=REQUEST_TIMEOUT_S)
            if r.status_code != 200:
                raise RuntimeError(f"Ollama error {r.status_code}: {r.text}")
            return (r.json().get("message", {}) or {}).get("content", "")

        except Exception as e:
            last_exc = e
            if attempt <= MAX_RETRIES:
                # exponential backoff
                time.sleep(BACKOFF_BASE_S * attempt)
                continue
            raise last_exc
