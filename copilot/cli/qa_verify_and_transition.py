#!/usr/bin/env python3
from __future__ import annotations

"""
QA Verifier: read staging pipeline QA result, then transition Jira.

What it does
- Finds the pipeline for the MR's target branch (staging), or a specific
  pipeline id if you pass --pipeline-id.
- Checks jobs:
  - qa:smoke-env (reads artifact qa_report.txt)
  - deploy:staging (best-effort check)
- PASS if:
  - pipeline == success
  - qa:smoke-env == success
  - qa_report.txt contains 'OK'
- On PASS: transition Jira with JIRA_TRANSITION_ON_QA_PASS (default 'READY FOR RELEASE')
- On FAIL: transition Jira with JIRA_TRANSITION_ON_QA_FAIL (default 'IN PROGRESS, TO DO')
- Adds an MR note and label ('qa-passed' / 'qa-failed') when MR is accessible.

Env required
- GITLAB_API_TOKEN (api scope), optional GITLAB_BASE_URL (default https://gitlab.com)
- (Fallback) GITLAB_PROJECT_PATH if URL parse ever fails

Jira (optional, for transitions/comments)
- JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN
- JIRA_TRANSITION_ON_QA_PASS (default 'READY FOR RELEASE')
- JIRA_TRANSITION_ON_QA_FAIL (default 'IN PROGRESS, TO DO')

Usage
  python copilot/cli/qa_verify_and_transition.py "<MR_URL>"
  # Options:
  #   --pipeline-id <id>   (use a specific pipeline)
  #   --target staging     (fallback if MR not accessible)
  #   --issue CCS-123      (explicit Jira key(s) if needed)
  #   --timeout-secs 900   --poll-secs 5 (wait if pipeline still running)
"""

import argparse
import os
import re
import sys
import time
from typing import Optional, List, Dict
from urllib.parse import urlparse, quote_plus

# Optional dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import requests


# ---------- env & small utils ----------

def _env(name: str, *fallbacks: str, default: Optional[str] = None) -> Optional[str]:
    for k in (name, *fallbacks):
        v = os.getenv(k)
        if v not in (None, ""):
            return v
    return default

def gl_host() -> str:
    return (_env("GITLAB_BASE_URL", "GITLAB_HOST", default="https://gitlab.com")
            or "https://gitlab.com").rstrip("/")

def gl_token() -> str:
    t = _env("GITLAB_API_TOKEN", "GITLAB_TOKEN")
    if not t:
        raise RuntimeError("GITLAB_API_TOKEN is required")
    return t

def hdr(token: str) -> Dict[str, str]:
    return {"PRIVATE-TOKEN": token}

def parse_project_path_from_mr_url(mr_url: str) -> Optional[str]:
    """
    From https://gitlab.com/group/sub/group/proj/-/merge_requests/123
    return 'group/sub/group/proj'.
    """
    try:
        u = urlparse(mr_url)
        parts = [p for p in u.path.split("/") if p]
        if "merge_requests" in parts:
            mr_idx = parts.index("merge_requests")
            if mr_idx >= 1 and parts[mr_idx - 1] == "-":
                proj_parts = parts[: mr_idx - 1]
            else:
                proj_parts = parts[: mr_idx]
            if proj_parts:
                return "/".join(proj_parts)
        if len(parts) >= 2:
            return "/".join(parts[:2])
    except Exception:
        pass
    return None

def mr_iid_from_url(url: str) -> Optional[int]:
    m = re.search(r"/merge_requests/(\d+)", url)
    return int(m.group(1)) if m else None

def extract_issue_keys(*texts: str) -> list[str]:
    keys: set[str] = set()
    for t in texts:
        if not t:
            continue
        keys.update(re.findall(r"[A-Z]+-\d+", t))
    return sorted(keys)


# ---------- GitLab API (by numeric project ID) ----------

def get_project_id(project_path: str, host: str, token: str) -> int:
    pid = quote_plus(project_path)
    url = f"{host}/api/v4/projects/{pid}"
    r = requests.get(url, headers=hdr(token), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(
            f"Resolve project id for '{project_path}': {r.status_code} {r.text}"
        )
    return int(r.json()["id"])

def get_mr_details(project_id: int, mr_iid: int, host: str, token: str) -> dict:
    url = f"{host}/api/v4/projects/{project_id}/merge_requests/{mr_iid}"
    r = requests.get(url, headers=hdr(token), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Get MR details: {r.status_code} {r.text}")
    return r.json()

def add_mr_note(project_id: int, mr_iid: int, body: str, host: str, token: str) -> None:
    url = f"{host}/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes"
    r = requests.post(url, headers=hdr(token), data={"body": body}, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Add MR note: {r.status_code} {r.text}")

def get_mr_labels(project_id: int, mr_iid: int, host: str, token: str) -> list[str]:
    url = f"{host}/api/v4/projects/{project_id}/merge_requests/{mr_iid}"
    r = requests.get(url, headers=hdr(token), timeout=30)
    r.raise_for_status()
    return r.json().get("labels") or []

def set_mr_labels(project_id: int, mr_iid: int, labels: list[str],
                  host: str, token: str) -> list[str]:
    url = f"{host}/api/v4/projects/{project_id}/merge_requests/{mr_iid}"
    r = requests.put(url, headers=hdr(token), data={"labels": ",".join(labels)},
                     timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Set MR labels: {r.status_code} {r.text}")
    return r.json().get("labels") or []

def list_pipelines_for_ref(project_id: int, ref: str, host: str, token: str,
                           per_page: int = 5) -> list[dict]:
    url = f"{host}/api/v4/projects/{project_id}/pipelines"
    params = {"ref": ref, "per_page": per_page, "order_by": "id", "sort": "desc"}
    r = requests.get(url, headers=hdr(token), params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def get_pipeline(project_id: int, pipeline_id: int, host: str, token: str) -> dict:
    url = f"{host}/api/v4/projects/{project_id}/pipelines/{pipeline_id}"
    r = requests.get(url, headers=hdr(token), timeout=30)
    r.raise_for_status()
    return r.json()

def list_pipeline_jobs(project_id: int, pipeline_id: int, host: str,
                       token: str) -> list[dict]:
    url = f"{host}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs"
    r = requests.get(url, headers=hdr(token), timeout=30)
    r.raise_for_status()
    return r.json()

def download_job_artifact_file(project_id: int, job_id: int, path: str,
                               host: str, token: str) -> Optional[str]:
    """
    GET /projects/:id/jobs/:job_id/artifacts/:artifact_path
    Returns text content if available, else None.
    """
    url = f"{host}/api/v4/projects/{project_id}/jobs/{job_id}/artifacts/{path}"
    r = requests.get(url, headers=hdr(token), timeout=30)
    if r.status_code == 200:
        return r.text
    return None


# ---------- Jira (reuse helper if available) ----------

def jira_transition(keys: list[str], names_csv: str) -> None:
    names = [s.strip() for s in (names_csv or "").split(",") if s.strip()]
    if not keys or not names:
        return
    try:
        from copilot.helpers.jira_helper import transition_issue_to_first_matching  # type: ignore
        for k in keys:
            try:
                ok = transition_issue_to_first_matching(k, names)
                print(f"Jira {k}: transition -> {names}: "
                      f"{'applied' if ok else 'no match'}")
            except Exception as e:
                print(f"Jira {k}: transition failed: {e}")
    except Exception as e:
        print(f"Jira helper unavailable; skipping transitions: {e}")

def jira_comment(keys: list[str], comment: str) -> None:
    if not keys or not comment:
        return
    try:
        from copilot.helpers.jira_helper import add_comment  # type: ignore
        for k in keys:
            try:
                add_comment(k, comment, adf=True)
                print(f"Jira {k}: comment added.")
            except Exception as e:
                print(f"Jira {k}: comment failed: {e}")
    except Exception as e:
        print(f"Jira helper unavailable; skipping comments: {e}")


# ---------- main ----------

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Verify staging QA and transition Jira")
    ap.add_argument("mr_url", help="GitLab MR URL")
    ap.add_argument("--pipeline-id", type=int, default=0,
                    help="Use this pipeline id (optional)")
    ap.add_argument("--timeout-secs", type=int, default=900,
                    help="Wait if pipeline is running")
    ap.add_argument("--poll-secs", type=int, default=5,
                    help="Polling interval seconds")
    # Fallbacks when MR lookup fails
    ap.add_argument("--target", default="staging",
                    help="Fallback target branch if MR not accessible")
    ap.add_argument("--issue", action="append", default=[],
                    help="Explicit Jira key(s)")
    # Transitions
    ap.add_argument("--on-pass",
                    default=os.getenv("JIRA_TRANSITION_ON_QA_PASS",
                                      "READY FOR RELEASE"),
                    help="Jira transition(s) when QA passes (CSV)")
    ap.add_argument("--on-fail",
                    default=os.getenv("JIRA_TRANSITION_ON_QA_FAIL",
                                      "IN PROGRESS, TO DO"),
                    help="Jira transition(s) when QA fails (CSV)")
    args = ap.parse_args(argv)

    host = gl_host()
    token = gl_token()

    # Resolve project path & ID
    url_project_path = (parse_project_path_from_mr_url(args.mr_url)
                        or _env("GITLAB_PROJECT_PATH"))
    if not url_project_path:
        print("Could not determine project path from URL or env.")
        return 1
    print(f">>> Using project_path: {url_project_path}")
    project_id = get_project_id(url_project_path, host, token)
    print(f">>> Resolved project_id: {project_id}")

    # MR
    mr_iid = mr_iid_from_url(args.mr_url)
    if not mr_iid:
        print("Could not parse MR IID from URL.")
        return 1

    # Try to read MR for source/target & keys
    source = target = title = ""
    mr_accessible = True
    try:
        info = get_mr_details(project_id, mr_iid, host, token)
        source = info.get("source_branch") or ""
        target = info.get("target_branch") or ""
        title = info.get("title") or ""
        print(f">>> MR {mr_iid}: {source} -> {target}")
    except Exception as e:
        mr_accessible = False
        print(f"MR details unavailable ({e}). Falling back to --target="
              f"'{args.target}'.")
        target = args.target

    # Jira keys
    keys = extract_issue_keys(source, title, args.mr_url)
    keys = sorted(set(keys + (args.issue or [])))
    if keys:
        print(f">>> Jira keys: {', '.join(keys)}")
    else:
        print(">>> No Jira keys found (Jira actions will be skipped).")

    # Determine pipeline
    pipeline = None
    if args.pipeline_id:
        pipeline = {"id": args.pipeline_id}
    else:
        ps = list_pipelines_for_ref(project_id, target, host, token=token)
        pipeline = ps[0] if ps else None
    if not pipeline:
        print("No pipeline found for target branch.")
        return 1

    pid = int(pipeline["id"])
    web_url = pipeline.get("web_url") or f"{host}/{url_project_path}/-/pipelines/{pid}"
    print(f">>> Checking pipeline #{pid}: {web_url}")

    # Wait if running
    deadline = time.time() + args.timeout_secs
    while True:
        p = get_pipeline(project_id, pid, host, token)
        status = p.get("status")
        print(f">>> Pipeline status: {status}")
        if status in ("success", "failed", "canceled", "skipped", "manual"):
            break
        if time.time() > deadline:
            print("Timed out waiting for pipeline.")
            return 1
        time.sleep(args.poll_secs)

    # Inspect jobs
    jobs = list_pipeline_jobs(project_id, pid, host, token)
    name_status = {j.get("name"): j.get("status") for j in jobs}
    print(f">>> Job statuses: {name_status}")

    qa_job = next((j for j in jobs if j.get("name") == "qa:smoke-env"), None)
    qa_txt = None
    if qa_job:
        qa_txt = download_job_artifact_file(project_id, int(qa_job["id"]),
                                            "qa_report.txt", host, token)
    qa_ok_flag = bool(qa_txt and "OK" in qa_txt)

    # Decide pass/fail
    passed = (
        (p.get("status") == "success")
        and (name_status.get("qa:smoke-env") == "success")
        and qa_ok_flag
    )
    print(f">>> QA result: {'PASS' if passed else 'FAIL'}")

    # Jira actions
    if keys:
        if passed:
            jira_transition(keys, args.on_pass)
            jira_comment(keys, f"QA passed on staging. Pipeline: {web_url}")
        else:
            jira_transition(keys, args.on_fail)
            jira_comment(keys, f"QA failed on staging. Pipeline: {web_url}")

    # MR annotations (if accessible)
    if mr_accessible:
        try:
            lbls = set(get_mr_labels(project_id, mr_iid, host, token))
            lbls.add("qa-passed" if passed else "qa-failed")
            set_mr_labels(project_id, mr_iid, sorted(lbls), host, token)
            note = ("✅ QA passed. " if passed else "❌ QA failed. ") + web_url
            add_mr_note(project_id, mr_iid, note, host, token)
        except Exception:
            pass

    print("Done.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
