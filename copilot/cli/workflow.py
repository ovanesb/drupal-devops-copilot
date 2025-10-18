# copilot/cli/workflow.py
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from typing import Optional

# Optional: load .env automatically if python-dotenv is installed
try:  # pragma: no cover
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Jira client (prefer your app’s client if present; otherwise use built-in)
try:
    from your_project.jira_client import YourJiraClient as JiraClient  # type: ignore
except Exception:  # pragma: no cover
    from copilot.jira import JiraClient  # type: ignore

from copilot.agents.workflow_agent import WorkflowAgent, WorkflowConfig


# ---------------- env helpers ----------------

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v not in (None, "") else default

def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


# ---------------- repo helpers ----------------

def ensure_repo(repo_path: str, repo_url: Optional[str], base_branch: str, dry_run: bool) -> None:
    repo_git = os.path.join(repo_path, ".git")
    if os.path.isdir(repo_git):
        return
    if not repo_url:
        raise SystemExit(f"Repo path '{repo_path}' not found and --repo-url not provided.")
    os.makedirs(os.path.dirname(repo_path) or ".", exist_ok=True)
    print(f"$ git clone {repo_url} {repo_path}")
    if not dry_run:
        subprocess.check_call(["git", "clone", repo_url, repo_path])
    print(f"$ (cd {repo_path} && git fetch origin && git checkout {base_branch} && git pull --ff-only origin {base_branch})")
    if not dry_run:
        subprocess.check_call(["git", "fetch", "origin"], cwd=repo_path)
        subprocess.check_call(["git", "checkout", base_branch], cwd=repo_path)
        subprocess.check_call(["git", "pull", "--ff-only", "origin", base_branch], cwd=repo_path)


def parse_requested_module_name(text: str) -> str | None:
    """
    Best-effort: look for 'Name the module <slug>' or backticked name in Jira description/AC.
    Returns snake_case (Drupal machine name) when found.
    """
    if not text:
        return None
    m = re.search(r"`([a-zA-Z0-9\-_]+)`", text)  # backticked first
    candidate = m.group(1) if m else None
    if not candidate:
        m2 = re.search(r"[Nn]ame the module\s+([a-zA-Z0-9\-_]+)", text)
        if m2:
            candidate = m2.group(1)
    if not candidate:
        return None
    s = candidate.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or None


# ---------------- optional deterministic (now NO-OP) ----------------

def run_auto_dev_on_current_branch(jira_key: str, repo_path: str, module_name: str | None) -> None:
    """
    Invoke the deterministic scaffolder on the CURRENT HEAD (feature branch already checked out).
    Currently a NO-OP (kept for compatibility).
    """
    try:
        from copilot.cli.auto_dev import main as auto_dev_main  # type: ignore
        print(f"[workflow] (auto-dev) running (currently NO-OP)…")
        args = ["--repo", repo_path, "--execute", jira_key]
        if module_name:
            args = ["--repo", repo_path, "--execute", "--module-name", module_name, jira_key]
        auto_dev_main(args)
    except Exception as e:
        print(f"[workflow] auto-dev skipped (missing/no-op): {e}")


# ---------------- NEW: LLM patch step ----------------

def run_llm_patch(jira_key: str, repo_path: str, *, provider: Optional[str], model: Optional[str]) -> bool:
    """
    Run the LLM patch creator which:
      - builds a Drupal-aware prompt (prompt_builder.py)
      - asks the LLM for a unified diff
      - applies the patch into the repo

    Returns True on success (patch applied), False otherwise.
    """
    cmd = ["python", "copilot/cli/ai_dev_task.py", jira_key, "--repo", repo_path]
    if provider:
        cmd += ["--provider", provider]
    if model:
        cmd += ["--model", model]

    print("$ " + " ".join(cmd))
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = (proc.stdout or "")
    if out:
        print(out, end="")

    if proc.returncode != 0:
        print(f"[workflow] LLM patch failed (rc={proc.returncode})")
        return False

    # Best-effort sanity: look for signal lines the task prints on success
    applied = ("[patch] applied" in out.lower()) or ("diff applied" in out.lower()) or ("created_files" in out)
    if not applied:
        # Still OK—some versions only exit 0; commit step will detect changes anyway.
        print("[workflow] LLM patch exited 0; proceeding to commit.")
    return True


# ---------------- Jira breadcrumbs ----------------

def jira_breadcrumbs_on_mr_open(jira_key: str, mr_url: str) -> None:
    """
    Post Jira link+comment and attempt a transition (first matching in env list).
    Safe no-op if helper/env is missing.
    """
    try:
        from copilot.helpers.jira_helper import (  # type: ignore
            add_comment, add_link_to_issue, transition_issue_to_first_matching, get_available_transitions
        )
    except Exception as e:
        print(f"[Jira] helpers not available ({e}). Skipping Jira breadcrumbs.")
        return

    if not jira_key:
        return

    # Link the MR
    try:
        if mr_url:
            add_link_to_issue(jira_key, mr_url, title="Merge Request")
    except Exception as e:
        print(f"[Jira] add_link_to_issue failed (non-fatal): {e}")

    # Comment
    try:
        body = f"Automated MR created: {mr_url}" if mr_url else "Automated MR creation attempted (no URL)."
        add_comment(jira_key, body, adf=True)
    except Exception as e:
        print(f"[Jira] add_comment failed (non-fatal): {e}")

    # Transition (optional): comma-separated list; we pick the first available
    desired = os.getenv("JIRA_TRANSITION_ON_MR_OPEN", "")
    names = [s.strip() for s in desired.split(",") if s.strip()]
    if not names:
        return

    try:
        ok = transition_issue_to_first_matching(jira_key, names)
        if not ok:
            try:
                avail = [t.get("name") for t in get_available_transitions(jira_key)]
            except Exception:
                avail = []
            print(f"[Jira] No matching transition among {names}; available: {avail}")
    except Exception as e:
        print(f"[Jira] transition failed (non-fatal): {e}")


# ---------------- main ----------------

def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Drupal DevOps Co-Pilot — Workflow (branch → LLM patch → commit → MR)"
    )
    p.add_argument("jira_key", help="Jira issue key, e.g., CCS-96")

    # Flags (env defaults let you run bare `copilot-workflow <ISSUE>`)
    p.add_argument("--dry-run", action="store_true", help="Print commands; do not change repo or call GitLab")

    # Draft handling: support new --draft (preferred) and keep old --no-draft for back-compat.
    p.add_argument("--draft", action="store_true", help="Create the MR as a draft (default: off)")
    p.add_argument("--no-draft", action="store_true", help=argparse.SUPPRESS)  # deprecated

    # Base branch: prefer BASE_BRANCH (then GIT_TARGET_BRANCH), default 'staging'
    p.add_argument("--base",
                   default=_env("BASE_BRANCH", _env("GIT_TARGET_BRANCH", "staging")),
                   help="Base/target branch (default from BASE_BRANCH/GIT_TARGET_BRANCH or 'staging')")

    # Labels from env
    p.add_argument("--labels",
                   default=_env("GITLAB_MR_LABELS", "autodev,ai-change,ready-to-merge"),
                   help="Comma-separated labels for the MR (default from GITLAB_MR_LABELS)")

    # Title/body override optional
    p.add_argument("--title", default=None, help="Override MR title (defaults to '<JIRA>: <Issue summary>')")
    p.add_argument("--body", default=None, help="Override commit body (defaults to Jira description)")

    # Repo + GitLab project path from env
    p.add_argument("--repo",
                   default=_env("COPILOT_REPO_PATH", os.getcwd()),
                   help="Path to the target repo (default from COPILOT_REPO_PATH or cwd)")
    p.add_argument("--repo-url",
                   default=_env("COPILOT_REPO_URL"),
                   help="If --repo missing, clone from this URL into --repo path")
    p.add_argument("--gitlab-project-id", default=None, help="Override GitLab project ID for this run")
    p.add_argument("--gitlab-project-path",
                   default=_env("GITLAB_PROJECT_PATH"),
                   help="Override GitLab project path for this run (default from GITLAB_PROJECT_PATH)")

    # LLM controls (default ON unless COPILOT_DISABLE_LLM=1)
    default_llm_enabled = not _env_bool("COPILOT_DISABLE_LLM", False)
    llm_group = p.add_mutually_exclusive_group()
    llm_group.add_argument("--llm", dest="llm_enabled", action="store_true",
                           default=default_llm_enabled, help=argparse.SUPPRESS)
    llm_group.add_argument("--no-llm", dest="llm_enabled", action="store_false",
                           help="Disable the LLM patch step (default: enabled unless COPILOT_DISABLE_LLM=1)")

    # Provider/model pass-through (optional; can rely on env)
    p.add_argument("--provider", default=_env("LLM_PROVIDER"), help="LLM provider (e.g., openai, ollama)")
    p.add_argument("--model", default=_env("LLM_MODEL"), help="LLM model (e.g., gpt-4o-mini, llama3.1:8b)")

    # Optional deterministic (legacy) step — default OFF now
    default_auto_dev = _env_bool("COPILOT_AUTO_DEV", False)
    auto_dev_group = p.add_mutually_exclusive_group()
    auto_dev_group.add_argument("--auto-dev", dest="auto_dev", action="store_true",
                                default=default_auto_dev, help=argparse.SUPPRESS)
    auto_dev_group.add_argument("--no-auto-dev", dest="auto_dev", action="store_false",
                                help="Disable deterministic scaffolding (default: disabled)")

    args = p.parse_args(argv)

    # Allow per-run GitLab project targeting
    if args.gitlab_project_id:
        os.environ["GITLAB_PROJECT_ID"] = str(args.gitlab_project_id)
    if args.gitlab_project_path:
        os.environ["GITLAB_PROJECT_PATH"] = str(args.gitlab_project_path)

    if not _env("GITLAB_PROJECT_PATH") and not args.gitlab_project_path:
        print("ERROR: GITLAB_PROJECT_PATH is not set (and was not provided via --gitlab-project-path).", flush=True)
        return 2

    base_branch = args.base
    ensure_repo(args.repo, args.repo_url, base_branch, args.dry_run)

    jira = JiraClient()
    agent = WorkflowAgent(jira_client=jira)

    # Jira data
    issue = jira.get_issue(args.jira_key)
    issue_title = (issue.get("summary") or args.jira_key).strip()
    issue_desc = (args.body if args.body is not None else issue.get("description") or "").strip()
    requested_module = parse_requested_module_name(issue_desc)

    # Draft: prefer --draft if provided; else fall back to legacy --no-draft flag
    draft_mr = True if args.draft else (False if args.no_draft else False)  # default non-draft

    cfg = WorkflowConfig(
        jira_key=args.jira_key,
        base_branch=base_branch,
        repo_path=args.repo,
        draft_mr=draft_mr,
        dry_run=args.dry_run,
    )

    # 1) Create branch FIRST
    branch = agent.create_branch(cfg, summary=issue_title)
    print(f"\n>>> Branch ready: {branch}")

    # 2) (Optional legacy) deterministic scaffolding — now NO-OP by default
    if args.auto_dev and not args.dry_run:
        run_auto_dev_on_current_branch(args.jira_key, args.repo, requested_module)

    # 3) (NEW default) LLM patch step — create actual changes before commit
    if args.llm_enabled and not args.dry_run:
        ok = run_llm_patch(args.jira_key, args.repo, provider=args.provider, model=args.model)
        if not ok:
            print("[workflow] WARNING: LLM patch did not apply cleanly. Commit step will continue (may be empty).")

    # 4) Commit & push
    try:
        commit_msg = agent.commit_and_push(
            cfg,
            title=issue_title,
            body=issue_desc,
            jira_ctx=issue,
            branch=branch,
        )
    except Exception as e:  # e.g., nothing to commit
        commit_msg = f"feat: {args.jira_key} — {issue_title}\n\n{issue_desc}\n\nRefs: {args.jira_key}\n"
        print("! Commit message fell back due to:", e)
    print("\n>>> Commit message preview:\n", commit_msg)

    # 5) MR description
    try:
        mr_desc = agent.render_mr_description(cfg, changes="(diff summary to be included)")
    except Exception as e:
        mr_desc = f"Auto-generated MR for {args.jira_key}: {issue_title}\n\nChanges: see diff."
        print("! MR description fell back due to:", e)

    # 6) Open MR (skip in dry-run)
    labels = [s.strip() for s in (args.labels or "").split(',') if s.strip()] or None
    if args.dry_run:
        print("\n[DRY-RUN] Would open MR with:")
        print(json.dumps({
            "title": args.title or f"{args.jira_key}: {issue_title}",
            "description": (mr_desc[:500] + ("…" if len(mr_desc) > 500 else "")),
            "source_branch": branch,
            "target_branch": cfg.base_branch,
            "draft": cfg.draft_mr,
            "labels": labels,
        }, indent=2))
        return 0

    try:
        mr = agent.open_merge_request(
            cfg,
            branch=branch,
            title=args.title or f"{args.jira_key}: {issue_title}",
            description=mr_desc,
            labels=labels,
        )
        print("\n>>> MR created:")
        print(json.dumps({"web_url": mr.get("web_url"), "iid": mr.get("iid")}, indent=2))

        # ---- JIRA breadcrumbs right here ----
        jira_breadcrumbs_on_mr_open(args.jira_key, mr.get("web_url") or "")

    except Exception as e:
        print("! Failed to create MR:", e)
        return 2

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
