# copilot/helpers/jira_helper.py
from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

import requests

# ---- ENV ----
JIRA_BASE = (os.getenv("JIRA_BASE_URL") or "").rstrip("/")
# Accept either JIRA_EMAIL or JIRA_USER_EMAIL
JIRA_EMAIL = os.getenv("JIRA_EMAIL") or os.getenv("JIRA_USER_EMAIL") or ""
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN") or ""
# For building human "browse" links (optional)
JIRA_BROWSE_PREFIX = (
    (os.getenv("JIRA_BROWSE_URL_PREFIX") or (JIRA_BASE + "/browse/")).rstrip("/") + "/"
)


def _assert_cfg():
    missing = [
        k
        for k, v in {
            "JIRA_BASE": JIRA_BASE,
            "JIRA_EMAIL": JIRA_EMAIL,
            "JIRA_API_TOKEN": JIRA_API_TOKEN,
        }.items()
        if not v
    ]
    if missing:
        raise RuntimeError(f"Jira env vars missing: {', '.join(missing)}")
    parsed = urlparse(JIRA_BASE)
    if not (parsed.scheme and parsed.netloc):
        raise RuntimeError(f"Invalid JIRA_BASE_URL: {JIRA_BASE!r}")


def _auth_tuple():
    _assert_cfg()
    return (JIRA_EMAIL, JIRA_API_TOKEN)


def _headers() -> Dict[str, str]:
    tok = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
    return {
        "Authorization": f"Basic {tok}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# ---- ADF -> text (best-effort with checkboxes/lists) ----
def _adf_to_text(node: Any) -> str:
    """
    Convert Jira ADF (Atlassian Document Format) to plain text with
    markdown-style bullets/checkboxes so downstream parsers can detect AC:
      - bulletList/listItem -> "- ..."
      - taskList/taskItem   -> "- [ ] ..." or "- [x] ..."
    """
    parts: List[str] = []

    def walk(n: Any):
        if isinstance(n, dict):
            t = n.get("type")
            content = n.get("content", []) or []

            if t == "text":
                parts.append(n.get("text", ""))

            elif t == "hardBreak":
                parts.append("\n")

            elif t in ("paragraph", "heading", "blockquote"):
                for c in content:
                    walk(c)
                parts.append("\n")

            elif t in ("bulletList", "orderedList"):
                # children are listItem nodes
                for c in content:
                    walk(c)

            elif t == "listItem":
                # Render as a simple bullet
                parts.append("- ")
                for c in content:
                    walk(c)
                parts.append("\n")

            elif t == "taskList":
                # children are taskItem nodes
                for c in content:
                    walk(c)

            elif t == "taskItem":
                state = (n.get("attrs") or {}).get("state", "TODO")
                parts.append("- [x] " if str(state).upper() == "DONE" else "- [ ] ")
                for c in content:
                    walk(c)
                parts.append("\n")

            else:
                # generic fallback
                for c in content:
                    walk(c)

        elif isinstance(n, list):
            for c in n:
                walk(c)

    walk(node)
    text = "".join(parts)
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---- Issue fields ----
def get_issue_summary(issue_key: str) -> str:
    _assert_cfg()
    url = f"{JIRA_BASE}/rest/api/3/issue/{quote(issue_key)}"
    r = requests.get(url, params={"fields": "summary"}, auth=_auth_tuple(), timeout=30)
    r.raise_for_status()
    return (r.json().get("fields", {}) or {}).get("summary", "") or ""


def get_issue_description(issue_key: str) -> str:
    _assert_cfg()
    url = f"{JIRA_BASE}/rest/api/3/issue/{quote(issue_key)}"
    r = requests.get(url, params={"fields": "description"}, auth=_auth_tuple(), timeout=30)
    r.raise_for_status()
    val = (r.json().get("fields", {}) or {}).get("description")
    if isinstance(val, dict):
        return _adf_to_text(val)
    return val or ""


def add_comment(issue_key: str, body_text: str, *, adf: bool = True) -> None:
    _assert_cfg()
    url = f"{JIRA_BASE}/rest/api/3/issue/{quote(issue_key)}/comment"
    if adf:
        payload = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": body_text}]}
                ],
            }
        }
    else:
        payload = {"body": body_text}
    resp = requests.post(
        url, auth=_auth_tuple(), headers=_headers(), json=payload, timeout=30
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Jira add_comment failed: {resp.status_code} {resp.text}")


def add_link_to_issue(issue_key: str, web_url: str, title: str = "Merge Request") -> None:
    _assert_cfg()
    url = f"{JIRA_BASE}/rest/api/3/issue/{quote(issue_key)}/remotelink"
    payload = {"object": {"url": web_url, "title": title}}
    resp = requests.post(
        url, auth=_auth_tuple(), headers=_headers(), json=payload, timeout=30
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Jira add_link_to_issue failed: {resp.status_code} {resp.text}")


def browse_url(issue_key: str) -> str:
    return f"{JIRA_BROWSE_PREFIX}{issue_key}"


# ---- Transitions ----
def get_available_transitions(issue_key: str) -> list[dict]:
    _assert_cfg()
    url = f"{JIRA_BASE}/rest/api/3/issue/{quote(issue_key)}/transitions"
    r = requests.get(url, auth=_auth_tuple(), timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Jira transitions fetch failed: {r.status_code} {r.text}")
    return r.json().get("transitions", []) or []


def transition_issue(issue_key: str, state_name: str) -> None:
    transitions = get_available_transitions(issue_key)
    match = next(
        (t for t in transitions if t.get("name", "").lower() == state_name.lower()), None
    )
    if not match:
        return
    url = f"{JIRA_BASE}/rest/api/3/issue/{quote(issue_key)}/transitions"
    resp = requests.post(
        url,
        auth=_auth_tuple(),
        headers=_headers(),
        json={"transition": {"id": match["id"]}},
        timeout=30,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"Jira transition_issue failed: {resp.status_code} {resp.text}")


def transition_issue_to_first_matching(issue_key: str, state_names: list[str]) -> bool:
    names_norm = [n.strip().lower() for n in state_names if n and n.strip()]
    if not names_norm:
        return False
    transitions = get_available_transitions(issue_key)
    by_name = {t.get("name", "").lower(): t for t in transitions}
    for name in names_norm:
        t = by_name.get(name)
        if t:
            url = f"{JIRA_BASE}/rest/api/3/issue/{quote(issue_key)}/transitions"
            resp = requests.post(
                url,
                auth=_auth_tuple(),
                headers=_headers(),
                json={"transition": {"id": t["id"]}},
                timeout=30,
            )
            if resp.status_code in (200, 204):
                return True
            raise RuntimeError(
                f"Jira transition to '{name}' failed: {resp.status_code} {resp.text}"
            )
    return False


# ---- Acceptance Criteria custom field ----
_field_id_cache: Dict[str, str] = {}


def list_fields() -> List[Dict[str, Any]]:
    _assert_cfg()
    url = f"{JIRA_BASE}/rest/api/3/field"
    r = requests.get(url, auth=_auth_tuple(), timeout=30)
    r.raise_for_status()
    return r.json() or []


def resolve_field_id_by_name(name: str) -> Optional[str]:
    if not name:
        return None
    if name in _field_id_cache:
        return _field_id_cache[name]
    try:
        for f in list_fields():
            if (f.get("name") or "").strip().lower() == name.strip().lower():
                _field_id_cache[name] = f["id"]
                return f["id"]
    except Exception:
        pass
    return None


def get_acceptance_field_id() -> Optional[str]:
    fid = os.getenv("JIRA_AC_FIELD_ID")
    if fid:
        return fid
    fname = os.getenv("JIRA_AC_FIELD_NAME")
    if fname:
        return resolve_field_id_by_name(fname)
    return resolve_field_id_by_name("Acceptance Criteria")


def get_issue_acceptance(issue_key: str) -> str:
    fid = get_acceptance_field_id()
    if not fid:
        return ""
    _assert_cfg()
    url = f"{JIRA_BASE}/rest/api/3/issue/{quote(issue_key)}"
    r = requests.get(url, params={"fields": fid}, auth=_auth_tuple(), timeout=30)
    r.raise_for_status()
    val = (r.json().get("fields", {}) or {}).get(fid)
    if not val:
        return ""
    if isinstance(val, dict):  # ADF
        return _adf_to_text(val)
    if isinstance(val, list):  # list of strings
        return "\n".join(str(x) for x in val if x)
    return str(val)


# ---- Issue-key extraction helper ----
ISSUE_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d+\b")

def extract_issue_keys_from_text(text: str) -> list[str]:
    """
    Return unique Jira issue keys found in free text (e.g. 'CCS-123', 'PROJ-9').
    Order-insensitive, case-insensitive project key.
    """
    if not text:
        return []
    return sorted(set(ISSUE_KEY_RE.findall(text)))


# ---- Async helpers expected by agents (NEW) ----

async def jira_comment(issue_key: str, body: str) -> Dict[str, Any] | None:
    """
    Async wrapper to post a Jira comment. Uses plain text (no ADF) for simplicity.
    """
    loop = asyncio.get_running_loop()
    def _sync():
        add_comment(issue_key, body_text=body, adf=False)
        return {"ok": True}
    return await loop.run_in_executor(None, _sync)

async def jira_transition(issue_key: str, to_status_name: str) -> Optional[str]:
    """
    Async helper to transition an issue by *name* (case-insensitive).
    If not found, leaves a comment listing available transitions.
    Returns the transition ID used, or None if not found.
    """
    loop = asyncio.get_running_loop()

    def _find_transition_id() -> Optional[str]:
        transitions = get_available_transitions(issue_key)
        # exact case-insensitive match first
        for t in transitions:
            if (t.get("name") or "").strip().lower() == (to_status_name or "").strip().lower():
                return str(t.get("id"))
        # fallback: substring match
        for t in transitions:
            name = (t.get("name") or "").strip().lower()
            if (to_status_name or "").strip().lower() in name and name:
                return str(t.get("id"))
        return None

    def _do_transition(tid: str) -> None:
        url = f"{JIRA_BASE}/rest/api/3/issue/{quote(issue_key)}/transitions"
        resp = requests.post(
            url,
            auth=_auth_tuple(),
            headers=_headers(),
            json={"transition": {"id": tid}},
            timeout=30,
        )
        if resp.status_code not in (200, 204):
            raise RuntimeError(f"Jira transition_issue failed: {resp.status_code} {resp.text}")

    tid = await loop.run_in_executor(None, _find_transition_id)
    if not tid:
        # leave a breadcrumb to help diagnose
        await jira_comment(
            issue_key,
            f"⚠️ Could not find transition named '{to_status_name}'. "
            f"Available: {', '.join((t.get('name') or '?') for t in get_available_transitions(issue_key))}",
        )
        return None

    await loop.run_in_executor(None, _do_transition, tid)
    return tid
