# copilot/cli/ai_review_and_merge.py
from __future__ import annotations
import argparse
import os
import re
import sys
import time
import subprocess
from textwrap import dedent
from typing import Tuple, List, Optional, Dict

import requests

from copilot.helpers.gitlab_helper import (
    resolve_project_id,
    mr_iid_from_url,
    get_mr_details,
    post_mr_comment,
    add_mr_labels,
    add_labels_to_mr,  # back-compat alias; uses add_mr_labels under the hood
    can_merge_mr,
    merge_mr,
)

from copilot.helpers.jira_helper import (
    extract_issue_keys_from_text,
    add_comment,
    transition_issue_to_first_matching,
)

from copilot.ai.llm import complete, is_disabled

DECISION_RE = re.compile(r"^\s*DECISION:\s*(APPROVED|CHANGES_REQUESTED|SKIPPED)\s*$", re.I)

SAFE_PREFIXES = ("notes/", "docs/")
SAFE_EXTS = (".md", ".markdown", ".rst")


def log(s: str, *, verbose: bool) -> None:
    if verbose:
        print(s, flush=True)


def parse_mr_url(url: str) -> Tuple[str, int]:
    """
    Parse GitLab MR URL like:
      https://gitlab.com/group/sub/proj/-/merge_requests/123
    Return (project_path, iid).
    """
    parts = url.rstrip("/").split("/")
    try:
        idx = parts.index("merge_requests")
        iid = int(parts[idx + 1])
        dash_idx = parts.index("-")
        project_path = "/".join(parts[3:dash_idx])
        return project_path, iid
    except Exception as e:
        raise SystemExit(f"Invalid MR URL format: {url} ({e})")


def get_changes(project_path: str, mr_iid: int) -> List[str]:
    """
    Return list of changed file paths for the MR (best-effort).
    Uses /merge_requests/:iid/changes.
    """
    host = (os.getenv("GITLAB_BASE_URL") or "https://gitlab.com").rstrip("/")
    token = os.getenv("GITLAB_API_TOKEN") or os.getenv("GITLAB_TOKEN")
    if not token:
        return []
    project_id = resolve_project_id(project_path)
    url = f"{host}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/changes"
    r = requests.get(url, headers={"PRIVATE-TOKEN": token}, timeout=30)
    if r.status_code != 200:
        return []
    data = r.json() or {}
    changes = data.get("changes") or []
    files: List[str] = []
    for ch in changes:
        p = ch.get("new_path") or ch.get("old_path")
        if p:
            files.append(p)
    return files


def is_trivial_change(project_path: str, mr_iid: int) -> bool:
    """
    Consider 'trivial' if *all* changed files are in SAFE_PREFIXES or SAFE_EXTS.
    """
    files = get_changes(project_path, mr_iid)
    if not files:
        return False
    for f in files:
        lf = f.lower()
        if not (lf.startswith(SAFE_PREFIXES) or lf.endswith(SAFE_EXTS)):
            return False
    return True


def build_review_prompt(mr: dict) -> tuple[str, str]:
    default_system = dedent("""
        You are a senior Drupal/PHP reviewer. Be concise and pragmatic.

        Review for:
        - Drupal 10/11 APIs only (no deprecated calls).
        - PSR-12 + Drupal coding standards (sniffs).
        - No edits outside custom modules (e.g., modules/custom/...).
        - Valid YAML (routes, services, permissions).
        - Proper DI (avoid static container unless justified).
        - Access checks, permissions, CSRF for routes/forms.
        - Config schema present when adding configuration.
        - Reasonable cacheability (contexts/tags/max-age) on renders.
        - Minimal, focused diff; no vendor/ or core changes.

        Decide one of: DECISION: APPROVED | CHANGES_REQUESTED.
        Output must start with a single line 'DECISION: ...' then short reasoning.
    """).strip()

    extra = os.getenv("DRUPAL_REVIEW_SYSTEM_PROMPT", "")
    system = (default_system + ("\n" + extra.strip() if extra.strip() else "")).strip()

    user = dedent(f"""
        Merge Request: {mr.get('web_url')}
        Title: {mr.get('title')}
        Author: {(mr.get('author') or {}).get('username','')}
        Source -> Target: {mr.get('source_branch')} -> {mr.get('target_branch')}
        Files changed are available in MR view; assume Drupal coding standards checks exist in CI.

        Please review and decide.
    """).strip()
    return system, user


def ensure_labels(project_path: str, mr_iid: int, labels: List[str]) -> List[str]:
    return add_mr_labels(project_path, mr_iid, labels)


# ---------- NEW: GitLab SHA helpers (for post-merge deploy) ----------

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v not in (None, "") else default

def gl_host() -> str:
    return (_env("GITLAB_BASE_URL", "https://gitlab.com") or "https://gitlab.com").rstrip("/")

def gl_token() -> Optional[str]:
    return _env("GITLAB_API_TOKEN") or _env("GITLAB_TOKEN")

def parse_project_path_from_mr_url(mr_url: str) -> Optional[str]:
    """
    https://gitlab.com/group/sub/proj/-/merge_requests/123 -> group/sub/proj
    """
    try:
        base, _ = mr_url.split("/-/merge_requests/", 1)
        return base.split("://", 1)[1].split("/", 1)[1].strip("/")
    except Exception:
        return None

def get_project_id(project_path: str) -> int:
    pid = requests.utils.quote(project_path, safe="")
    url = f"{gl_host()}/api/v4/projects/{pid}"
    headers = {"PRIVATE-TOKEN": gl_token() or ""}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return int(r.json()["id"])

def get_branch_sha(project_id: int, branch: str) -> Optional[str]:
    url = f"{gl_host()}/api/v4/projects/{project_id}/repository/branches/{branch}"
    headers = {"PRIVATE-TOKEN": gl_token() or ""}
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        return None
    return (r.json().get("commit") or {}).get("id")

def wait_for_branch_sha(project_id: int, branch: str, prev_sha: Optional[str],
                        timeout: int = 300, interval: int = 5) -> Optional[str]:
    """Poll until branch SHA changes from prev_sha (or until timeout)."""
    deadline = time.time() + timeout
    last_seen = None
    while time.time() < deadline:
        sha = get_branch_sha(project_id, branch)
        if sha:
            last_seen = sha
            if prev_sha and sha != prev_sha:
                return sha
            if not prev_sha:
                return sha
        time.sleep(interval)
    return last_seen


# ---------- Mergeability retry wrapper ----------

def _looks_like_checking(why: str | None) -> bool:
    if not why:
        return False
    w = why.lower()
    # Common shapes we see: 'checking', 'detailed_merge_status=checking', etc.
    return "checking" in w

def can_merge_with_retry(project_path: str, mr_iid: int, *, verbose: bool) -> tuple[bool, str]:
    """
    Wrap can_merge_mr() and retry while GitLab reports 'checking' mergeability.
    Controlled by MERGE_RETRY_MAX / MERGE_RETRY_INTERVAL envs.
    """
    max_attempts = int(_env("MERGE_RETRY_MAX", "20") or "20")
    interval = float(_env("MERGE_RETRY_INTERVAL", "3") or "3")

    attempt = 0
    last_why = ""
    while attempt < max_attempts:
        ok, why = can_merge_mr(project_path, mr_iid)
        last_why = why or ""
        if ok:
            return True, "mergeable"
        if not _looks_like_checking(why):
            # Not in 'checking' state — return immediately
            return False, (why or "")
        # Still 'checking' — sleep and retry
        attempt += 1
        if verbose:
            print(f"[ai-merge] Mergeability is still 'checking' (attempt {attempt}/{max_attempts}); retrying in {interval:.1f}s…", flush=True)
        time.sleep(interval)

    # Exceeded retries — return the last reason
    return False, last_why or "checking (timeout)"


# ---------- Deploy runner ----------

def run_deploy(script_path: str, *, target_branch: str, verbose: bool,
               extra_env: Optional[Dict[str, str]] = None) -> tuple[bool, str]:
    """
    Execute the deploy script and return (ok, combined_output).
    Pass DEPLOY_BRANCH and any extra_env to the script's environment.
    """
    if not os.path.isfile(script_path) or not os.access(script_path, os.X_OK):
        return False, f"Deploy script not found or not executable: {script_path}"

    env = os.environ.copy()
    env["DEPLOY_BRANCH"] = target_branch
    if extra_env:
        env.update({k: v for k, v in extra_env.items() if v is not None})

    try:
        proc = subprocess.run(
            [script_path],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=None,
            check=False,
        )
        out = proc.stdout or ""
        ok = (proc.returncode == 0)

        # Trim huge logs for comments
        if len(out) > 4000:
            out = out[-4000:]
            out = "(…deploy log truncated…)\n" + out

        if verbose:
            print(out)

        return ok, out
    except Exception as e:
        return False, f"Deploy invocation failed: {e}"


def main() -> int:
    ap = argparse.ArgumentParser(prog="copilot-ai-review-merge")
    ap.add_argument("mr_url", help="GitLab MR URL")
    ap.add_argument("--auto-approve-trivial", action="store_true")
    ap.add_argument("--auto-merge", action="store_true")

    # Deployment hooks
    ap.add_argument("--deploy", action="store_true", help="Run deploy after successful merge")
    ap.add_argument(
        "--deploy-script",
        default=os.getenv("COPILOT_DEPLOY_SCRIPT", "./scripts/deploy_to_ec2.sh"),
        help="Path to deploy script to execute after merge (default: ./scripts/deploy_to_ec2.sh)"
    )

    # Jira transitions
    ap.add_argument(
        "--on-merge-transition",
        default=os.getenv("JIRA_TRANSITION_ON_MERGE", "In Staging"),
        help="Comma-separated Jira transitions to apply on merge (default from env or 'In Staging')",
    )
    ap.add_argument(
        "--on-deploy-transition",
        default=os.getenv("JIRA_TRANSITION_ON_DEPLOY", "Ready for Test, QA"),
        help="Comma-separated Jira transitions to apply after successful deploy "
             "(default from env or 'Ready for Test, QA')",
    )

    # LLM controls
    ap.add_argument("--provider", default=os.getenv("LLM_PROVIDER", ""))
    ap.add_argument("--model", default=os.getenv("LLM_MODEL", ""))

    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    verbose = bool(args.verbose)

    # Resolve MR coordinates
    log(f"[ai-merge] Parsing MR URL: {args.mr_url}", verbose=verbose)
    project_path, mr_iid = parse_mr_url(args.mr_url)
    log(f"[ai-merge] Project: {project_path}, IID: {mr_iid}", verbose=verbose)

    mr = get_mr_details(project_path, mr_iid)
    log(f"[ai-merge] Loaded MR: {mr.get('title')} ({mr.get('web_url')})", verbose=verbose)

    # Extract Jira keys from MR title+description
    log("[ai-merge] Extracting Jira keys from MR title/description…", verbose=verbose)
    issue_keys = extract_issue_keys_from_text(
        (mr.get("title") or "") + "\n" + (mr.get("description") or "")
    )
    log(f"[ai-merge] Jira keys detected: {issue_keys}", verbose=verbose)

    # Tag as AI-reviewed
    log("[ai-merge] Labeling MR as ai-reviewed…", verbose=verbose)
    ensure_labels(project_path, mr_iid, ["ai-reviewed"])

    # Possibly auto-approve trivial changes
    trivial_approved = False
    trivial_msg = ""
    if args.auto_approve_trivial and is_trivial_change(project_path, mr_iid):
        trivial_approved = True
        trivial_msg = "Auto-approved: only changes in safe paths.\n"

    # LLM-based decision
    decision_text = "DECISION: SKIPPED\nAI review skipped (no LLM or disabled)."
    decision = "SKIPPED"

    try:
        if trivial_approved:
            decision = "APPROVED"
            files = get_changes(project_path, mr_iid) or []
            decision_text = "DECISION: APPROVED\n" + trivial_msg + ("Files:\n" + "\n".join(files) if files else "")
        elif not is_disabled():
            log("[ai-merge] Starting AI review…", verbose=verbose)
            sys_prompt, user_prompt = build_review_prompt(mr)
            text = complete(system=sys_prompt, user=user_prompt, model=args.model or None, provider=args.provider or None)
            decision_text = (text or "").strip()
            first = (decision_text.splitlines() or [""])[0]
            m = DECISION_RE.match(first)
            decision = (m.group(1).upper() if m else "CHANGES_REQUESTED")
        else:
            ensure_labels(project_path, mr_iid, ["changes-requested"])
    except Exception as e:
        decision_text = f"DECISION: SKIPPED\nAI review error: {e}"
        decision = "SKIPPED"

    # Post review note
    try:
        log("[ai-merge] Posting MR review comment…", verbose=verbose)
        post_mr_comment(project_path, mr_iid, decision_text)
    except Exception:
        pass

    # Handle outcomes
    if decision == "APPROVED":
        log("[ai-merge] AI decision: APPROVED", verbose=verbose)
        ensure_labels(project_path, mr_iid, ["ready-to-merge"])

        # 🔁 Retry while GitLab is still "checking" mergeability
        ok, why = can_merge_with_retry(project_path, mr_iid, verbose=verbose)

        if args.auto_merge and ok:
            try:
                log("[ai-merge] Attempting auto-merge…", verbose=verbose)
                merged = merge_mr(project_path, mr_iid)
                if merged:
                    log("[ai-merge] Merge succeeded.", verbose=verbose)
                    # Transition Jira issues on merge
                    merge_seq = [x.strip() for x in (args.on_merge_transition or "").split(",") if x.strip()]
                    for key in issue_keys:
                        if merge_seq:
                            try:
                                transition_issue_to_first_matching(key, merge_seq)
                            except Exception:
                                pass
                        try:
                            add_comment(key, f"MR merged: {args.mr_url}")
                        except Exception:
                            pass

                    # Optional deploy
                    if args.deploy:
                        target_branch = mr.get("target_branch") or "main"
                        log(f"[ai-merge] Deploy requested. Preparing to deploy to EC2…", verbose=verbose)

                        # Resolve and wait for new staging SHA (GitLab API)
                        expect_sha = None
                        pre_sha = None
                        project_path_from_url = parse_project_path_from_mr_url(args.mr_url) or project_path
                        extra_env: Dict[str, str] = {}
                        if gl_token() and project_path_from_url:
                            try:
                                pid = get_project_id(project_path_from_url)
                                pre_sha = get_branch_sha(pid, target_branch)
                                if pre_sha:
                                    log(f"[ai-merge] Pre-merge {target_branch} SHA: {pre_sha}", verbose=verbose)
                                timeout = int(_env("EXPECT_TIMEOUT", "300") or "300")
                                interval = int(_env("EXPECT_INTERVAL", "5") or "5")
                                log(f"[ai-merge] Waiting for {target_branch} to update… (timeout {timeout}s, every {interval}s)", verbose=verbose)
                                expect_sha = wait_for_branch_sha(pid, target_branch, prev_sha=pre_sha, timeout=timeout, interval=interval)
                                if expect_sha and pre_sha and expect_sha == pre_sha:
                                    log("[ai-merge] WARNING: Branch SHA did not change within timeout; deploying anyway.", verbose=verbose)
                            except Exception as e:
                                log(f"[ai-merge] WARNING: Could not resolve/poll branch SHA: {e}. Deploying without EXPECT_SHA.", verbose=verbose)

                        # Build deploy env
                        extra_env["DRUSH_URI"] = _env("DRUSH_URI", "http://localhost") or "http://localhost"
                        extra_env["DEPLOY_GIT_REMOTE_URL"] = _env("DEPLOY_GIT_REMOTE_URL") or f"git@gitlab.com:{project_path_from_url}.git"
                        if expect_sha:
                            extra_env["EXPECT_SHA"] = expect_sha
                            extra_env["EXPECT_TIMEOUT"] = _env("EXPECT_TIMEOUT", "300") or "300"
                            extra_env["EXPECT_INTERVAL"] = _env("EXPECT_INTERVAL", "5") or "5"
                            log(f"[ai-merge] Will require EXPECT_SHA={expect_sha} on EC2.", verbose=verbose)

                        log(f"[ai-merge] Running {args.deploy_script!r} (DEPLOY_BRANCH={target_branch})…", verbose=verbose)
                        ok, out = run_deploy(args.deploy_script, target_branch=target_branch, verbose=verbose, extra_env=extra_env)

                        # Comment to MR either way
                        try:
                            post_mr_comment(project_path, mr_iid,
                                            f"Post-merge deploy {'succeeded ✅' if ok else 'failed ❌'}.\n\n```\n{out}\n```")
                        except Exception:
                            pass

                        # Comment + transition in Jira
                        for key in issue_keys:
                            try:
                                add_comment(key, f"Staging deploy {'succeeded' if ok else 'failed'}.\n\n```\n{out}\n```")
                            except Exception:
                                pass
                            if ok:
                                deploy_seq = [x.strip() for x in (args.on_deploy_transition or "").split(",") if x.strip()]
                                if deploy_seq:
                                    try:
                                        transition_issue_to_first_matching(key, deploy_seq)
                                    except Exception:
                                        pass
                else:
                    post_mr_comment(project_path, mr_iid,
                        "AI approved ✅ but this bot user lacks permission to merge into the target branch.")
            except Exception as e:
                post_mr_comment(project_path, mr_iid, f"Merge attempt failed: {e}")
        elif args.auto_merge and not ok:
            post_mr_comment(
                project_path, mr_iid,
                f"AI approved ✅ but cannot merge now ({why}). Maintainership / pipeline / discussions may block."
            )
        return 0

    if decision in ("CHANGES_REQUESTED", "SKIPPED"):
        log(f"[ai-merge] AI decision: {decision}", verbose=verbose)
        ensure_labels(project_path, mr_iid, ["changes-requested"])
        trans = os.getenv("JIRA_TRANSITION_ON_CHANGES", "")
        seq = [x.strip() for x in trans.split(",") if x.strip()]
        for key in issue_keys:
            if seq:
                try:
                    transition_issue_to_first_matching(key, seq)
                except Exception:
                    pass
            try:
                add_comment(key, "AI review requested changes on the MR.")
            except Exception:
                pass
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
