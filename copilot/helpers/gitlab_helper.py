import os
import json
import requests
import urllib.parse
from typing import Any, Optional

class GitLabMRError(Exception):
    pass

def _env(name: str, *fallbacks: str, default: Optional[str] = None) -> Optional[str]:
    for k in (name, *fallbacks):
        v = os.getenv(k)
        if v not in (None, ""):
            return v
    return default

def _auth_headers(token: str) -> dict:
    return {"PRIVATE-TOKEN": token}

def _host() -> str:
    return (_env("GITLAB_BASE_URL", "GITLAB_HOST", default="https://gitlab.com") or "https://gitlab.com").rstrip("/")

def _token() -> str:
    tok = _env("GITLAB_API_TOKEN", "GITLAB_TOKEN")
    if not tok:
        raise GitLabMRError("Missing GitLab token. Set GITLAB_API_TOKEN (or GITLAB_TOKEN).")
    return tok

def _pid_from_path(project_path: str) -> str:
    return urllib.parse.quote_plus(project_path)

def resolve_project_id(project_path: str, *, host: Optional[str] = None, token: Optional[str] = None) -> int:
    """
    Resolve numeric project id using /projects/:path. Uses env GITLAB_PROJECT_ID if present.
    """
    if os.getenv("GITLAB_PROJECT_ID"):
        try:
            return int(os.getenv("GITLAB_PROJECT_ID", "0"))
        except ValueError:
            pass
    host = host or _host()
    token = token or _token()
    pid = _pid_from_path(project_path)
    url = f"{host}/api/v4/projects/{pid}"
    r = requests.get(url, headers=_auth_headers(token), timeout=30)
    if r.status_code != 200:
        raise GitLabMRError(f"Failed to resolve project id: {r.status_code} {r.text}")
    return int(r.json().get("id"))

def open_mr(
    project_path: str,
    source_branch: str,
    target_branch: str,
    title: str,
    description: str = "",
    remove_source_branch: bool = True,
    draft: bool = True,
    labels=None,
    assignees: Optional[list[int]] = None,
    reviewers: Optional[list[int]] = None,
    token: Optional[str] = None,
    host: str = "",
) -> str:
    """
    Create a Merge Request and return its web URL.
    Supports labels, assignee_ids, reviewer_ids.
    """
    token = token or _token()
    host = (host or _host()).rstrip("/")

    final_title = title
    if draft and not title.lower().startswith("draft:"):
        final_title = f"Draft: {title}"

    pid = _pid_from_path(project_path)
    url = f"{host}/api/v4/projects/{pid}/merge_requests"

    payload: dict[str, Any] = {
        "source_branch": source_branch,
        "target_branch": target_branch,
        "title": final_title,
        "description": description or "",
        "remove_source_branch": bool(remove_source_branch),
    }

    if labels:
        if isinstance(labels, (list, tuple, set)):
            payload["labels"] = ",".join(str(x) for x in labels)
        else:
            payload["labels"] = str(labels)

    if assignees:
        payload["assignee_ids"] = assignees
    if reviewers:
        payload["reviewer_ids"] = reviewers

    resp = requests.post(url, headers=_auth_headers(token), data=payload, timeout=30)
    if resp.status_code not in (200, 201):
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise GitLabMRError(f"Failed to open MR ({resp.status_code}): {detail}")

    data = resp.json()
    web_url = data.get("web_url")
    if not web_url:
        raise GitLabMRError(f"MR created but no web_url in response: {json.dumps(data)[:500]}")
    return web_url

def find_existing_mr(project_path: str, source_branch: str, target_branch: str,
                     host: Optional[str] = None, token: Optional[str] = None) -> Optional[str]:
    """
    Return web_url of an open MR with the same source/target, or None if not found.
    """
    token = token or _token()
    host = (host or _host()).rstrip("/")
    pid = _pid_from_path(project_path)
    url = (f"{host}/api/v4/projects/{pid}/merge_requests"
           f"?state=opened&source_branch={urllib.parse.quote_plus(source_branch)}"
           f"&target_branch={urllib.parse.quote_plus(target_branch)}")
    resp = requests.get(url, headers=_auth_headers(token), timeout=30)
    if resp.status_code != 200:
        return None
    arr = resp.json() or []
    if not arr:
        return None
    return arr[0].get("web_url")

def mr_iid_from_url(url: str) -> Optional[int]:
    """
    Extract IID from typical MR URL: .../merge_requests/<iid>
    """
    try:
        parts = url.rstrip("/").split("/")
        idx = parts.index("merge_requests")
        return int(parts[idx+1])
    except Exception:
        return None

def add_mr_note(project_path: str, mr_iid: int, body: str,
                *, host: Optional[str] = None, token: Optional[str] = None) -> None:
    token = token or _token()
    host = (host or _host()).rstrip("/")
    pid = _pid_from_path(project_path)
    url = f"{host}/api/v4/projects/{pid}/merge_requests/{mr_iid}/notes"
    r = requests.post(url, headers=_auth_headers(token), data={"body": body}, timeout=30)
    if r.status_code not in (200, 201):
        raise GitLabMRError(f"Failed to add MR note: {r.status_code} {r.text}")

def post_mr_comment(project_path: str, mr_iid: int, body: str,
                    *, host: Optional[str] = None, token: Optional[str] = None) -> dict:
    """
    Create a note (comment) on a merge request and return the created note JSON.
    (Some callers prefer JSON; `add_mr_note` returns None on success.)
    """
    token = token or _token()
    host = (host or _host()).rstrip("/")
    pid = _pid_from_path(project_path)
    url = f"{host}/api/v4/projects/{pid}/merge_requests/{mr_iid}/notes"
    r = requests.post(url, headers=_auth_headers(token), json={"body": body}, timeout=30)
    if r.status_code not in (200, 201):
        raise GitLabMRError(f"Failed to post MR comment: {r.status_code} {r.text}")
    return r.json()

def get_mr_details(project_path: str, mr_iid: int,
                   *, host: Optional[str] = None, token: Optional[str] = None) -> dict:
    token = token or _token()
    host = (host or _host()).rstrip("/")
    pid = _pid_from_path(project_path)
    url = f"{host}/api/v4/projects/{pid}/merge_requests/{mr_iid}"
    r = requests.get(url, headers=_auth_headers(token), timeout=30)
    if r.status_code != 200:
        raise GitLabMRError(f"Failed to get MR details: {r.status_code} {r.text}")
    return r.json()

def add_mr_labels(project_path: str, mr_iid: int, labels_to_add: list[str],
                  *, host: Optional[str] = None, token: Optional[str] = None) -> list[str]:
    """
    Append labels to an MR (preserving existing). Returns the final label list.
    """
    token = token or _token()
    host = (host or _host()).rstrip("/")
    pid = _pid_from_path(project_path)

    # Get existing labels
    details = get_mr_details(project_path, mr_iid, host=host, token=token)
    existing = details.get("labels") or []
    final = sorted(set([*existing, *[s for s in labels_to_add if s]]))

    # Update labels
    url = f"{host}/api/v4/projects/{pid}/merge_requests/{mr_iid}"
    r = requests.put(url, headers=_auth_headers(token), data={"labels": ",".join(final)}, timeout=30)
    if r.status_code not in (200, 201):
        raise GitLabMRError(f"Failed to update MR labels: {r.status_code} {r.text}")
    return final

# Back-compat alias: some code imports add_labels_to_mr
def add_labels_to_mr(project_path: str, mr_iid: int, labels_to_add: list[str],
                     *, host: Optional[str] = None, token: Optional[str] = None) -> list[str]:
    return add_mr_labels(project_path, mr_iid, labels_to_add, host=host, token=token)

def merge_mr(project_path: str, mr_iid: int, *,
             merge_when_pipeline_succeeds: bool = True,
             squash: bool = True,
             sha: Optional[str] = None,
             host: Optional[str] = None,
             token: Optional[str] = None) -> dict:
    token = token or _token()
    host = (host or _host()).rstrip("/")
    pid = _pid_from_path(project_path)
    url = f"{host}/api/v4/projects/{pid}/merge_requests/{mr_iid}/merge"
    data = {
        "merge_when_pipeline_succeeds": str(bool(merge_when_pipeline_succeeds)).lower(),
        "squash": str(bool(squash)).lower(),
    }
    if sha:
        data["sha"] = sha
    r = requests.put(url, headers=_auth_headers(token), data=data, timeout=30)
    if r.status_code not in (200, 201, 202):
        raise GitLabMRError(f"Failed to merge MR: {r.status_code} {r.text}")
    return r.json()

def list_mr_pipelines(project_path: str, mr_iid: int,
                      *, host: Optional[str] = None, token: Optional[str] = None) -> list[dict]:
    token = token or _token()
    host = (host or _host()).rstrip("/")
    pid = _pid_from_path(project_path)
    url = f"{host}/api/v4/projects/{pid}/merge_requests/{mr_iid}/pipelines"
    r = requests.get(url, headers=_auth_headers(token), timeout=30)
    if r.status_code != 200:
        raise GitLabMRError(f"Failed to list MR pipelines: {r.status_code} {r.text}")
    return r.json() or []

def get_pipeline(project_path: str, pipeline_id: int,
                 *, host: Optional[str] = None, token: Optional[str] = None) -> dict:
    token = token or _token()
    host = (host or _host()).rstrip("/")
    pid = _pid_from_path(project_path)
    url = f"{host}/api/v4/projects/{pid}/pipelines/{pipeline_id}"
    r = requests.get(url, headers=_auth_headers(token), timeout=30)
    if r.status_code != 200:
        raise GitLabMRError(f"Failed to get pipeline: {r.status_code} {r.text}")
    return r.json()

def trigger_pipeline(project_path: str, ref: str, variables: Optional[dict] = None,
                     *, host: Optional[str] = None, token: Optional[str] = None) -> dict:
    """
    Trigger a pipeline using a trigger token (requires GITLAB_TRIGGER_TOKEN and numeric project id).
    If GITLAB_PROJECT_ID is missing, this resolves it.
    """
    trigger_token = os.getenv("GITLAB_TRIGGER_TOKEN")
    if not trigger_token:
        raise GitLabMRError("GITLAB_TRIGGER_TOKEN is required for triggering pipelines.")
    host = (host or _host()).rstrip("/")
    token = token or _token()
    project_id = int(os.getenv("GITLAB_PROJECT_ID") or resolve_project_id(project_path, host=host, token=token))
    url = f"{host}/api/v4/projects/{project_id}/trigger/pipeline"
    data = {"token": trigger_token, "ref": ref}
    if variables:
        for k, v in variables.items():
            data[f"variables[{k}]"] = v
    r = requests.post(url, data=data, timeout=30)
    if r.status_code not in (200, 201, 202):
        raise GitLabMRError(f"Failed to trigger pipeline: {r.status_code} {r.text}")
    return r.json()

# ---------------- Mergeability helper ----------------

def can_merge_mr(project_path: str, mr_iid: int,
                 *, host: Optional[str] = None, token: Optional[str] = None) -> tuple[bool, str]:
    """
    Best-effort check whether the current token user can merge the MR *now*.
    Returns (ok, reason) where reason is a short diagnostic string.
    """
    details = get_mr_details(project_path, mr_iid, host=host, token=token)

    # permission check
    user_can_merge = bool((details.get("user") or {}).get("can_merge", False))
    if not user_can_merge:
        return False, "user.can_merge=false"

    # state check
    state = (details.get("state") or "").lower()
    if state != "opened":
        return False, f"state={state}"

    # draft / WIP check
    if details.get("work_in_progress") or details.get("draft"):
        return False, "draft_or_wip=true"

    # blocking discussions
    if details.get("blocking_discussions_resolved") is False:
        return False, "blocking_discussions_unresolved"

    # detailed merge status
    dms = details.get("detailed_merge_status") or details.get("merge_status")
    # Consider acceptable for MWPS:
    # - mergeable: ready to go
    # - ci_must_pass / pipeline_must_succeed: allow MWPS path
    ok_statuses = {"mergeable", "ci_must_pass", "pipeline_must_succeed"}
    if str(dms).lower() in ok_statuses:
        return True, f"detailed_merge_status={dms}"

    return False, f"detailed_merge_status={dms}"
