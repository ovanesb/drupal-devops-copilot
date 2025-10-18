# copilot/agent/acceptance.py
from __future__ import annotations

import re
from typing import List, Dict

def parse_ac(text: str) -> List[str]:
    """Generic AC extractor (kept in sync with prompt_builder.extract_acceptance_criteria)."""
    lines = text.splitlines()
    ac: List[str] = []
    for i, ln in enumerate(lines):
        if re.search(r"^\s*#+\s*Acceptance Criteria\b", ln, re.I) or re.search(r"\bAcceptance Criteria\b\s*:?$", ln, re.I):
            for ln2 in lines[i + 1:]:
                if re.match(r"^\s*#+\s+\S", ln2):
                    break
                if re.match(r"^\s*-\s+\[.\]\s+", ln2) or re.match(r"^\s*[-*]\s+", ln2):
                    ac.append(re.sub(r"^\s*-\s+\[.\]\s+|\s*[-*]\s+", "", ln2).strip())
            break
    if not ac:
        for ln in lines:
            m = re.match(r"^\s*-\s+\[.\]\s+(.*)$", ln)
            if m:
                ac.append(m.group(1).strip())
    if not ac:
        m = re.search(r"\bAC\b\s*:\s*(.+)", text, re.I | re.S)
        if m:
            blob = m.group(1)
            for ln in blob.splitlines():
                ln = ln.strip("-* \t")
                if ln:
                    ac.append(ln)
    # dedupe
    seen = set()
    out = []
    for x in ac:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def generate_validation_hints(ac_items: List[str]) -> Dict[str, str]:
    """
    Map AC items to hints or commands we expect CI/QA to validate.
    This is informational; your existing CI already enforces lint/qa/deploy.
    """
    hints: Dict[str, str] = {}
    for i, item in enumerate(ac_items, 1):
        lower = item.lower()
        if "route" in lower or "controller" in lower:
            hints[f"AC{i}"] = "Ensure *.routing.yml + Controller + access checks exist."
        elif "permission" in lower:
            hints[f"AC{i}"] = "Ensure *.permissions.yml updated and used in access."
        elif "config" in lower:
            hints[f"AC{i}"] = "If new config types are added, add config schema."
        elif "form" in lower:
            hints[f"AC{i}"] = "Form validation + CSRF token + submit handlers."
        elif "event" in lower or "subscriber" in lower:
            hints[f"AC{i}"] = "Add EventSubscriber via services.yml and tag."
        else:
            hints[f"AC{i}"] = "Covered by general CI and code review."
    return hints
