# copilot/agents/workflow_agent.py
from __future__ import annotations
import os
import re
import shlex
import subprocess
import urllib.parse
from dataclasses import dataclass
from typing import Optional, Dict, Any

import requests

from copilot.ai.ai_generator import AIGenerator
from copilot.prompts.registry import PromptRegistry
from copilot.context.context_builder import ContextBuilder
from copilot.context.providers.jira_provider import JiraProvider
from copilot.context.providers.git_provider import GitProvider
from copilot.context.providers.drush_provider import DrushProvider


def run(cmd: list[str], *, dry_run: bool = False, cwd: Optional[str] = None) -> str:
    printable = " ".join(shlex.quote(c) for c in cmd)
    if cwd:
        print(f"$ (cd {shlex.quote(cwd)} && {printable})")
    else:
        print("$", printable)
    if dry_run:
        return ""
    return subprocess.check_output(cmd, text=True, cwd=cwd).strip()


def run_ok(cmd: list[str], *, cwd: Optional[str] = None) -> tuple[bool, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        return (p.returncode == 0), (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return False, str(e)


def slugify(text: str, max_len: int = 48) -> str:
    text = re.sub(r"[^a-zA-Z0-9\-_]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text.strip("-_")[:max_len].lower()


@dataclass
class WorkflowConfig:
    jira_key: str
    base_branch: str = os.getenv("GIT_TARGET_BRANCH", "develop")
    repo_path: str = os.getenv("COPILOT_REPO_PATH", os.getcwd())
    draft_mr: bool = True
    remove_source_after_merge: bool = False
    dry_run: bool = False


class GitLabAPI:
    def __init__(self):
        base = os.getenv("GITLAB_BASE_URL") or os.getenv("GITLAB_URL")
        if not base:
            raise RuntimeError("GITLAB_BASE_URL not set")
        self.base = base.rstrip("/")
        token = os.getenv("GITLAB_API_TOKEN") or os.getenv("GITLAB_TOKEN")
        if not token:
            raise RuntimeError("GITLAB_API_TOKEN not set")
        self.session = requests.Session()
        self.session.headers.update({"PRIVATE-TOKEN": token})

    def _api(self, path: str) -> str:
        return f"{self.base}/api/v4{path}"

    def ensure_project_id(self) -> int:
        if pid := os.getenv("GITLAB_PROJECT_ID"):
            return int(pid)
        path = os.getenv("GITLAB_PROJECT_PATH")
        if not path:
            raise RuntimeError("Set GITLAB_PROJECT_ID or GITLAB_PROJECT_PATH")
        enc = urllib.parse.quote_plus(path)
        r = self.session.get(self._api(f"/projects/{enc}"))
        r.raise_for_status()
        return int(r.json()["id"])

    def create_merge_request(
        self,
        project_id: int,
        *,
        title: str,
        description: str,
        source_branch: str,
        target_branch: str,
        draft: bool = True,
        remove_source: bool = False,
        labels: Optional[list[str]] = None,
    ) -> dict:
        payload = {
            "title": (f"Draft: {title}" if draft and not title.lower().startswith("draft:") else title),
            "description": description,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "remove_source_branch": remove_source,
        }
        if labels:
            payload["labels"] = ",".join(labels)
        r = self.session.post(self._api(f"/projects/{project_id}/merge_requests"), data=payload)
        r.raise_for_status()
        return r.json()


class WorkflowAgent:
    """Branch → commit → push → MR (text generation via AIGenerator)."""

    def __init__(self, jira_client) -> None:
        registry = PromptRegistry()
        context_builder = ContextBuilder(
            jira=JiraProvider(client=jira_client),
            git=GitProvider(),
            drush=DrushProvider(),
        )
        self.ai = AIGenerator(registry, context_builder)
        self._gitlab_client = None

    def plan(self, cfg: WorkflowConfig) -> Dict[str, Any]:
        return {"jira": {"key": cfg.jira_key}}

    def create_branch(self, cfg: WorkflowConfig, summary: str | None) -> str:
        base = cfg.base_branch
        repo = cfg.repo_path
        run(["git", "fetch", "origin"], dry_run=cfg.dry_run, cwd=repo)
        name = slugify(summary or cfg.jira_key)
        branch = f"feature/{cfg.jira_key.lower()}-{name}"
        run(["git", "checkout", base], dry_run=cfg.dry_run, cwd=repo)
        run(["git", "pull", "--ff-only", "origin", base], dry_run=cfg.dry_run, cwd=repo)
        run(["git", "checkout", "-b", branch], dry_run=cfg.dry_run, cwd=repo)
        return branch

    def _short_commit_msg(self, cfg: WorkflowConfig, title: str) -> str:
        # Always keep it short & predictable; avoid dumping Jira body.
        clean = " ".join(title.split())
        return f"feat({cfg.jira_key}): {clean}"

    def commit_and_push(
        self,
        cfg: WorkflowConfig,
        *,
        title: str,
        body: str | None,
        jira_ctx: dict | None,
        branch: str,
    ) -> str:
        repo = cfg.repo_path

        # Stage everything (auto-dev should have created files on this branch)
        run(["git", "add", "-A"], dry_run=cfg.dry_run, cwd=repo)

        # Only commit if there are changes
        ok, out = run_ok(["git", "status", "--porcelain"], cwd=repo)
        if not ok:
            print("! git status failed; attempting commit anyway.")
        if ok and out.strip() == "":
            print(">>> No changes to commit.")
            # Ensure branch is pushed so MR can still open
            run(["git", "push", "-u", "origin", branch], dry_run=cfg.dry_run, cwd=repo)
            return self._short_commit_msg(cfg, title)

        msg = self._short_commit_msg(cfg, title)
        run(["git", "commit", "-m", msg], dry_run=cfg.dry_run, cwd=repo)
        run(["git", "push", "-u", "origin", branch], dry_run=cfg.dry_run, cwd=repo)
        return msg

    def open_merge_request(
        self,
        cfg: WorkflowConfig,
        *,
        branch: str,
        title: str,
        description: str,
        labels: Optional[list[str]] = None,
    ) -> dict:
        gl = self._get_gitlab()
        pid = gl.ensure_project_id()
        mr = gl.create_merge_request(
            pid,
            title=title,
            description=description,
            source_branch=branch,
            target_branch=cfg.base_branch,
            draft=cfg.draft_mr,
            remove_source=cfg.remove_source_after_merge,
            labels=labels,
        )
        return mr

    def render_mr_description(self, cfg: WorkflowConfig, *, changes: str) -> str:
        # Keep fallback friendly if LLM is unavailable
        try:
            return self.ai.generate(
                prompt_id="git_mr_template",
                inputs={
                    "title": f"{cfg.jira_key}: Implement changes",
                    "summary": "Autogenerated MR description from Jira + diff",
                    "changes": changes,
                    "jira": {"key": cfg.jira_key},
                    "pipeline_url": os.getenv("CI_JOB_URL", "n/a"),
                },
                context_spec={"jira": {"key": cfg.jira_key}},
                agent="git_copilot",
            )
        except Exception:
            return f"{cfg.jira_key}: Changes implemented.\n\nSee diff."

    def _get_gitlab(self) -> "GitLabAPI":
        if self._gitlab_client is None:
            self._gitlab_client = GitLabAPI()
        return self._gitlab_client


__all__ = [
    "WorkflowAgent",
    "WorkflowConfig",
]
