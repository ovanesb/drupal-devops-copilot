#!/usr/bin/env python3
from __future__ import annotations

"""
One-shot workflow:

1) Create branch, scaffold, push, and open MR
   -> runs `copilot-workflow` (env-driven; no flags needed)
2) AI review & auto-merge (NO deploy here)
   -> runs `copilot-ai-review-merge --auto-merge --verbose`
   (we record pre-merge SHA and wait for branch SHA to change)
3) Deploy to EC2, waiting for the exact new SHA
   -> runs `./scripts/deploy_to_ec2.sh` with EXPECT_SHA/timeout env
4) Run QA on EC2
   -> runs `copilot-qa-ec2 <ISSUE-KEY>`

Env it reads (all optional; sensible defaults where possible):
- COPILOT_REPO_PATH        (used by copilot-workflow; default handled there)
- GITLAB_PROJECT_PATH      (e.g., "user/group/myproject")  <-- required for SHA wait
- GITLAB_API_TOKEN         (needed for SHA wait; if missing, deploy runs w/o EXPECT_SHA)
- GITLAB_BASE_URL          (default: https://gitlab.com)
- DEPLOY_BRANCH            (default: staging)
- DRUSH_URI                (default: http://localhost)
- DEPLOY_GIT_REMOTE_URL    (default: git@gitlab.com:<GITLAB_PROJECT_PATH>.git)
- EXPECT_TIMEOUT           (default: 300 seconds)
- EXPECT_INTERVAL          (default: 5 seconds)
"""

import os
import re
import sys
import time
import json
import subprocess
from typing import Optional

# optional dotenv
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# ---------------- small utils ----------------

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v not in (None, "") else default

def run(cmd: list[str], cwd: Optional[str] = None, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    """Run command, print output, raise on nonzero."""
    print("$ " + " ".join(cmd))
    cp = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)
    if cp.stdout:
        sys.stdout.write(cp.stdout)
    if cp.stderr:
        sys.stderr.write(cp.stderr)
    cp.check_returncode()
    return cp

def parse_mr_url_from_text(s: str) -> Optional[str]:
    """
    Try to extract an MR web URL from mixed stdout/stderr text.
    1) Prefer a JSON object with 'web_url'
    2) Fallback to any URL matching '/-/merge_requests/<iid>'
    """
    # try to find JSON blobs and pick web_url
    for m in re.findall(r"\{.*?\}", s, flags=re.DOTALL):
        try:
            obj = json.loads(m)
            u = obj.get("web_url")
            if isinstance(u, str) and "/-/merge_requests/" in u:
                return u
        except Exception:
            pass
    # fallback: regex URL
    m = re.search(r"https?://[^\s]+/-/merge_requests/\d+", s)
    return m.group(0) if m else None

# ---------------- GitLab helpers ----------------

def gl_host() -> str:
    return (_env("GITLAB_BASE_URL", "https://gitlab.com") or "https://gitlab.com").rstrip("/")

def gl_token() -> Optional[str]:
    return _env("GITLAB_API_TOKEN")

def parse_project_path_from_mr_url(mr_url: str) -> Optional[str]:
    """
    https://gitlab.com/group/sub/proj/-/merge_requests/123 -> group/sub/proj
    """
    try:
        base, _ = mr_url.split("/-/merge_requests/", 1)
        after_host = base.split("://", 1)[1].split("/", 1)[1]  # group/sub/proj
        return after_host.strip("/")
    except Exception:
        return None

def get_project_id(project_path: str) -> int:
    import requests
    pid = requests.utils.quote(project_path, safe="")
    url = f"{gl_host()}/api/v4/projects/{pid}"
    headers = {"PRIVATE-TOKEN": gl_token() or ""}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return int(r.json()["id"])

def get_branch_sha(project_id: int, branch: str) -> Optional[str]:
    import requests
    url = f"{gl_host()}/api/v4/projects/{project_id}/repository/branches/{branch}"
    headers = {"PRIVATE-TOKEN": gl_token() or ""}
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        return None
    return (r.json().get("commit") or {}).get("id")

def wait_for_branch_sha(project_id: int, branch: str, prev_sha: Optional[str],
                        timeout: int, interval: int) -> Optional[str]:
    """Poll until branch SHA changes from prev_sha (or until timeout)."""
    deadline = time.time() + timeout
    last_seen = None
    while time.time() < deadline:
        sha = get_branch_sha(project_id, branch)
        if sha:
            last_seen = sha
            if prev_sha and sha != prev_sha:
                return sha
            if not prev_sha:  # no baseline; any sha we can use
                return sha
        time.sleep(interval)
    return last_seen

# ---------------- main ----------------

def main(argv: Optional[list[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print("usage: copilot-one-shot <JIRA-ISSUE-KEY>")
        return 2
    issue = argv[0]

    project_path = _env("GITLAB_PROJECT_PATH")
    if not project_path:
        print("ERROR: set GITLAB_PROJECT_PATH (e.g., 'user/group/myproject') in your environment.")
        return 2

    deploy_branch = _env("DEPLOY_BRANCH", "staging")
    drush_uri = _env("DRUSH_URI", "http://localhost")

    print(f"\n==> One-shot flow for {issue}\n")

    # Step 1: create MR (auto-dev) — now fully env-driven
    print("==> Step 1/4: copilot-workflow (auto-dev + MR; env defaults)")
    wf = run(["copilot-workflow", issue])
    all_out = (wf.stdout or "") + "\n" + (wf.stderr or "")
    mr_url = parse_mr_url_from_text(all_out)
    if not mr_url:
        print("ERROR: could not parse MR URL from copilot-workflow output.")
        return 2
    print(f"==> Detected MR: {mr_url}")

    # Step 2: AI review & merge (no deploy here)
    print("==> Step 2/4: AI review & merge (no deploy)")

    pid = None
    pre_sha = None
    if gl_token():
        try:
            pid = get_project_id(project_path)
            pre_sha = get_branch_sha(pid, deploy_branch)
            if pre_sha:
                print(f"[pre] {deploy_branch} = {pre_sha}")
        except Exception as e:
            print(f"!! WARNING: Could not resolve pre-merge SHA: {e}")

    run(["copilot-ai-review-merge", mr_url, "--auto-merge", "--verbose"])

    # Step 3: deploy with EXPECT_SHA (wait for branch to advance)
    print("==> Step 3/4: Deploy (wait for exact SHA)")
    expect_sha = None
    if gl_token() and pid:
        try:
            timeout = int(_env("EXPECT_TIMEOUT", "300") or "300")
            interval = int(_env("EXPECT_INTERVAL", "5") or "5")
            expect_sha = wait_for_branch_sha(pid, deploy_branch, prev_sha=pre_sha,
                                             timeout=timeout, interval=interval)
            if expect_sha and pre_sha and expect_sha == pre_sha:
                print("!! WARNING: Branch SHA did not change from pre-merge SHA within timeout; proceeding anyway.")
        except Exception as e:
            print(f"!! WARNING: Could not resolve {deploy_branch} SHA from GitLab API. Proceeding without EXPECT_SHA. ({e})")
    else:
        print("!! WARNING: GITLAB_API_TOKEN not present; deploying without EXPECT_SHA wait.")

    env = os.environ.copy()
    env["DEPLOY_BRANCH"] = deploy_branch
    env["DRUSH_URI"] = drush_uri
    env["DEPLOY_GIT_REMOTE_URL"] = _env("DEPLOY_GIT_REMOTE_URL") or f"git@gitlab.com:{project_path}.git"
    if expect_sha:
        env["EXPECT_SHA"] = expect_sha
        env["EXPECT_TIMEOUT"] = _env("EXPECT_TIMEOUT", "300")
        env["EXPECT_INTERVAL"] = _env("EXPECT_INTERVAL", "5")
        print(f"--> Expecting remote {deploy_branch} SHA: {expect_sha}")

    run(["./scripts/deploy_to_ec2.sh"], env=env)

    # Optional settle
    time.sleep(3)

    # Step 4: QA on EC2
    print("\n==> Step 4/4: QA on EC2 (reads Jira QA steps or description)")
    qa = subprocess.run(["copilot-qa-ec2", issue], text=True)
    if qa.returncode != 0:
        print("!! QA failed. Check Jira comment for details.")
    return qa.returncode

if __name__ == "__main__":
    raise SystemExit(main())
