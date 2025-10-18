# copilot/jira.py
from __future__ import annotations
import os
import requests
from typing import Any, Dict, Optional

"""
Minimal Jira Cloud/Server client for the Co-Pilot.

Env vars:
  JIRA_BASE_URL=https://your-domain.atlassian.net
  JIRA_EMAIL=you@example.com                  # for Jira Cloud basic auth
  JIRA_API_TOKEN=xxxxxxxxxxxxxxxxxxxx         # API token (Cloud) or password (Server)
  JIRA_ACCEPTANCE_CRITERIA_FIELD=customfield_12345   # optional; if set, we fetch it
"""

class JiraClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None,
        acceptance_field: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ):
        self.base_url = (base_url or os.getenv("JIRA_BASE_URL", "")).rstrip("/")
        self.email = email or os.getenv("JIRA_EMAIL")
        self.api_token = api_token or os.getenv("JIRA_API_TOKEN")
        self.acceptance_field = acceptance_field or os.getenv("JIRA_ACCEPTANCE_CRITERIA_FIELD")
        if not self.base_url:
            raise RuntimeError("JIRA_BASE_URL is not set")
        if not (self.email and self.api_token):
            raise RuntimeError("JIRA_EMAIL and JIRA_API_TOKEN must be set")

        self.sess = session or requests.Session()
        self.sess.auth = (self.email, self.api_token)
        self.sess.headers.update({"Accept": "application/json"})

    # ---- Public API expected by providers ----
    def get_issue(self, key: str) -> Dict[str, Any]:
        fields = [
            "summary",
            "description",
            "reporter",
            "priority",
            "labels",
        ]
        if self.acceptance_field:
            fields.append(self.acceptance_field)
        url = f"{self.base_url}/rest/api/3/issue/{key}"
        r = self.sess.get(url, params={"fields": ",".join(fields)})
        r.raise_for_status()
        data = r.json()
        f = data.get("fields", {})

        desc = self._extract_description(f.get("description"))
        ac = None
        if self.acceptance_field:
            ac = self._extract_generic(f.get(self.acceptance_field))
        # fallback: if no explicit AC field, try to reuse description (or leave None)
        acceptance_criteria = ac or None

        return {
            "key": key,
            "summary": f.get("summary") or "",
            "description": desc or "",
            "acceptance_criteria": acceptance_criteria,
            "reporter": self._extract_name(f.get("reporter")),
            "priority": self._extract_name(f.get("priority")),
            "labels": f.get("labels") or [],
        }

    # ---- Helpers ----
    def _extract_name(self, obj: Any) -> str:
        if not isinstance(obj, dict):
            return ""
        # Jira returns displayName for users; name for others varies
        return obj.get("displayName") or obj.get("name") or obj.get("id") or ""

    def _extract_generic(self, value: Any) -> Optional[str]:
        """Try to flatten either a plain string or an ADF document into text."""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return self._adf_to_text(value) or None
        return str(value)

    def _extract_description(self, desc: Any) -> str:
        # Jira Cloud often returns ADF (dict). Jira Server may return plain text.
        return self._extract_generic(desc) or ""

    def _adf_to_text(self, node: Any) -> str:
        """
        Very minimal ADF (Atlassian Document Format) flattener.
        Good enough for summaries/prompts; not meant for rich fidelity.
        """
        parts: list[str] = []
        def walk(n: Any):
            if n is None:
                return
            if isinstance(n, dict):
                t = n.get("type")
                if t == "text":
                    text = n.get("text", "")
                    parts.append(text)
                # recurse into content/marks regardless of node type
                if "content" in n and isinstance(n["content"], list):
                    for c in n["content"]:
                        walk(c)
            elif isinstance(n, list):
                for it in n:
                    walk(it)
        walk(node)
        # basic line compaction
        text = " ".join(" ".join(parts).split())
        return text.strip()
