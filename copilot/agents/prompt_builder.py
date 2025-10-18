# copilot/agents/prompt_builder.py
from __future__ import annotations

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from copilot.helpers.jira_helper import (
    get_issue_summary,
    get_issue_description,
    get_issue_acceptance,
    browse_url,
)

WEBROOT_CANDIDATES = ["web", "docroot", "public", "htdocs"]


def find_webroot(repo: Path) -> Path:
    for cand in WEBROOT_CANDIDATES:
        p = repo / cand
        if p.exists() and p.is_dir():
            return p
    return repo


def read_json_safe(p: Path) -> Dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def composer_info(repo: Path) -> Tuple[str, Dict[str, str]]:
    cj = repo / "composer.json"
    data = read_json_safe(cj) if cj.exists() else {}
    return data.get("name", ""), {k: str(v) for k, v in (data.get("require", {}) or {}).items()}


def detect_drupal_core_version(require: Dict[str, str]) -> Optional[str]:
    for k, v in require.items():
        if k in ("drupal/core", "drupal/core-recommended", "drupal/recommended-project"):
            return str(v)
    return None


def list_custom_modules(webroot: Path) -> List[str]:
    out: List[str] = []
    for rel in ["modules/custom", "sites/default/modules/custom", "modules"]:
        p = webroot / rel
        if p.exists():
            for child in sorted(p.iterdir()):
                if child.is_dir() and (child / f"{child.name}.info.yml").exists():
                    out.append(child.name)
    return out


def summarize_repo(repo: Path) -> Dict[str, object]:
    name, require = composer_info(repo)
    core = detect_drupal_core_version(require)
    webroot = find_webroot(repo)
    mods = list_custom_modules(webroot)
    has_phpcs = (repo / "phpcs.xml").exists() or (repo / "phpcs.xml.dist").exists() or (repo / "ruleset.xml").exists()
    has_phpstan = (repo / "phpstan.neon").exists() or (repo / "phpstan.neon.dist").exists()
    return {
        "composer_name": name,
        "drupal_core": core,
        "webroot": str(webroot.relative_to(repo) if webroot != repo else "."),
        "custom_modules": mods,
        "has_phpcs": has_phpcs,
        "has_phpstan": has_phpstan,
    }


def extract_acceptance_criteria_from_text(text: str) -> List[str]:
    if not text:
        return []
    ac: List[str] = []
    lines = text.splitlines()

    # 1) Section titled 'Acceptance Criteria'
    section = None
    for i, ln in enumerate(lines):
        if re.search(r"^\s*#+\s*Acceptance Criteria\b", ln, re.I) or re.search(r"\bAcceptance Criteria\b\s*:?$", ln, re.I):
            section = i
            break
    if section is not None:
        for ln in lines[section + 1 :]:
            if re.match(r"^\s*#+\s+\S", ln):  # next heading
                break
            if re.match(r"^\s*-\s+\[.\]\s+", ln) or re.match(r"^\s*[-*]\s+", ln):
                ac.append(re.sub(r"^\s*-\s+\[.\]\s+|\s*[-*]\s+", "", ln).strip())

    # 2) Any markdown checkboxes anywhere
    if not ac:
        for ln in lines:
            m = re.match(r"^\s*-\s+\[.\]\s+(.*)$", ln)
            if m:
                ac.append(m.group(1).strip())

    # 3) After "AC:" token
    if not ac:
        m = re.search(r"\bAC\b\s*:\s*(.+)", text, re.I | re.S)
        if m:
            blob = m.group(1)
            for ln in blob.splitlines():
                ln = ln.strip("-* \t")
                if ln:
                    ac.append(ln)

    # 4) Fallback: first contiguous bullet block
    if not ac:
        block: List[str] = []
        in_block = False
        for ln in lines:
            if re.match(r"^\s*[-*]\s+", ln):
                in_block = True
                block.append(re.sub(r"^\s*[-*]\s+", "", ln).strip())
            elif in_block:
                break
        if block:
            ac = [x for x in block if x]

    # de-dup
    seen = set()
    out = []
    for x in ac:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def build_prompt(issue_key: str, repo_path: str) -> Dict[str, str]:
    repo = Path(repo_path).resolve()
    ctx = summarize_repo(repo)

    title = (get_issue_summary(issue_key) or "").strip()
    desc = (get_issue_description(issue_key) or "").strip()
    issue_link = browse_url(issue_key)

    # Prefer the dedicated AC field, but MERGE with Description bullets.
    ac_text = (get_issue_acceptance(issue_key) or "").strip()
    field_items = extract_acceptance_criteria_from_text(ac_text)
    desc_items = extract_acceptance_criteria_from_text(desc)

    # If the AC field has text but no bullet/checkbox structure, treat the whole text as one AC item.
    if not field_items and ac_text:
        field_items = [ac_text.strip()]

    # Merge, keeping order: AC field items first, then any new items from description
    seen = set()
    ac_list: List[str] = []
    for src in (field_items, desc_items):
        for item in src:
            key = item.strip()
            if key and key not in seen:
                seen.add(key)
                ac_list.append(key)

    system = f"""You are a Principal Drupal Engineer (15+ years).
You produce robust, production-grade Drupal code that passes CI.
Follow Drupal coding standards (PSR-12, Drupal sniffs), modern APIs (Drupal 10/11),
and avoid deprecated functions.

REQUIREMENTS (hard):
- Target Drupal 11; set core_version_requirement: ^11 in *.info.yml.
- Keep ALL changes inside the project's custom module(s) path (typically modules/custom/…).
- Do NOT modify vendor/, composer.lock, or core files.
- YAML must be valid; add routing, permissions, services as needed.
- Wire services via dependency injection (services.yml + type-hinted constructors).
- If you add configuration, provide config/schema.
- Include access checks/permissions and CSRF protection for routes/forms.
- Ensure cacheability (contexts/tags/max-age) on render arrays where relevant.
- Add/update README in the affected module if helpful.

QUALITY:
- Minimal, focused diffs: only what's required to satisfy the ticket.
- Add/update simple kernel/functional tests when adding new routes/services (if test infra exists).
- Keep class, file, and function names aligned with Drupal naming conventions.
- Prefer typed data and strict types where reasonable.

OUTPUT:
- Return ONLY a unified diff (patch) beginning with lines like 'diff --git a/... b/...'.
- No prose, no code fences, no explanations.

Repository context:
- Composer name: {ctx.get('composer_name') or '(unknown)'}
- Drupal core: {ctx.get('drupal_core') or '(unknown)'}
- Webroot: {ctx.get('webroot')}
- Custom modules: {', '.join(ctx.get('custom_modules') or []) or '(none)'}
- PHPCS config present: {bool(ctx.get('has_phpcs'))}
- PHPStan config present: {bool(ctx.get('has_phpstan'))}
"""

    # Optional: allow hot-tuning via env without code changes
    extra_gen = os.getenv("DRUPAL_GENERATION_SYSTEM_PROMPT", "")
    if extra_gen.strip():
        system = (system + "\n" + extra_gen.strip()).strip()

    user_lines: List[str] = []
    user_lines.append(f"Issue: {issue_key} — {title or '(no title)'}")
    user_lines.append(f"Jira: {issue_link}")
    user_lines.append("")
    if desc:
        user_lines.append("Jira Description:")
        user_lines.append(desc)
        user_lines.append("")

    if ac_list:
        user_lines.append("Acceptance Criteria (must meet):")
        for i, item in enumerate(ac_list, 1):
            user_lines.append(f"{i}. {item}")
        user_lines.append("")
        user_lines.append("Ensure the produced diff enables us to satisfy the above AC and pass CI.")
        user_lines.append("")

    user_lines.append("Validation (CI expectations):")
    user_lines.append("- YAML lint passes.")
    user_lines.append("- PHPCS on changed PHP-like files passes or is minimal/no-op if none.")
    user_lines.append("- PHPStan passes at project's level (or minimal if config absent).")
    user_lines.append("- On staging branch, deploy job should succeed.")
    user_lines.append("")
    user_lines.append("Return only the unified diff patch; no prose.")

    guardrails = (
        "Guardrails:\n"
        "- Do not touch files outside modules/custom/.\n"
        "- Do not modify vendor/ or composer.lock directly.\n"
        "- If creating a new module, place it under modules/custom/<machine_name>/.\n"
    )

    return {
        "system_prompt": system,
        "user_prompt": "\n".join(user_lines),
        "guardrails": guardrails,
        "title": title,
        "ac": "\n".join(ac_list),
    }
