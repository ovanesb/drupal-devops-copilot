# copilot/context/providers/jira_provider.py
from __future__ import annotations
from typing import Any, Dict

class JiraProvider:
    def __init__(self, client):
        self.client = client  # inject actual Jira client

    def fetch(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        key = spec.get("key")
        # return minimal dict to feed prompts; expand as needed
        issue = self.client.get_issue(key)  # implement in your Jira client
        return {
            "key": key,
            "summary": issue.get("summary"),
            "acceptance_criteria": issue.get("acceptance_criteria"),
            "reporter": issue.get("reporter"),
            "priority": issue.get("priority"),
            "labels": issue.get("labels"),
        }