# copilot/gitlab_ext.py
"""
GitLab helpers for the Drupal DevOps Copilot.

- Uses python-gitlab (same as your original file).
- Preserves open_mr(...) exactly as you used it.
- Adds:
    get_mr_changes(project_path|id, mr_iid) -> List[dict]
    post_mr_note(project_path|id, mr_iid, body) -> dict
    approve_mr(project_path|id, mr_iid) -> dict
    merge_mr(project_path|id, mr_iid, ...) -> dict   (robust to version diffs)
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

# Optional .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    import gitlab
    from gitlab import exceptions as gl_ex
except Exception as e:
    raise ImportError("python-gitlab is required. Install with: pip install python-gitlab") from e


DEFAULT_TIMEOUT = int(os.environ.get("GITLAB_HTTP_TIMEOUT", "30"))  # seconds


# -----------------------------------------------------------------------------
# Low-level helpers
# -----------------------------------------------------------------------------

def _client() -> "gitlab.Gitlab":
    url = os.environ.get("GITLAB_BASE_URL") or os.environ.get("GITLAB_URL")
    token = os.environ.get("GITLAB_API_TOKEN") or os.environ.get("GITLAB_TOKEN")
    if not url or not token:
        raise RuntimeError(
            "Missing GitLab credentials. Set GITLAB_BASE_URL & GITLAB_API_TOKEN "
            "(or aliases GITLAB_URL & GITLAB_TOKEN)."
        )
    gl = gitlab.Gitlab(url, private_token=token, per_page=100, timeout=DEFAULT_TIMEOUT)
    gl.auth()
    return gl


def _get_project(gl: "gitlab.Gitlab", project_path_or_id: str | int):
    """
    Load a project by path ("group/sub/project") or numeric id.
    """
    try:
        return gl.projects.get(project_path_or_id, lazy=False)
    except Exception:
        try:
            return gl.projects.get(int(project_path_or_id), lazy=False)
        except Exception as e:
            raise RuntimeError(f"Unable to load project '{project_path_or_id}': {e}") from e


def _get_mr(project, mr_iid: int):
    try:
        return project.mergerequests.get(mr_iid, lazy=False)
    except Exception as e:
        raise RuntimeError(f"Unable to load MR !{mr_iid}: {e}") from e


def _resolve_reviewers(project, reviewers_usernames: List[str]) -> List[int]:
    if not reviewers_usernames:
        return []
    members = []
    page = 1
    while True:
        batch = project.members.list(query=None, page=page, per_page=100, all=False)
        if not batch:
            break
        members.extend(batch)
        page += 1
    username_to_id = {getattr(m, "username", None): getattr(m, "id", None) for m in members}
    return [username_to_id[u] for u in reviewers_usernames if u in username_to_id and username_to_id[u]]


def _find_existing_mr_by_source(project, source: str, target: Optional[str] = None):
    params = {"state": "opened", "source_branch": source, "all": True}
    if target:
        params["target_branch"] = target
    mrs = project.mergerequests.list(**params)
    return mrs[0] if mrs else None


# -----------------------------------------------------------------------------
# MR creation (existing API, kept as-is)
# -----------------------------------------------------------------------------

def open_mr(
    project_path: str | int,
    source: str,
    target: str,
    title: str,
    description: str,
    *,
    labels: Optional[List[str]] = None,
    reviewers: Optional[List[str]] = None,
    remove_source: bool = True,
    draft: bool = True,
) -> str:
    """
    Create (or reuse) a Merge Request and return its web URL.
    - Timeouts are enforced via python-gitlab client.
    - On 409 (existing MR), returns existing MR URL.
    """
    start = time.time()
    gl = _client()
    project = _get_project(gl, project_path)

    payload: Dict[str, Any] = {
        "source_branch": source,
        "target_branch": target,
        "title": f"Draft: {title}" if draft and not title.lower().startswith("draft:") else title,
        "description": description,
        "remove_source_branch": remove_source,
    }
    if labels:
        payload["labels"] = labels

    try:
        mr = project.mergerequests.create(payload)
    except gl_ex.GitlabCreateError as e:
        if getattr(e, "response_code", None) == 409:
            existing = _find_existing_mr_by_source(project, source, target)
            if existing:
                # Try to sync reviewers on the existing MR (best-effort)
                if reviewers:
                    ids = _resolve_reviewers(project, reviewers)
                    if ids:
                        try:
                            existing.reviewer_ids = ids
                            existing.save()
                        except Exception:
                            pass
                return existing.web_url
        raise RuntimeError(f"GitLab MR creation failed: {e}") from e
    except Exception as e:
        raise RuntimeError(f"GitLab API error (timeout={DEFAULT_TIMEOUT}s?): {e}") from e

    if reviewers:
        ids = _resolve_reviewers(project, reviewers)
        if ids:
            try:
                mr.reviewer_ids = ids
                mr.save()
            except Exception:
                pass

    return mr.web_url


# -----------------------------------------------------------------------------
# NEW: helpers needed by code_review_agent
# -----------------------------------------------------------------------------

def get_mr_changes(project_path: str | int, mr_iid: int) -> List[Dict[str, Any]]:
    """
    Return list of change dicts for an MR (each with new_path/old_path/diff/...).
    """
    gl = _client()
    project = _get_project(gl, project_path)
    mr = _get_mr(project, mr_iid)
    # python-gitlab: mr.changes() populates mr.changes (dict with 'changes' key)
    try:
        data = mr.changes()
        if isinstance(data, dict) and "changes" in data:
            return data.get("changes") or []
        if hasattr(mr, "changes") and isinstance(mr.changes, dict):
            return mr.changes.get("changes") or []
    except Exception:
        pass
    # Fallback: refetch & call changes()
    try:
        mr2 = project.mergerequests.get(mr_iid, lazy=False)
        data = mr2.changes()
        if isinstance(data, dict) and "changes" in data:
            return data.get("changes") or []
    except Exception:
        pass
    return []


def post_mr_note(project_path: str | int, mr_iid: int, body: str) -> Dict[str, Any]:
    """
    Post a note (comment) on the MR and return a dict-ish representation.
    """
    gl = _client()
    project = _get_project(gl, project_path)
    mr = _get_mr(project, mr_iid)
    try:
        note = mr.notes.create({"body": body})
        return getattr(note, "attributes", {"body": body})
    except Exception as e:
        raise RuntimeError(f"Failed to post MR note: {e}") from e


def approve_mr(project_path: str | int, mr_iid: int) -> Dict[str, Any]:
    """
    Approve the MR with the current API user (if approvals are enabled).
    """
    gl = _client()
    project = _get_project(gl, project_path)
    mr = _get_mr(project, mr_iid)
    try:
        res = mr.approve()
        return res or {"ok": True}
    except Exception as e:
        # Don’t hard-fail if approvals are not enabled
        return {"ok": False, "error": str(e)}


def merge_mr(
    project_path: str | int,
    mr_iid: int,
    *,
    merge_when_pipeline_succeeds: bool = False,
    should_remove_source_branch: Optional[bool] = None,
    squash: Optional[bool] = None,
    sha: Optional[str] = None,
    merge_commit_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Merge the MR. Tolerant to python-gitlab version differences.
    Treats “already merged / nothing to merge / 405” as success.
    """
    gl = _client()
    project = _get_project(gl, project_path)
    mr = _get_mr(project, mr_iid)

    kwargs: Dict[str, Any] = {
        "merge_when_pipeline_succeeds": merge_when_pipeline_succeeds,
    }
    if should_remove_source_branch is not None:
        kwargs["should_remove_source_branch"] = should_remove_source_branch
    if squash is not None:
        kwargs["squash"] = squash
    if sha is not None:
        kwargs["sha"] = sha
    if merge_commit_message is not None:
        kwargs["merge_commit_message"] = merge_commit_message

    try:
        res = mr.merge(**kwargs)  # python-gitlab call
        return res or {"ok": True}
    except Exception as e:
        msg = str(e).lower()
        # Common cases across server/client versions
        if any(x in msg for x in ("already merged", "nothing to merge", "405")):
            return {"ok": True, "already_merged_or_empty": True}
        # try to inspect MR state
        try:
            mr_refreshed = project.mergerequests.get(mr_iid, lazy=False)
            if getattr(mr_refreshed, "state", "").lower() == "merged":
                return {"ok": True, "already_merged": True}
        except Exception:
            pass
        raise RuntimeError(f"Merge failed: {e}") from e
