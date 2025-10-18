# copilot/jira_ext.py
"""
Minimal Jira helper for Drupal DevOps Co-Pilot.

Env vars:
- JIRA_BASE_URL          e.g. https://your-space.atlassian.net
- JIRA_EMAIL             Jira user email (for API auth)
- JIRA_API_TOKEN         Jira API token

Optional:
- JIRA_TRANSITION_ON_MR_OPEN   e.g. "To Review"
- JIRA_HTTP_TIMEOUT            seconds (default 15)
"""

from __future__ import annotations
import os
import requests

DEFAULT_TIMEOUT = int(os.environ.get("JIRA_HTTP_TIMEOUT", "15"))

def _base() -> str:
    base = os.environ.get("JIRA_BASE_URL")
    if not base:
        raise RuntimeError("Jira not configured: set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN.")
    return base.rstrip("/")

def _auth() -> tuple[str, str]:
    email = os.environ.get("JIRA_EMAIL")
    token = os.environ.get("JIRA_API_TOKEN")
    if not email or not token:
        raise RuntimeError("Jira auth missing: set JIRA_EMAIL and JIRA_API_TOKEN.")
    return (email, token)

def _raise_for_status_with_details(r: requests.Response) -> None:
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        detail = ""
        try:
            j = r.json()
            # common Jira error fields
            msg = j.get("message") or j.get("errorMessages") or j.get("errors") or j
            detail = f" | details: {msg}"
        except Exception:
            detail = f" | body: {r.text[:300]}"
        raise requests.HTTPError(f"{e} {detail}") from e

def _adf_paragraph(text: str) -> dict:
    # Simple ADF paragraph with text (and optional link autodetected by Jira)
    return {
        "type": "paragraph",
        "content": [{"type": "text", "text": text}],
    }

def comment(issue_key: str, body_text: str) -> dict:
    """
    Post a comment using ADF (Document Format). body_text is inserted into a paragraph.
    """
    url = f"{_base()}/rest/api/3/issue/{issue_key}/comment"
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [_adf_paragraph(body_text)],
        }
    }
    r = requests.post(url, auth=_auth(), json=payload, timeout=DEFAULT_TIMEOUT)
    _raise_for_status_with_details(r)
    return r.json()

def transitions(issue_key: str) -> list[dict]:
    url = f"{_base()}/rest/api/3/issue/{issue_key}/transitions"
    r = requests.get(url, auth=_auth(), timeout=DEFAULT_TIMEOUT)
    _raise_for_status_with_details(r)
    data = r.json()
    return data.get("transitions", [])

def transition(issue_key: str, name: str) -> None:
    name_lower = name.strip().lower()
    opts = transitions(issue_key)
    choice = next((t for t in opts if t.get("name", "").strip().lower() == name_lower), None)
    if not choice:
        raise RuntimeError(f"Transition '{name}' not available for {issue_key}. Options: {[t.get('name') for t in opts]}")
    url = f"{_base()}/rest/api/3/issue/{issue_key}/transitions"
    r = requests.post(url, auth=_auth(), json={"transition": {"id": choice["id"]}}, timeout=DEFAULT_TIMEOUT)
    _raise_for_status_with_details(r)
