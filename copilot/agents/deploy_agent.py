from __future__ import annotations

import os
from typing import Iterable, List, Sequence

from copilot.deploy.ec2_runner import rsync_changed, drush_pipeline
from copilot.deploy.qa_ec2 import smoke as qa_smoke
from copilot.helpers.jira_helper import jira_comment, jira_transition

# Guardrails: match deploy.ec2_runner defaults
ALLOWED_DIR = "modules/custom"


def _composer_changed(files: Iterable[str]) -> bool:
    for f in files:
        if f in ("composer.json", "composer.lock"):
            return True
    return False


def _summ(lines: Sequence[str], tail: int = 60) -> str:
    if not lines:
        return "(no output)"
    if len(lines) <= tail:
        return "\n".join(lines)
    return "\n".join(["… (truncated) …"] + list(lines)[-tail:])


class DeployAgent:
    """
    Deploys code to EC2 (via SSH/rsync), runs drush pipeline, executes basic QA,
    then comments + transitions Jira.

    Expected env (set on the machine running this agent):
      DEPLOY_HOST, DEPLOY_USER, DEPLOY_SSH_KEY, DEPLOY_WORKDIR, SITE_BASE_URL
    """

    def __init__(self) -> None:
        # Light sanity checks; we don't hard-fail here (rsync/ssh will error if wrong).
        self.host = os.getenv("DEPLOY_HOST", "")
        self.user = os.getenv("DEPLOY_USER", "ubuntu")
        self.key = os.getenv("DEPLOY_SSH_KEY", "")
        self.workdir = os.getenv("DEPLOY_WORKDIR", "/srv/drupal")

    async def deploy_and_qa_to_ec2(
        self,
        issue_key: str,
        repo_root: str,
        changed_files: List[str],
        composer_changed_flag: bool | None = None,
        next_state_on_success: str = "QA",
    ) -> bool:
        """
        1) rsync only allowed changed files under modules/custom/*
        2) docker compose up -d
        3) drush cim / updb / cr (+ composer install if needed)
        4) HTTP smoke tests on EC2
        5) Jira comment + transition
        """
        # Determine whether to run composer install
        needs_composer = (
            _composer_changed(changed_files)
            if composer_changed_flag is None
            else composer_changed_flag
        )

        await jira_comment(issue_key, f"🚀 Starting EC2 deploy (composer={needs_composer})")

        # 1) sync files
        ok_rsync, out_rsync = await rsync_changed(repo_root, changed_files)
        await jira_comment(issue_key, f"**EC2 rsync output**\n```\n{_summ(out_rsync)}\n```")
        if not ok_rsync:
            await jira_comment(issue_key, "❌ EC2 rsync failed. Stopping.")
            return False

        # 2–3) drush pipeline
        ok_drush, out_drush = await drush_pipeline(needs_composer=needs_composer)
        await jira_comment(issue_key, f"**Drush pipeline**\n```\n{_summ(out_drush)}\n```")
        if not ok_drush:
            await jira_comment(issue_key, "❌ Drush pipeline failed.")
            return False

        # 4) QA smoke
        qa_log = await qa_smoke()
        await jira_comment(issue_key, f"**EC2 QA**\n```\n{_summ(qa_log, tail=20)}\n```")

        # If all steps succeeded, transition Jira
        await jira_transition(issue_key, next_state_on_success)
        await jira_comment(issue_key, f"✅ Deployed to EC2 and moved to **{next_state_on_success}**.")
        return True
