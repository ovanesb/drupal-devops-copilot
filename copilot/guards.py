# copilot/guards.py
from __future__ import annotations
import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

# Allowed / blocked paths can be tuned via env if needed.
_ALLOWED_DEFAULT = "modules/custom/,themes/custom/,profiles/custom/,notes/,server/,ui/"
_BLOCKED_DEFAULT = "vendor/,core/,.git/"

ALLOWED_PREFIXES = tuple(p.strip() for p in (os.getenv("COPILOT_ALLOWED_PATHS") or _ALLOWED_DEFAULT).split(",") if p.strip())
BLOCKED_PREFIXES = tuple(p.strip() for p in (os.getenv("COPILOT_BLOCKED_PATHS") or _BLOCKED_DEFAULT).split(",") if p.strip())

# Additional "high-risk" files that require explicit override
HIGH_RISK_FILES = {
    ".gitlab-ci.yml",
    "composer.json",
    "composer.lock",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}

# Risk thresholds (tune via env if needed)
MAX_CHANGED_FILES = int(os.getenv("COPILOT_MAX_CHANGED_FILES", "30"))
MAX_TOTAL_LINES = int(os.getenv("COPILOT_MAX_TOTAL_LINES", "2000"))

_DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$")

@dataclass
class PatchRisk:
    files: List[str]
    total_added: int
    total_removed: int
    blocked: List[str]
    out_of_scope: List[str]
    high_risk: List[str]
    risk_level: str   # "low" | "medium" | "high"
    reason: str

def _changed_paths_from_patch(patch: str) -> List[str]:
    paths: List[str] = []
    for line in patch.splitlines():
        m = _DIFF_HEADER_RE.match(line.strip())
        if m:
            # choose the "b/" side
            b = m.group(2)
            paths.append(b)
    return paths

def _count_added_removed(patch: str) -> Tuple[int, int]:
    added = removed = 0
    for line in patch.splitlines():
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed

def _is_prefix(path: str, prefixes: Iterable[str]) -> bool:
    path = path.lstrip("./")
    for p in prefixes:
        if p and path.startswith(p):
            return True
    return False

def assess_patch_risk(patch: str) -> PatchRisk:
    files = _changed_paths_from_patch(patch)
    added, removed = _count_added_removed(patch)
    blocked = [f for f in files if _is_prefix(f, BLOCKED_PREFIXES)]
    out_of_scope = [f for f in files if not _is_prefix(f, ALLOWED_PREFIXES)]
    high_risk = [f for f in files if f in HIGH_RISK_FILES]

    # Base risk rules
    level = "low"
    reason_parts: List[str] = []

    if blocked:
        level = "high"
        reason_parts.append(f"blocked paths: {blocked[:3]}{'...' if len(blocked)>3 else ''}")

    if high_risk:
        level = "high"
        reason_parts.append(f"high-risk files: {high_risk[:3]}{'...' if len(high_risk)>3 else ''}")

    if len(files) > MAX_CHANGED_FILES or (added + removed) > MAX_TOTAL_LINES:
        level = "high"
        reason_parts.append(f"size limit exceeded (files={len(files)}, lines={added+removed})")

    if level != "high" and out_of_scope:
        level = "medium"
        reason_parts.append(f"out-of-scope paths: {out_of_scope[:3]}{'...' if len(out_of_scope)>3 else ''}")

    if not files:
        level = "low"
        reason_parts.append("no file headers found")

    reason = "; ".join(reason_parts) or "OK"

    return PatchRisk(
        files=files,
        total_added=added,
        total_removed=removed,
        blocked=blocked,
        out_of_scope=out_of_scope,
        high_risk=high_risk,
        risk_level=level,
        reason=reason,
    )

def enforce_patch_guardrails(patch: str, *, allow_risk: bool = False) -> PatchRisk:
    """
    Validate a unified diff against safety rules.
    - Raises ValueError if risk is high and allow_risk=False.
    - Returns PatchRisk for logging/observability.
    """
    risk = assess_patch_risk(patch)
    if risk.risk_level == "high" and not allow_risk:
        raise ValueError(f"Patch rejected by guardrails: {risk.reason}")
    return risk
