# server/app.py
from __future__ import annotations
import os
import re
import shlex
import subprocess
from typing import Generator, Iterable, Optional, Tuple, Dict, Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

# ---------- App ----------
app = FastAPI(title="Drupal DevOps Co-Pilot API")

# CORS (Next.js dev on :3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO = os.getenv("COPILOT_REPO_PATH", "./work/drupal-project")

# ---------- LLM resolution (kept for future) ----------
KNOWN_OPENAI = {
    "gpt-4o", "gpt-4o-mini", "o4-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-4"
}
DEFAULT_OPENAI = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")
DEFAULT_OLLAMA = os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5-coder:7b-instruct-q4_0")

def resolve_llm(provider: str | None, model: str | None) -> Tuple[str, str]:
    p = (provider or os.getenv("LLM_PROVIDER") or "openai").strip().lower()
    m = (model or os.getenv("LLM_MODEL") or "").strip()

    def looks_like_ollama(mo: str) -> bool:
        return ":" in mo

    def looks_like_openai(mo: str) -> bool:
        base = mo.split(":")[0]
        return (base in KNOWN_OPENAI) or (":" not in mo)

    if p == "ollama":
        if not m or looks_like_openai(m):
            m = DEFAULT_OLLAMA
        return "ollama", m

    if not m or looks_like_ollama(m):
        m = DEFAULT_OPENAI
    return "openai", m

def _env_with_llm(provider: str | None, model: str | None, disable_llm: bool) -> dict:
    env = os.environ.copy()
    if provider:
        env["LLM_PROVIDER"] = provider
    if model:
        env["LLM_MODEL"] = model
    if disable_llm:
        env["COPILOT_DISABLE_LLM"] = "1"
    else:
        env.pop("COPILOT_DISABLE_LLM", None)
    return env

# ---------- shell helpers ----------
def _stream_cmd(cmd: str | Iterable[str], cwd: Optional[str] = None, env: Optional[dict] = None) -> Generator[bytes, None, None]:
    try:
        if isinstance(cmd, str):
            popen_cmd = cmd
            shell = True
            show = cmd
        else:
            popen_cmd = list(cmd)
            shell = False
            show = " ".join(shlex.quote(x) for x in popen_cmd)

        yield f"$ {show}\n".encode()
        p = subprocess.Popen(
            popen_cmd,
            cwd=cwd or ROOT,
            env=env or os.environ.copy(),
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
        assert p.stdout
        for line in p.stdout:
            yield line.encode()
        rc = p.wait()
        if rc != 0:
            yield f"[error] command exited with {rc}: {show}\n".encode()
    except Exception as e:
        yield f"[error] {_safe_err(e)}\n".encode()

def _capture(cmd: list[str], cwd: Optional[str] = None, env: Optional[dict] = None) -> tuple[int, str]:
    p = subprocess.Popen(cmd, cwd=cwd or ROOT, env=env or os.environ.copy(),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out, _ = p.communicate()
    return p.returncode, out or ""

def _safe_err(e: Exception) -> str:
    return f"{type(e).__name__}: {e}"

# ---------- MR helpers ----------
def _parse_mr_url_from_output(buffer: str) -> Optional[str]:
    m = re.search(r"MR opened:\s*(https?://\S+)", buffer)
    if m:
        return m.group(1)
    m = re.search(r">>> MR:\s*(https?://\S+)", buffer)
    if m:
        return m.group(1)
    return None

# ---------- health ----------
@app.get("/health")
def health():
    return {"ok": True}

# ---------- Plan Preview (no LLM) ----------
@app.get("/plan/preview")
def plan_preview(issue_key: str):
    try:
        from copilot.helpers.jira_helper import (
            get_issue_summary,
            get_issue_description,
            get_issue_acceptance,
        )
        from copilot.agents.prompt_builder import extract_acceptance_criteria_from_text

        summary = (get_issue_summary(issue_key) or "").strip()
        desc_md = (get_issue_description(issue_key) or "").strip()
        ac_md = (get_issue_acceptance(issue_key) or "").strip()

        desc_checks = extract_acceptance_criteria_from_text(desc_md)
        ac_checks = extract_acceptance_criteria_from_text(ac_md)

        suggested = issue_key.lower().replace("-", "_")

        data: Dict[str, Any] = {
            "issue_key": issue_key,
            "summary": summary,
            "description_md": desc_md,
            "acceptance_md": ac_md,
            "description_checklist": desc_checks,
            "acceptance_checklist": ac_checks,
            "suggested_module_name": suggested,
            "suggested_plan": [
                "Create/ensure feature branch from base",
                "Scaffold or patch minimal Drupal 11 module",
                "Open/Update MR and run CI",
                "Deploy to staging",
                "QA verify against AC",
            ],
            "validations": [
                "YAML lint passes",
                "PHPCS passes on changed PHP-like files",
                "PHPStan (if configured) passes",
                "Staging deploy job succeeds",
            ],
            "risks": [
                "Avoid touching vendor/ or core files",
                "Keep diff minimal and focused",
                "Ensure correct core_version_requirement in .info.yml",
            ],
        }
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": _safe_err(e)}, status_code=500)

# ---------- One-shot CLI passthrough ----------
@app.get("/stream/one-shot")
def stream_one_shot(issue_key: str):
    cmd = ["copilot-one-shot", issue_key]

    def gen():
        try:
            yield b"[stream] started\n"
            yield f"--- One-Shot: {' '.join(cmd)}\n".encode()
            for chunk in _stream_cmd(cmd, cwd=ROOT):
                yield chunk
        except Exception as e:
            yield f"[error] {_safe_err(e)}\n".encode()
        finally:
            yield b"[stream] ended (exit 0)\n"

    return StreamingResponse(gen(), media_type="text/plain")

# ---------- NEW: STEP-BY-STEP passthroughs ----------

@app.get("/stream/workflow-cli")
def stream_workflow_cli(issue_key: str):
    """
    Mirrors: copilot-workflow <ISSUE>
    (Relies on .env for repo, project path, labels, draft, etc.)
    """
    cmd = ["copilot-workflow", issue_key]

    def gen():
        try:
            yield b"[stream] started\n"
            yield f"--- Workflow: {' '.join(cmd)}\n".encode()
            for chunk in _stream_cmd(cmd, cwd=ROOT):
                yield chunk
        except Exception as e:
            yield f"[error] {_safe_err(e)}\n".encode()
        finally:
            yield b"[stream] ended (exit 0)\n"

    return StreamingResponse(gen(), media_type="text/plain")


@app.get("/stream/ai-review-merge-cli")
def stream_ai_review_merge_cli(
    mr_url: str,
    auto_merge: bool = Query(True),
    deploy: bool = Query(True),
    verbose: bool = Query(True),
):
    """
    Mirrors: copilot-ai-review-merge <MR_URL> --auto-merge --deploy --verbose
    (Flags can be toggled by query, default True.)
    """
    cmd = ["copilot-ai-review-merge", mr_url]
    if auto_merge:
        cmd.append("--auto-merge")
    if deploy:
        cmd.append("--deploy")
    if verbose:
        cmd.append("--verbose")

    def gen():
        try:
            yield b"[stream] started\n"
            yield f"--- AI Review & Merge: {' '.join(cmd)}\n".encode()
            for chunk in _stream_cmd(cmd, cwd=ROOT):
                yield chunk
        except Exception as e:
            yield f"[error] {_safe_err(e)}\n".encode()
        finally:
            yield b"[stream] ended (exit 0)\n"

    return StreamingResponse(gen(), media_type="text/plain")


@app.get("/stream/qa-ec2-cli")
def stream_qa_ec2_cli(issue_key: str):
    """
    Mirrors: copilot-qa-ec2 <ISSUE>
    """
    cmd = ["copilot-qa-ec2", issue_key]

    def gen():
        try:
            yield b"[stream] started\n"
            yield f"--- QA EC2: {' '.join(cmd)}\n".encode()
            for chunk in _stream_cmd(cmd, cwd=ROOT):
                yield chunk
        except Exception as e:
            yield f"[error] {_safe_err(e)}\n".encode()
        finally:
            yield b"[stream] ended (exit 0)\n"

    return StreamingResponse(gen(), media_type="text/plain")
