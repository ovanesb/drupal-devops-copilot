#!/usr/bin/env python3
from __future__ import annotations

"""
AI Agent: ensure staging deploy, wait for success, then move Jira to READY FOR QA.

- Parses project path from the MR URL and resolves numeric project ID
- Ensures/monitors a pipeline on the target ref (--ensure-pipeline)
- Verifies key jobs (deploy:staging, qa:smoke-env)
- Transitions Jira to READY FOR QA and comments the pipeline URL
- Adds MR note and 'ready-for-qa' label (best-effort)

Env:
- GITLAB_API_TOKEN (required), GITLAB_BASE_URL (default https://gitlab.com)
- JIRA_BASE_URL or JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN (optional for Jira)
- JIRA_READY_FOR_QA_NAME (default "READY FOR QA")
"""

import argparse, os, re, sys, time, requests
from typing import Optional, List, Dict
from urllib.parse import urlparse, quote_plus

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

def _env(name: str, *fallbacks: str, default: Optional[str] = None) -> Optional[str]:
    for k in (name, *fallbacks):
        v = os.getenv(k)
        if v not in (None, ""):
            return v
    return default

def gl_host() -> str:
    return (_env("GITLAB_BASE_URL", "GITLAB_HOST", default="https://gitlab.com") or "https://gitlab.com").rstrip("/")

def gl_token() -> str:
    t = _env("GITLAB_API_TOKEN", "GITLAB_TOKEN")
    if not t:
        raise RuntimeError("GITLAB_API_TOKEN is required")
    return t

def hdr(token: str) -> Dict[str, str]:
    return {"PRIVATE-TOKEN": token}

def parse_project_path_from_mr_url(mr_url: str) -> Optional[str]:
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

# --- GitLab (by numeric project ID) ---

def get_project_id(project_path: str, host: str, token: str) -> int:
    pid = quote_plus(project_path)
    url = f"{host}/api/v4/projects/{pid}"
    r = requests.get(url, headers=hdr(token), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Resolve project id for '{project_path}': {r.status_code} {r.text}")
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

def set_mr_labels(project_id: int, mr_iid: int, labels: list[str], host: str, token: str) -> list[str]:
    url = f"{host}/api/v4/projects/{project_id}/merge_requests/{mr_iid}"
    r = requests.put(url, headers=hdr(token), data={"labels": ",".join(labels)}, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Set MR labels: {r.status_code} {r.text}")
    return r.json().get("labels") or []

def list_pipelines_for_ref(project_id: int, ref: str, host: str, token: str, per_page: int = 5) -> list[dict]:
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

def create_pipeline(project_id: int, ref: str, host: str, token: str, variables: Optional[dict] = None) -> dict:
    url = f"{host}/api/v4/projects/{project_id}/pipelines"
    data = {"ref": ref}
    if variables:
        for k, v in variables.items():
            data[f"variables[{k}]"] = v
    r = requests.post(url, headers=hdr(token), data=data, timeout=30)
    if r.status_code not in (201, 200):
        raise RuntimeError(f"Create pipeline: {r.status_code} {r.text}")
    return r.json()

def list_pipeline_jobs(project_id: int, pipeline_id: int, host: str, token: str) -> list[dict]:
    url = f"{host}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs"
    r = requests.get(url, headers=hdr(token), timeout=30)
    r.raise_for_status()
    return r.json()

# --- Jira (reuse helper if available) ---

def jira_transition(keys: list[str], name: str) -> None:
    if not keys or not name:
        return
    try:
        from copilot.helpers.jira_helper import transition_issue_to_first_matching  # type: ignore
        for k in keys:
            try:
                ok = transition_issue_to_first_matching(k, [name])
                print(f"Jira {k}: transition -> {name}: {'applied' if ok else 'no match'}")
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

# --- main ---

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Ensure staging deploy, wait, then move Jira to READY FOR QA")
    ap.add_argument("mr_url", help="GitLab MR URL")
    ap.add_argument("--ensure-pipeline", action="store_true", help="Create a pipeline on target ref if none found")
    ap.add_argument("--timeout-secs", type=int, default=900, help="Max seconds to wait for pipeline")
    ap.add_argument("--poll-secs", type=int, default=5, help="Polling interval seconds")
    ap.add_argument("--ready-name", default=os.getenv("JIRA_READY_FOR_QA_NAME", "READY FOR QA"),
                    help="Jira transition name to apply on success")
    ap.add_argument("--target", default="staging", help="Fallback target branch if MR not accessible")
    ap.add_argument("--issue", action="append", default=[], help="Explicit Jira key(s)")
    args = ap.parse_args(argv)

    host = gl_host()
    token = gl_token()

    url_project_path = parse_project_path_from_mr_url(args.mr_url) or _env("GITLAB_PROJECT_PATH")
    if not url_project_path:
        print("Could not determine project path from URL or env.")
        return 1

    print(f">>> Using project_path: {url_project_path}")
    project_id = get_project_id(url_project_path, host, token)
    print(f">>> Resolved project_id: {project_id}")

    mr_iid = mr_iid_from_url(args.mr_url)
    if not mr_iid:
        print("Could not parse MR IID from URL.")
        return 1

    # Try MR details; if 404, fallback to --target/--issue and skip MR annotations
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
        print(f"MR details unavailable ({e}). Falling back to --target='{args.target}'.")
        target = args.target

    # Jira keys
    keys = extract_issue_keys(source, title, args.mr_url)
    keys = sorted(set(keys + (args.issue or [])))
    if keys:
        print(f">>> Jira keys: {', '.join(keys)}")
    else:
        print(">>> No Jira keys found (will skip Jira transition if none).")

    # Find or create pipeline on target ref
    pipelines = list_pipelines_for_ref(project_id, target, host, token)
    pipeline = pipelines[0] if pipelines else None
    if not pipeline and args.ensure_pipeline:
        print(">>> No pipeline found; creating one...")
        pipeline = create_pipeline(project_id, target, host, token)
    if not pipeline:
        print("No pipeline found for target branch and --ensure-pipeline not set.")
        return 1

    pid = int(pipeline["id"])
    web_url = pipeline.get("web_url") or f"{host}/{url_project_path}/-/pipelines/{pid}"
    print(f">>> Monitoring pipeline #{pid}: {web_url}")

    deadline = time.time() + args.timeout_secs
    last_status = ""
    while True:
        p = get_pipeline(project_id, pid, host, token)
        status = p.get("status")
        if status != last_status:
            print(f">>> Pipeline status: {status}")
            last_status = status
        if status in ("success", "failed", "canceled", "skipped", "manual"):
            break
        if time.time() > deadline:
            print("Timed out waiting for pipeline.")
            return 1
        time.sleep(args.poll_sects if hasattr(args, 'poll_sects') else args.poll_secs)

    if status != "success":
        print(f"Pipeline finished with status: {status}")
        if mr_accessible:
            try:
                add_mr_note(project_id, mr_iid,
                            f"Staging deploy pipeline finished: **{status}**\n{web_url}",
                            host, token)
            except Exception:
                pass
        return 1

    # Verify jobs (best-effort)
    try:
        jobs = list_pipeline_jobs(project_id, pid, host, token)
    except Exception:
        jobs = []
    names = {j.get("name"): j.get("status") for j in jobs}
    print(f">>> Job statuses: {names}")
    ok_deploy = names.get("deploy:staging") == "success"
    ok_qa = names.get("qa:smoke-env") == "success"
    if not (ok_deploy and ok_qa):
        print("Warning: expected jobs not both successful (continuing).")

    # Jira transition + comment
    comment = f"Staging deploy successful. Pipeline: {web_url}"
    if keys:
        jira_transition(keys, args.ready_name)
        jira_comment(keys, comment)

    # MR annotations if accessible
    if mr_accessible:
        try:
            lbls = set(get_mr_labels(project_id, mr_iid, host, token))
            lbls.add("ready-for-qa")
            set_mr_labels(project_id, mr_iid, sorted(lbls), host, token)
            add_mr_note(project_id, mr_iid,
                        f"✅ Staging deploy succeeded. Marked Jira **{args.ready_name}**.\n{web_url}",
                        host, token)
        except Exception:
            pass

    print("Done.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
