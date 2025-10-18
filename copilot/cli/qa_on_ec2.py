#!/usr/bin/env python3
from __future__ import annotations

r"""
Simple QA on EC2 driven by Jira "QA steps" text.

Flow:
  1) Fetch QA text from Jira custom field (by key or by name) or fallback to Description.
  2) If YAML with "steps:" -> execute steps.
  3) Else, if Ollama available (LLM_PROVIDER=ollama), convert free text -> steps via LLM and execute.
  4) Comment + transition Jira on PASS/FAIL.

Supported steps (any step may include `expect` to assert substring on stdout):
  - drush: "<args>"                  # runs drush inside php container
  - php:   "<php code>"              # drush php:eval
  - shell: "<bash>"                  # run bash in php container
  - http_get: { url: "http://..." }  # curl -fsSL

Env (required):
  JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN
  EC2_HOST, EC2_USER=ubuntu, DEPLOY_SSH_KEY=~/.ssh/id_rsa (or PEM), DRUSH_URI=http://localhost

Env (optional):
  JIRA_QA_FIELD_KEY                  # e.g. customfield_10402
  JIRA_QA_FIELD_NAME="QA steps"      # if key not set, resolve by name then fallback to Description
  JIRA_TRANSITION_ON_QA_PASS="READY FOR QA, QA"
  JIRA_TRANSITION_ON_QA_FAIL="IN PROGRESS, TO DO"

  # LLM auto-wiring (Ollama)
  LLM_PROVIDER=ollama
  LLM_MODEL=qwen2.5-coder:7b-instruct-q4_0
  LLM_ENDPOINT=http://127.0.0.1:11434
  # (legacy aliases still recognized)
  OLLAMA_MODEL=...
  OLLAMA_URL=...

CLI:
  copilot-qa-ec2 CCS-123 [--no-llm] [--debug]
"""

import argparse
import os
import sys
import shlex
import json
import subprocess
from typing import Optional, Dict, Any, List, Tuple

# yaml (optional but recommended)
try:
    import yaml  # type: ignore
except Exception:
    yaml = None

# dotenv (optional)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

import requests


# ---------------- utilities ----------------

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v not in (None, "") else default

def _b64(s: str) -> str:
    import base64
    return base64.b64encode(s.encode("utf-8")).decode("ascii")

def _as_list(v) -> List[Any]:
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]

def _yaml_load(s: str):
    if yaml is None:
        return None
    try:
        return yaml.safe_load(s)
    except Exception:
        return None


# ---------------- Jira helpers ----------------

def _jira_headers() -> Dict[str, str]:
    email = _env("JIRA_EMAIL") or ""
    token = _env("JIRA_API_TOKEN") or ""
    if not (email and token):
        raise RuntimeError("Jira creds missing: set JIRA_EMAIL and JIRA_API_TOKEN")
    return {
        "Authorization": "Basic " + _b64(f"{email}:{token}"),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def _jira_base() -> str:
    base = (_env("JIRA_BASE_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("JIRA_BASE_URL not set")
    return base

def jira_get_field_id_by_name(field_name: str) -> Optional[str]:
    r = requests.get(f"{_jira_base()}/rest/api/3/field", headers=_jira_headers(), timeout=30)
    if r.status_code != 200:
        return None
    for f in r.json():
        if f.get("name") == field_name:
            return f.get("id")
    return None

def jira_fetch_field_text(issue_key: str, field_key: str) -> Optional[str]:
    params = {"fields": field_key}
    r = requests.get(f"{_jira_base()}/rest/api/3/issue/{issue_key}",
                     headers=_jira_headers(), params=params, timeout=30)
    if r.status_code != 200:
        return None
    fields = r.json().get("fields", {})
    val = fields.get(field_key)
    if val is None:
        return None
    if isinstance(val, str):
        return val.strip()
    try:
        return _adf_to_text(val).strip()
    except Exception:
        return None

def jira_fetch_description(issue_key: str) -> Optional[str]:
    r = requests.get(f"{_jira_base()}/rest/api/3/issue/{issue_key}?fields=description",
                     headers=_jira_headers(), timeout=30)
    if r.status_code != 200:
        return None
    desc = r.json().get("fields", {}).get("description")
    if desc is None:
        return None
    if isinstance(desc, str):
        return desc.strip()
    try:
        return _adf_to_text(desc).strip()
    except Exception:
        return None

def _adf_to_text(adf) -> str:
    parts: List[str] = []
    def walk(node):
        if not isinstance(node, dict):
            return
        if node.get("type") == "text":
            parts.append(node.get("text", ""))
        for k in ("content", "paragraphs"):
            v = node.get(k)
            if isinstance(v, list):
                for c in v:
                    walk(c)
        if node.get("type") in ("paragraph", "heading", "bulletList", "orderedList"):
            parts.append("\n")
    walk(adf if isinstance(adf, dict) else {})
    return "".join(parts)

def jira_transition(keys: List[str], names_csv: str) -> None:
    names = [s.strip() for s in (names_csv or "").split(",") if s.strip()]
    if not keys or not names:
        return
    try:
        from copilot.helpers.jira_helper import transition_issue_to_first_matching  # type: ignore
        for k in keys:
            try:
                transition_issue_to_first_matching(k, names)
                print(f"[jira] {k}: transition -> {names}: applied")
            except Exception as e:
                print(f"[jira] {k}: transition failed: {e}")
    except Exception as e:
        print(f"[jira] helper unavailable; skipping transitions: {e}")

def jira_comment(keys: List[str], comment: str) -> None:
    if not keys or not comment:
        return
    try:
        from copilot.helpers.jira_helper import add_comment  # type: ignore
        for k in keys:
            try:
                add_comment(k, comment, adf=True)
                print(f"[jira] {k}: comment added")
            except Exception as e:
                print(f"[jira] {k}: comment failed: {e}")
    except Exception as e:
        print(f"[jira] helper unavailable; skipping comments: {e}")


# ---------------- Ollama helpers (optional) ----------------

def ollama_available(url: str) -> bool:
    try:
        r = requests.get(url.rstrip("/") + "/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False

def ollama_to_steps(text: str, url: str, model: str, debug: bool=False) -> List[Dict[str, Any]]:
    """
    Use Ollama to convert free text to JSON steps.
    """
    sys_prompt = (
        "You convert QA instructions into a JSON object with a 'steps' array.\n"
        "Allowed step schemas:\n"
        '  {"drush": "cr", "expect": "..."}\n'
        '  {"php": "echo \\\\Drupal::config(\'system.site\').get(\'name\');", "expect": "..."}\n'
        '  {"shell": "ls -1 web/modules/custom", "expect": "..."}\n'
        '  {"http_get": {"url": "http://localhost/"},"expect":"..."}\n'
        "Return ONLY valid JSON (no markdown, no prose)."
    )
    user_prompt = f"Instructions:\n{text}\n\nReturn JSON now."

    payload = {
        "model": model,
        "system": sys_prompt,
        "prompt": user_prompt,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    r = requests.post(url.rstrip("/") + "/api/generate", json=payload, timeout=120)
    r.raise_for_status()
    content = r.json().get("response") or ""
    if debug:
        print(f"[debug] ollama raw: {content[:400]}{'...' if len(content)>400 else ''}")

    txt = content.strip()
    if txt.startswith("```"):
        txt = txt.strip("`").strip()
        if txt.startswith("json"):
            txt = txt[4:].lstrip()
    try:
        obj = json.loads(txt)
        steps = obj.get("steps") if isinstance(obj, dict) else None
        return steps if isinstance(steps, list) else []
    except Exception:
        return []


# ---------------- remote exec helpers ----------------

def build_ssh_base(host: str, user: str, key: str) -> List[str]:
    return ["ssh", "-i", key, "-o", "StrictHostKeyChecking=no", f"{user}@{host}"]

def ssh_exec(ssh_base: List[str], remote_cmd: str) -> Tuple[int, str, str]:
    proc = subprocess.run(ssh_base + [remote_cmd], capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()

def dc_exec_php(ssh_base: List[str], cmd: List[str], workdir: str="/var/www/html") -> Tuple[int, str, str]:
    # Always run docker compose from the stack dir on EC2 (where docker-compose.yml lives).
    stack_dir = _env("DEPLOY_WORKDIR", "/srv/drupal")
    joined = " ".join(shlex.quote(x) for x in cmd)
    remote = f"cd {shlex.quote(stack_dir)} && docker compose exec -T -w {shlex.quote(workdir)} php {joined} </dev/null"
    return ssh_exec(ssh_base, remote)


# ---------------- step runners ----------------

def run_step_remote(step: Dict[str, Any], ssh_base: List[str], drush_uri: str) -> Tuple[bool, str]:
    expect: Optional[str] = None

    if "drush" in step:
        spec = step["drush"]
        if isinstance(spec, dict):
            args = str(spec.get("args", "")).strip()
            expect = spec.get("expect")
        else:
            args = str(spec).strip()
            expect = step.get("expect")
        if not args:
            return False, "drush: missing args"
        rc, out, err = dc_exec_php(ssh_base, ["./vendor/bin/drush", f"--uri={drush_uri}", *shlex.split(args)])
        ok = (rc == 0) and ((expect is None) or (str(expect) in (out or "")))
        return ok, f"drush {args} -> rc={rc}\n{out or err}"

    if "php" in step:
        code = step["php"]
        if isinstance(code, dict):
            code = code.get("code", "")
            expect = step.get("expect") or step["php"].get("expect")
        else:
            expect = step.get("expect")
        code = str(code).strip()
        if not code:
            return False, "php: missing code"
        rc, out, err = dc_exec_php(ssh_base, ["./vendor/bin/drush", f"--uri={drush_uri}", "php:eval", code])
        ok = (rc == 0) and ((expect is None) or (str(expect) in (out or "")))
        return ok, f"php:eval -> rc={rc}\n{out or err}"

    if "shell" in step:
        spec = step["shell"]
        if isinstance(spec, dict):
            cmd = spec.get("cmd", "")
            expect = spec.get("expect")
        else:
            cmd = str(spec)
            expect = step.get("expect")
        cmd = cmd.strip()
        if not cmd:
            return False, "shell: missing cmd"
        rc, out, err = dc_exec_php(ssh_base, ["bash", "-lc", cmd])
        ok = (rc == 0) and ((expect is None) or (str(expect) in (out or "")))
        return ok, f"shell: {cmd} -> rc={rc}\n{out or err}"

    if "http_get" in step:
        spec = step["http_get"]
        if isinstance(spec, dict):
            url = spec.get("url")
            expect = spec.get("expect", step.get("expect"))
        else:
            url = str(spec)
            expect = step.get("expect")
        if not url:
            return False, "http_get: missing url"
        rc, out, err = dc_exec_php(ssh_base, ["curl", "-fsSL", url])
        ok = (rc == 0) and ((expect is None) or (str(expect) in (out or "")))
        return ok, f"http_get: {url} -> rc={rc}\n{out or err}"

    return False, f"unknown step: {json.dumps(step)}"

def run_steps_remote(steps: List[Dict[str, Any]], ssh_base: List[str], drush_uri: str) -> Tuple[bool, List[str]]:
    logs: List[str] = []
    all_ok = True
    for i, st in enumerate(_as_list(steps), 1):
        ok, msg = run_step_remote(st or {}, ssh_base=ssh_base, drush_uri=drush_uri)
        logs.append(f"[step {i}] {'OK' if ok else 'FAIL'}\n{msg}")
        if not ok:
            all_ok = False
    return all_ok, logs


# ---------------- main ----------------

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="QA on EC2 via Jira QA text (YAML steps or LLM)")
    ap.add_argument("issue_key", help="Jira issue key (e.g., CCS-73)")
    ap.add_argument("--no-llm", action="store_true", help="Disable LLM fallback")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args(argv)

    # --- resolve all config from env (no CLI knobs) ---
    jira_field_key  = (_env("JIRA_QA_FIELD_KEY", "") or "").strip()
    jira_field_name = (_env("JIRA_QA_FIELD_NAME", "QA steps") or "").strip()

    ec2_host = _env("EC2_HOST", "127.0.0.1")
    ec2_user = _env("EC2_USER", "ubuntu")
    ssh_key  = _env("DEPLOY_SSH_KEY", os.path.expanduser("~/.ssh/id_rsa"))
    drush_uri = _env("DRUSH_URI", "http://localhost")

    trans_pass = _env("JIRA_TRANSITION_ON_QA_PASS", "READY FOR QA, QA")
    trans_fail = _env("JIRA_TRANSITION_ON_QA_FAIL", "IN PROGRESS, TO DO")

    # LLM provider wiring (supports Ollama via generic envs)
    provider = (_env("LLM_PROVIDER", "") or "").lower()
    ollama_model = _env("LLM_MODEL") or _env("OLLAMA_MODEL") or "qwen2.5-coder:7b-instruct-q4_0"
    ollama_url   = _env("LLM_ENDPOINT") or _env("OLLAMA_URL") or "http://127.0.0.1:11434"

    # 1) Pull QA text from Jira
    qa_text = None
    if not jira_field_key and jira_field_name:
        try:
            jira_field_key = jira_get_field_id_by_name(jira_field_name) or ""
            if args.debug:
                print(f"[debug] resolved field '{jira_field_name}' -> '{jira_field_key}'")
        except Exception as e:
            if args.debug:
                print(f"[debug] field map failed: {e}")

    if jira_field_key:
        try:
            qa_text = jira_fetch_field_text(args.issue_key, jira_field_key)
            if args.debug:
                print(f"[debug] field text length={0 if qa_text is None else len(qa_text)}")
        except Exception as e:
            if args.debug:
                print(f"[debug] field fetch error: {e}")

    if not qa_text:
        try:
            qa_text = jira_fetch_description(args.issue_key)
            if args.debug:
                print(f"[debug] description length={0 if qa_text is None else len(qa_text)}")
        except Exception as e:
            if args.debug:
                print(f"[debug] description fetch error: {e}")

    if not qa_text:
        print("[qa] ERROR: Could not read QA text from Jira (field or description).")
        return 2

    # 2) Parse YAML with steps if possible
    steps: List[Dict[str, Any]] = []
    data = _yaml_load(qa_text)
    if isinstance(data, dict) and "steps" in data and isinstance(data["steps"], list):
        steps = data["steps"]

    # 3) If no YAML steps, try LLM (Ollama) to convert free text -> steps
    if not steps and not args.no_llm and provider == "ollama":
        if ollama_available(ollama_url):
            steps = ollama_to_steps(qa_text, ollama_url, ollama_model, debug=args.debug)
            if args.debug:
                print(f"[debug] ollama produced {len(steps)} step(s)")
        else:
            if args.debug:
                print(f"[debug] Ollama not available at {ollama_url}; skipping LLM fallback")

    if not steps:
        print("[qa] ERROR: No steps found (neither YAML nor LLM).")
        return 2

    if args.debug:
        print("[debug] steps:")
        print(json.dumps(steps, indent=2))

    # 4) Execute steps on EC2
    ssh_base = build_ssh_base(ec2_host, ec2_user, ssh_key)
    ok, logs = run_steps_remote(steps, ssh_base=ssh_base, drush_uri=drush_uri)
    print("\n".join(logs))

    # 5) Jira annotate + transition (two-step chain on PASS via env only)
    keys = [args.issue_key]
    msg = ("✅ QA passed on staging (EC2).\n" if ok else "❌ QA failed on staging (EC2).\n") + \
          "Steps:\n" + "\n".join(logs[:10])
    jira_comment(keys, msg)

    # Env-based transitions
    fail_csv = _env("JIRA_TRANSITION_ON_QA_FAIL", "IN PROGRESS, TO DO")
    pre_csv  = _env("JIRA_ON_QA_PASS_PRE",  _env("JIRA_TRANSITION_ON_QA_PASS", "READY FOR QA, QA"))
    post_csv = _env("JIRA_ON_QA_PASS_POST", "READY FOR RELEASE, READY FOR PROD, READY FOR DEPLOY")

    if ok:
        # 1) READY FOR QA (or your configured PRE value)
        if pre_csv:
            jira_transition(keys, pre_csv)
        # 2) READY FOR RELEASE (POST chain)
        if post_csv:
            jira_transition(keys, post_csv)
    else:
        if fail_csv:
            jira_transition(keys, fail_csv)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
