# copilot/cli/deploy.py
from __future__ import annotations
import os, sys, argparse
from copilot.agents.deploy_agent import deploy

def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="copilot-deploy")
    p.add_argument("--project-path", default=os.getenv("GITLAB_PROJECT_PATH",""))
    p.add_argument("--env", default="staging", choices=["staging","production"])
    p.add_argument("--ref", default=os.getenv("GIT_TARGET_BRANCH","main"))
    p.add_argument("--yes", action="store_true", help="Non-interactive confirmation")
    args = p.parse_args(argv)

    if not args.project_path:
        print("Set --project-path or GITLAB_PROJECT_PATH"); return 2
    if not args.yes:
        print("Refusing to deploy without --yes"); return 3

    url = deploy(args.project_path, env=args.env, ref=args.ref)
    print(f"Triggered deploy to {args.env}: {url}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
