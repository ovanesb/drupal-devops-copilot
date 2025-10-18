# copilot/cli/review.py
from __future__ import annotations
import os, sys, argparse
from copilot.agents.code_review_agent import review_and_merge_and_deploy

def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="copilot-review")
    p.add_argument("--project-path", required=False, default=os.getenv("GITLAB_PROJECT_PATH",""),
                   help="GitLab project path (or set GITLAB_PROJECT_PATH)")
    p.add_argument("--mr", type=int, required=True, help="Merge Request IID")
    p.add_argument("--issue", required=True, help="Jira issue key, e.g., PROJ-123")
    p.add_argument("--repo-path", required=False, default=os.getenv("COPILOT_REPO_PATH", os.getcwd()),
                   help="Local repo root to rsync from (default: $COPILOT_REPO_PATH or CWD)")
    args = p.parse_args(argv)

    if not args.project_path:
        print("Set --project-path or GITLAB_PROJECT_PATH")
        return 2

    rc = review_and_merge_and_deploy(
        project_path=args.project_path,
        mr_iid=args.mr,
        issue_key=args.issue,
        repo_root=args.repo_path,
    )
    print("Review + merge + deploy complete with code:", rc)
    return rc

if __name__ == "__main__":
    sys.exit(main())
