# copilot/agents/plan_preview.py
from __future__ import annotations
import re
from typing import Dict, List, Any

from copilot.helpers.jira_helper import (
    get_issue_summary,
    get_issue_description,
    get_issue_acceptance,
)

def _normalize_text(s: str) -> str:
    return (s or "").strip()

_CHECK_PREFIX = re.compile(r"^\s*(?:-\s*\[\s*[xX ]\s*\]|-\s+|\*\s+|\d+\.\s+)\s*(.+?)\s*$")

def parse_checklist(md: str) -> List[str]:
    """Extract bullet/checkbox/numbered items from Markdown-ish text."""
    out: List[str] = []
    for line in (md or "").splitlines():
        m = _CHECK_PREFIX.match(line)
        if m:
            item = m.group(1).strip()
            if item:
                out.append(item)
    return out

def suggest_module_machine_name(issue_key: str, summary: str) -> str:
    """
    Create a safe Drupal module machine name (lowercase, underscores) from key+summary.
    """
    base = f"{issue_key}-{summary}".lower()
    # replace non-alphanum with underscore
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    # Drupal prefers <= 50 chars-ish; trim and collapse underscores
    base = re.sub(r"_+", "_", base)[:48].strip("_")
    if not base:
        base = issue_key.lower().replace("-", "_")
    # prefix to avoid collisions and express origin
    return f"copilot_{base}"

def build_plan_preview(issue_key: str) -> Dict[str, Any]:
    summary = _normalize_text(get_issue_summary(issue_key))
    desc = _normalize_text(get_issue_description(issue_key))
    ac = _normalize_text(get_issue_acceptance(issue_key))

    desc_items = parse_checklist(desc)
    ac_items = parse_checklist(ac)

    module_name = suggest_module_machine_name(issue_key, summary or issue_key)

    # Opinionated Drupal steps; adjust dynamically if description mentions module/hook/route/etc.
    wants_module = True
    wants_hook_help = any("hook_help" in x.lower() or "help" in x.lower() for x in (desc_items + ac_items))
    wants_route = any("route" in x.lower() or "controller" in x.lower() for x in (desc_items + ac_items))

    suggested: List[str] = []
    if wants_module:
        suggested += [
            f"Scaffold custom module `{module_name}` under `modules/custom/{module_name}`.",
            f"Add `{module_name}.info.yml` with `core_version_requirement: ^11` and a clear description.",
            f"Add `{module_name}.module` as needed.",
        ]
    if wants_hook_help:
        suggested.append(f"Implement `hook_help()` in `{module_name}.module` to display the required plain text.")
    if wants_route:
        suggested += [
            f"Add `{module_name}.routing.yml` with a sample route `/admin/structure/{module_name}`.",
            f"Create `src/Controller/{module_name.title().replace('_','')}Controller.php` returning render array with text.",
            f"Add basic access check (permission) and define it in `{module_name}.permissions.yml` if needed.",
        ]

    suggested += [
        f"Add `README.md` in the module to document purpose and how to test.",
        "Run local linters (yamllint/PHPCS/PHPStan if configured) and update code to satisfy CI.",
        "Commit changes with a conventional message referencing the Jira key.",
        "Push branch; open/verify Merge Request and pipeline status.",
    ]

    validations = [
        "YAML lint passes (CI job `yamllint`).",
        "PHPCS passes on changed PHP-like files (or no PHP changes).",
        "PHPStan passes at project level (smoke test if config absent).",
        "Staging deploy pipeline succeeds on merge.",
    ]

    risks = [
        "Avoid changing vendor files or core.",
        "Ensure no deprecated Drupal 11 APIs are used.",
        "Paths outside `modules/custom/**` should be explicitly justified.",
    ]

    return {
        "issue_key": issue_key,
        "summary": summary,
        "description_md": desc,
        "acceptance_md": ac,
        "acceptance_checklist": ac_items,
        "description_checklist": desc_items,
        "suggested_module_name": module_name,
        "suggested_plan": suggested,
        "validations": validations,
        "risks": risks,
    }
