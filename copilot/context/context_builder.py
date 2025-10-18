# copilot/context/context_builder.py
from __future__ import annotations
from typing import Any, Dict

from copilot.context.providers.jira_provider import JiraProvider
from copilot.context.providers.git_provider import GitProvider
from copilot.context.providers.drush_provider import DrushProvider

class ContextBuilder:
    """Orchestrates data from providers.

    context_spec example:
    {
      "jira": {"key": "CCS-7"},
      "git": {"diff": true, "base": "origin/develop", "head": "HEAD"},
      "drush": {"status": true}
    }
    """
    def __init__(self, jira: JiraProvider, git: GitProvider, drush: DrushProvider):
        self.jira = jira
        self.git = git
        self.drush = drush

    def build(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {}
        if jira_spec := spec.get("jira"):
            ctx["jira"] = self.jira.fetch(jira_spec)
        if git_spec := spec.get("git"):
            ctx["git"] = self.git.fetch(git_spec)
        if drush_spec := spec.get("drush"):
            ctx["drush"] = self.drush.fetch(drush_spec)
        return ctx