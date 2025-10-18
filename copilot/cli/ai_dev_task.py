# copilot/cli/ai_dev_task.py
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from typing import Dict, List, Optional

from copilot.agents.prompt_builder import build_prompt
from copilot.ai.llm import complete, is_disabled
from copilot.codegen.patch_applier import PatchApplier, PatchApplyError

# =========================
# Config / Env
# =========================
COPILOT_DEBUG = os.getenv("COPILOT_DEBUG_LLM", "0") == "1"
FORCE_MANIFEST_ENV = os.getenv("COPILOT_FORCE_MANIFEST", "0") == "1"
MANIFEST_MAX_TOKENS = int(os.getenv("LLM_MANIFEST_MAX_TOKENS", "800"))

# =========================
# Shell / Git helpers
# =========================
def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\n{p.stderr}")
    return p

def _git_current_branch(repo: Path) -> str:
    p = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    return (p.stdout or "").strip()

def _git_has_changes(repo: Path) -> bool:
    p = _run(["git", "status", "--porcelain"], cwd=repo)
    return bool((p.stdout or "").strip())

def _git_commit_all(repo: Path, message: str) -> None:
    _run(["git", "add", "-A"], cwd=repo)
    if not _git_has_changes(repo):
        raise RuntimeError("No changes to commit")
    _run(["git", "commit", "-m", message], cwd=repo)

def _git_push_current(repo: Path) -> None:
    branch = _git_current_branch(repo)
    _run(["git", "push", "-u", "origin", branch], cwd=repo)
    print(f">>> Pushed branch '{branch}' to origin.")

# =========================
# Debug helpers
# =========================
def _debug_dump(name: str, content: str) -> None:
    if not COPILOT_DEBUG:
        return
    d = Path(".copilot_debug")
    d.mkdir(exist_ok=True)
    f = d / f"{name}"
    try:
        f.write_text(content or "", encoding="utf-8")
        print(f"[debug] wrote {f}")
    except Exception as e:
        print(f"[debug] could not write {f}: {e}", file=sys.stderr)

# =========================
# Diff helpers
# =========================
_CODE_FENCE_RE = re.compile(r"^\s*```+([a-zA-Z0-9_-]*)?\s*$")

def _extract_first_diff_block(text: str) -> str:
    """Best-effort: pull out a unified diff from LLM output."""
    if not text:
        return ""
    lines = text.splitlines()
    if lines and _CODE_FENCE_RE.match(lines[0]):
        end_idx = None
        for i in range(1, len(lines)):
            if _CODE_FENCE_RE.match(lines[i]):
                end_idx = i
                break
        if end_idx is not None:
            lines = lines[1:end_idx]
    body = "\n".join(lines)
    m = re.search(r"^diff --git a/.+ b/.+", body, flags=re.M)
    if m:
        return body[m.start():]
    m = re.search(r"^diff --git a/.+ b/.+", text, flags=re.M)
    if m:
        return text[m.start():]
    return ""

def _looks_like_unified_diff(text: str) -> bool:
    if not text:
        return False
    return (
        "diff --git a/" in text
        and re.search(r"^(\+\+\+|---) [ab]/", text, flags=re.M) is not None
        and re.search(r"^@@\s+-\d", text, flags=re.M) is not None
    )

# =========================
# JSON manifest helpers
# =========================
def _extract_outer_json(s: str) -> str:
    """Return the outermost JSON object even if the model wrapped it in prose/fences."""
    if not s or not isinstance(s, str) or not s.strip():
        raise ValueError("Empty LLM response.")
    m = re.search(r"```(?:json)?\s*({.*?})\s*```", s, flags=re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(r"\{.*\}\s*$", s, flags=re.DOTALL)
    if m:
        return m.group(0)
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and last > first:
        return s[first:last + 1]
    raise ValueError("No JSON object found in LLM output.")

def _derive_machine_name(issue_key: str) -> str:
    base = issue_key.strip().lower().replace("-", "_")
    return "".join(ch for ch in base if ch.isalnum() or ch == "_") or "copilot_module"

def _detect_docroot(repo: Path) -> str:
    """Return 'web' or 'docroot' depending on project layout; default 'web'."""
    if (repo / "web" / "index.php").exists():
        return "web"
    if (repo / "docroot" / "index.php").exists():
        return "docroot"
    return "web"

def _normalize_repo_path(p: str, docroot: str) -> str:
    """Normalize manifest paths to the actual docroot."""
    p = p.lstrip("/").replace("\\", "/")
    if p.startswith("docroot/"):
        return docroot + p[len("docroot"):]
    if p.startswith("web/"):
        return docroot + p[len("web"):]
    if p.startswith("modules/"):
        return f"{docroot}/{p}"
    return p

def _allowed_path(target: Path, repo: Path, allowed_dirs: Optional[List[str]]) -> bool:
    """Ensure target is inside repo and (if provided) inside one of allowed subpaths."""
    try:
        target_resolved = target.resolve()
        repo_resolved = repo.resolve()
        target_resolved.relative_to(repo_resolved)
    except Exception:
        return False
    if not allowed_dirs:
        return True
    rel = str(target_resolved.relative_to(repo_resolved)).replace("\\", "/")
    for d in allowed_dirs:
        d_norm = d.strip("/").lower()
        if rel.lower().startswith(d_norm + "/") or rel.lower() == d_norm:
            return True
    return False

# ---------- PHP sanitizer ----------
_PHP_VAR_ESC_RE = re.compile(r'\\(\$[A-Za-z_][A-Za-z0-9_]*)')

def _php_sanitize(s: str) -> str:
    """
    Sanitize LLM-produced PHP/module files:
      1) Remove stray backslashes before PHP variables: \$var -> $var
      2) Drop any declare(...) statements (avoid in module files)
      3) Drop DRUPAL_MINIMUM_PHP define (unwanted)
      4) Fix accidental '\\t(' -> 't(' in translations
      5) Ensure trailing newline and collapse excessive blank lines
    """
    s = s.replace('\r\n', '\n').replace('\r', '\n')

    # 1) unescape PHP variables
    s = _PHP_VAR_ESC_RE.sub(r'\1', s)

    # 2) remove declare(...) lines anywhere
    s = re.sub(r'^\s*declare\s*\([^)]*\)\s*;\s*$', '', s, flags=re.MULTILINE)

    # 3) remove DRUPAL_MINIMUM_PHP define
    s = re.sub(r"^\s*define\s*\(\s*['\"]DRUPAL_MINIMUM_PHP['\"][^)]*\)\s*;\s*$", '', s, flags=re.MULTILINE)

    # 4) fix \t( to t(
    s = s.replace(r'\t(', 't(')

    # 5) tidy blanks & ensure trailing newline
    s = re.sub(r'\n{3,}', '\n\n', s).strip('\n') + '\n'
    return s

def _write_files_from_manifest(repo: Path, manifest: Dict, *, allowed_dirs: Optional[List[str]], docroot: str) -> List[Path]:
    """Write files from parsed JSON manifest."""
    if not isinstance(manifest, dict):
        raise ValueError("Manifest is not a JSON object")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Manifest has no 'files' array")
    written: List[Path] = []
    for entry in files:
        p = entry.get("path")
        c = entry.get("content")
        if not isinstance(p, str) or not isinstance(c, str):
            continue
        p_norm = _normalize_repo_path(p, docroot)
        target = (repo / p_norm).resolve()
        if not _allowed_path(target, repo, allowed_dirs):
            raise ValueError(f"Path not allowed by guardrails: {p_norm}")

        # PHP-specific cleanup
        ext = os.path.splitext(p_norm)[1].lower()
        if ext in ('.php', '.module', '.inc'):
            c = _php_sanitize(c)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(c, encoding="utf-8")
        written.append(target)
    return written

def _build_manifest_instruction(issue_key: str, repo: Path, allowed_dirs: Optional[List[str]], docroot: str) -> str:
    machine = _derive_machine_name(issue_key)
    base_hint = f"{docroot}/modules/custom/{machine}/"
    guard_dirs = allowed_dirs or [base_hint]
    return dedent(f"""\
    If you cannot produce a valid unified diff OR when the change is predominantly creating new files,
    output a STRICT JSON manifest with NO explanations:

    {{
      "files": [
        {{"path": "PATH/RELATIVE/TO/REPO", "content": "FULL FILE CONTENTS"}}
      ]
    }}

    Rules:
    - Paths MUST be relative to repository root.
    - Paths MUST be under one of: {guard_dirs}.
    - The project docroot is '{docroot}/'. Prefer placing new code under '{docroot}/modules/custom/'.
    - Emit ONLY valid JSON (no markdown fences, no comments, no trailing commas).
    - Ensure YAML and PHP are syntactically valid.
    - Escape all backslashes in JSON strings (e.g., use \\\\Drupal).
    - Keep files minimal and Drupal 11-compatible.

    PHP STRICTNESS:
    - Do NOT escape PHP variables. There must be NO backslash before any $variable.
    - Do NOT use declare(strict_types=1) in module files.
    - Do NOT define constants like DRUPAL_MINIMUM_PHP.
    """)

# --- Repair helpers ---
def _json_escape_repair_in_strings(raw: str) -> str:
    """Repair invalid JSON backslashes like \Drupal or \Some\Path."""
    valid_esc = set('"\\/bfnrtu')
    out = []
    in_str = False
    esc = False
    for ch in raw:
        if not in_str:
            if ch == '"':
                in_str = True
            out.append(ch)
            continue
        if esc:
            if ch not in valid_esc:
                out.append('\\')
            out.append(ch)
            esc = False
            continue
        if ch == '\\':
            esc = True
            out.append(ch)
            continue
        if ch == '"':
            in_str = False
        out.append(ch)
    return ''.join(out)

def _escape_ctrl_in_strings(txt: str) -> str:
    """
    Escape literal control characters only inside JSON string values:
    \\n -> \\n, \\r -> \\r, \\t -> \\t (i.e., replace real control chars with escapes).
    """
    out = []
    in_str = False
    esc = False
    for ch in txt:
        if not in_str:
            out.append(ch)
            if ch == '"':
                in_str = True
            continue
        if esc:
            out.append(ch)
            esc = False
            continue
        if ch == '\\':
            esc = True
            out.append(ch)
            continue
        if ch == '"':
            in_str = False
            out.append(ch)
            continue
        if ch == '\n':
            out.extend(['\\', 'n']); continue
        if ch == '\r':
            out.extend(['\\', 'r']); continue
        if ch == '\t':
            out.extend(['\\', 't']); continue
        out.append(ch)
    return ''.join(out)

# --- Manifest generation ---
def _try_manifest_generation(
    issue_key: str,
    repo: Path,
    system_prompt: str,
    user_prompt: str,
    provider: Optional[str],
    model: Optional[str],
    allowed_dirs: Optional[List[str]],
    docroot: str,
) -> List[Path]:
    """Ask the LLM for a JSON manifest and write files if valid."""
    instruction = _build_manifest_instruction(issue_key, repo, allowed_dirs, docroot)
    user2 = (
        f"{user_prompt}\n\n{instruction}\n\n"
        "IMPORTANT: Output STRICT valid JSON. Escape all backslashes (\\\\), quotes (\\\"), and newlines (\\\\n). "
        "Do NOT escape PHP variables (no backslash before $variable)."
    ).strip()

    print(">>> JSON manifest mode …")
    out = complete(
        system=system_prompt,
        user=user2,
        provider=provider,
        model=model,
        max_tokens=MANIFEST_MAX_TOKENS,
    ) or ""

    _debug_dump("manifest_raw.txt", out)

    try:
        raw = _extract_outer_json(out)
    except Exception as e:
        raise RuntimeError(f"LLM did not return JSON-looking content: {e}")

    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError:
        repaired = _json_escape_repair_in_strings(raw)
        repaired = _escape_ctrl_in_strings(repaired)
        try:
            manifest = json.loads(repaired)
            _debug_dump("manifest_repaired.json", repaired)
        except Exception as e2:
            snippet = (raw[:240] + '...') if len(raw) > 240 else raw
            raise RuntimeError(
                f"LLM did not return valid JSON manifest (raw+repaired failed): {e2}\nSnippet:\n{snippet}"
            )

    written = _write_files_from_manifest(repo, manifest, allowed_dirs=allowed_dirs, docroot=docroot)
    return written

# =========================
# Main
# =========================
def main() -> int:
    ap = argparse.ArgumentParser(description="Generate code via LLM (diff or manifest).")
    ap.add_argument("issue_key", help="Jira issue key, e.g., CCS-123")
    ap.add_argument("--repo", default=os.getenv("COPILOT_REPO_PATH", "./work/drupal-project"))
    ap.add_argument("--provider", default=os.getenv("LLM_PROVIDER", ""))
    ap.add_argument("--model", default=os.getenv("LLM_MODEL", ""))
    ap.add_argument("--allow-outside-custom", action="store_true")
    ap.add_argument("--force-manifest", action="store_true")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not (repo / ".git").exists():
        print(f"ERROR: Not a git repo: {repo}", file=sys.stderr)
        return 2

    docroot = _detect_docroot(repo)
    allowed_dirs_default = [f"{docroot}/modules/custom/"]
    allowed_dirs = None if args.allow_outside_custom else allowed_dirs_default

    prompts = build_prompt(args.issue_key, str(repo))
    system_prompt = prompts.get("system_prompt", "")
    user_prompt = prompts.get("user_prompt", "")
    guardrails_text = prompts.get("guardrails", "")
    title = (prompts.get("title", "") or args.issue_key).strip()

    if is_disabled():
        print("(Skipping LLM execution; COPILOT_DISABLE_LLM=1)")
        return 0

    force_manifest = args.force_manifest or FORCE_MANIFEST_ENV

    if force_manifest:
        try:
            written = _try_manifest_generation(
                args.issue_key,
                repo,
                system_prompt,
                user_prompt,
                args.provider or None,
                args.model or None,
                allowed_dirs,
                docroot,
            )
            if not written:
                print("ERROR: Manifest produced no files.", file=sys.stderr)
                return 7

            rels = [str(p.relative_to(repo)) for p in written]
            _run(["git", "add", *rels], cwd=repo)
            _git_commit_all(repo, f"feat({args.issue_key}): add files via LLM manifest — {title}")
            _git_push_current(repo)
            print(">>> Files created from manifest, committed, and pushed:")
            for p in rels:
                print(" -", p)
            print("[PATCH] applied_and_pushed=1")
            return 0
        except Exception as e:
            print(f"ERROR: Manifest mode failed: {e}", file=sys.stderr)
            return 8

    print(">>> Generating patch via LLM …")
    diff_user = f"{user_prompt}\n\n{guardrails_text}".strip()
    raw = complete(
        system=system_prompt,
        user=diff_user,
        provider=args.provider or None,
        model=args.model or None,
    )
    _debug_dump("diff_raw.txt", raw)
    patch_text = _extract_first_diff_block(raw)

    if _looks_like_unified_diff(patch_text):
        try:
            PatchApplier(allowed_dirs=allowed_dirs).apply_patch(repo, patch_text)
            _git_commit_all(repo, f"feat({args.issue_key}): apply LLM patch — {title}")
            _git_push_current(repo)
            print(">>> Patch applied, committed, and pushed.")
            return 0
        except PatchApplyError as e:
            print(f"[warn] Patch could not be applied safely: {e}")

    print("[info] LLM did not return a valid unified diff; will try manifest mode.")
    try:
        written = _try_manifest_generation(
            args.issue_key,
            repo,
            system_prompt,
            user_prompt,
            args.provider or None,
            args.model or None,
            allowed_dirs,
            docroot,
        )
        if not written:
            print("ERROR: Manifest produced no files.", file=sys.stderr)
            return 7

        rels = [str(p.relative_to(repo)) for p in written]
        _run(["git", "add", *rels], cwd=repo)
        _git_commit_all(repo, f"feat({args.issue_key}): add files via LLM manifest — {title}")
        _git_push_current(repo)
        print(">>> Files created from manifest, committed, and pushed:")
        for p in rels:
            print(" -", p)
        print("[PATCH] applied_and_pushed=1")
        return 0
    except Exception as e:
        print(f"ERROR: Manifest mode failed: {e}", file=sys.stderr)
        return 8


if __name__ == "__main__":
    raise SystemExit(main())
