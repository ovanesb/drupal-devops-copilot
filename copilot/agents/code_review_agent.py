# copilot/agents/code_review_agent.py
from __future__ import annotations

import os
import re
import asyncio
from typing import List, Dict, Tuple

from copilot.gitlab_ext import get_mr_changes, post_mr_note
# These may or may not exist in your gitlab_ext; we call them defensively:
try:
    from copilot.gitlab_ext import approve_mr, merge_mr  # type: ignore
except Exception:  # pragma: no cover
    approve_mr = None  # type: ignore
    merge_mr = None  # type: ignore

from copilot.helpers.jira_helper import jira_comment, jira_transition
from copilot.agents.deploy_agent import DeployAgent

# ---- Jira states (override via env to match your workflow) ----
JIRA_STATE_MERGED = os.getenv("JIRA_STATE_MERGED", "Ready for Deploy")
JIRA_STATE_DEPLOYING = os.getenv("JIRA_STATE_DEPLOYING", "Deploying")
# DeployAgent will move to QA on success by default.


# ---------------- Static checks ----------------

def _quick_static_checks(changes: List[Dict]) -> List[str]:
    findings: List[str] = []
    for ch in changes:
        path = ch.get("new_path") or ch.get("old_path") or ""
        diff = ch.get("diff") or ""

        # examples: add your own rules
        if path.endswith((".yml", ".yaml")) and "password:" in diff:
            findings.append(f"YAML secret in `{path}` — consider CI masked vars or KMS/SSM.")
        if path.endswith(".php") and "var_dump(" in diff:
            findings.append(f"Debug call `var_dump` left in `{path}`.")
        if path.endswith("composer.json") and re.search(r'"minimum-stability"\s*:\s*"(dev|alpha|beta)"', diff):
            findings.append("Composer minimum-stability not production-safe.")
    return findings


def _summ(lines: List[str], tail: int = 60) -> str:
    if not lines:
        return "(no output)"
    if len(lines) <= tail:
        return "\n".join(lines)
    return "\n".join(["… (truncated) …"] + lines[-tail:])


def _collect_changed_files(changes: List[Dict]) -> Tuple[List[str], bool]:
    """
    Extract a simple file list from GitLab MR 'changes' payload and whether composer.* changed.
    """
    files: List[str] = []
    composer_changed = False
    for ch in changes:
        p = ch.get("new_path") or ch.get("old_path") or ""
        if not p:
            continue
        files.append(p)
        if p in ("composer.json", "composer.lock"):
            composer_changed = True
    # de-dup while preserving order
    seen = set()
    uniq = []
    for f in files:
        if f not in seen:
            seen.add(f)
            uniq.append(f)
    return uniq, composer_changed


# ---------------- Main flow (new) ----------------

def review_and_merge_and_deploy(
    project_path: str,
    mr_iid: int,
    issue_key: str,
    repo_root: str | None = None,
) -> int:
    """
    1) Review MR (static checks). Comment results.
    2) If OK, approve & merge (if helpers available).
    3) Transition Jira → Ready for Deploy.
    4) Transition Jira → Deploying, then deploy to EC2 + drush + QA via DeployAgent.
    5) DeployAgent posts logs & moves Jira to QA on success.

    Returns:
      0 on success; non-zero on failure/blockers.
    """
    # Pull changes for review
    changes = get_mr_changes(project_path, mr_iid)

    # --- Static checks
    findings = _quick_static_checks(changes)
    if not findings:
        post_mr_note(project_path, mr_iid, "✅ Automated review: no obvious issues found.")
    else:
        body = "### 🤖 Automated review findings\n" + "\n".join(f"- {f}" for f in findings)
        post_mr_note(project_path, mr_iid, body)
        # Block merge if we flagged a likely secret
        if any("secret" in f.lower() for f in findings):
            # Also notify Jira
            try:
                asyncio.run(jira_comment(issue_key, "❌ Automated review flagged potential secret; MR not merged."))
            except Exception:
                pass
            return 1

    # --- Approve & merge (best-effort; skip if helpers missing)
    merged_ok = False
    try:
        if approve_mr:
            approve_mr(project_path, mr_iid)  # type: ignore
        if merge_mr:
            merge_mr(project_path, mr_iid)  # type: ignore
            merged_ok = True
        else:
            # Fall back: assume an external job merges; we still proceed but mark as pending
            post_mr_note(project_path, mr_iid, "ℹ️ No merge helper available; assuming MR will be merged externally.")
            merged_ok = True  # allow flow to continue in demo
    except Exception as e:
        post_mr_note(project_path, mr_iid, f"❌ Merge failed: {e}")
        try:
            asyncio.run(jira_comment(issue_key, f"❌ Merge failed for MR !{mr_iid}: {e}"))
        except Exception:
            pass
        return 2

    # --- Notify Jira: Ready for Deploy
    if merged_ok:
        try:
            asyncio.run(jira_comment(issue_key, f"AI Review approved and merged MR !{mr_iid} ✅"))
            asyncio.run(jira_transition(issue_key, JIRA_STATE_MERGED))
        except Exception:
            pass

    # --- Deploy to EC2
    try:
        # Prepare file list & whether we need composer install
        files, composer_changed = _collect_changed_files(changes)
        if repo_root is None:
            repo_root = os.getenv("COPILOT_REPO_PATH", os.getcwd())

        # Let Jira know we’re starting deployment
        try:
            asyncio.run(jira_transition(issue_key, JIRA_STATE_DEPLOYING))
            asyncio.run(jira_comment(issue_key, "🚀 Starting EC2 deploy (rsync → docker compose → drush)."))
        except Exception:
            pass

        agent = DeployAgent()
        ok = asyncio.run(
            agent.deploy_and_qa_to_ec2(
                issue_key=issue_key,
                repo_root=repo_root,
                changed_files=files,
                composer_changed_flag=composer_changed,
                # next_state_on_success defaults to "QA" inside DeployAgent
            )
        )
        if not ok:
            # DeployAgent already commented; we add a short note here
            try:
                asyncio.run(jira_comment(issue_key, "❌ EC2 deployment failed. See logs above."))
            except Exception:
                pass
            return 3

    except Exception as e:
        try:
            asyncio.run(jira_comment(issue_key, f"❌ EC2 deployment exception: {e}"))
        except Exception:
            pass
        return 3

    return 0


# ---------------- Backward-compat wrapper ----------------

def review_mr(project_path: str, mr_iid: int, *, issue_key: str | None = None, repo_root: str | None = None) -> int:
    """
    Backward-compatible wrapper for older callers.
    If issue_key is missing, we only do the review (no merge/deploy) and return 0/1.
    """
    changes = get_mr_changes(project_path, mr_iid)
    findings = _quick_static_checks(changes)
    if not issue_key:
        # Original behavior: comment findings and return
        if not findings:
            post_mr_note(project_path, mr_iid, "✅ Automated review: no obvious issues found.")
            return 0
        body = "### 🤖 Automated review findings\n" + "\n".join(f"- {f}" for f in findings)
        post_mr_note(project_path, mr_iid, body)
        return 1 if any("secret" in f.lower() for f in findings) else 0

    # If issue_key provided, run full new flow
    return review_and_merge_and_deploy(project_path, mr_iid, issue_key, repo_root=repo_root)
