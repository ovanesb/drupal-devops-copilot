# copilot/agents/code_author_agent.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import os
import textwrap
import datetime as _dt

# Local imports
from copilot.codegen.patch_applier import PatchApplier, PatchApplyError


@dataclass
class AuthorConfig:
    """
    Configuration for the CodeAuthorAgent. Keep this light; the CLI drives most behavior.
    """
    allowlist: List[str] = field(default_factory=lambda: [
        "src/", "web/", "modules/", "themes/", "profiles/", "config/", "notes/"
    ])
    max_patch_bytes: int = 200_000


class CodeAuthorAgent:
    """
    Produces a plan (list of tasks) for code authoring based on a Jira issue.

    - In non-LLM mode (COPILOT_DISABLE_LLM=1 or missing OPENAI key), it emits a single,
      deterministic task that creates notes/<ISSUE>.md. This keeps runs predictable.
    - In LLM mode, it *attempts* to generate a smarter diff via copilot.ai.ai_generator,
      but falls back to the deterministic plan on any error.

    The CLI is responsible for:
      - preparing/checkout the branch,
      - iterating tasks, preview/apply patches,
      - validating, committing, pushing, and opening the MR.
    """

    def __init__(self, repo_path: str | Path, config: Optional[AuthorConfig] = None):
        self.repo_path = Path(repo_path).resolve()
        self.config = config or AuthorConfig()
        self.applier = PatchApplier(self.repo_path, allowlist=self.config.allowlist,
                                    max_bytes=self.config.max_patch_bytes)

    # ---------------------------
    # Public API used by the CLI
    # ---------------------------

    def generate_plan(self, issue: Dict[str, str]) -> List[Dict]:
        """
        Return a list of task dictionaries.
        Each task can contain:
          - title: str
          - patch: str (unified diff)  [optional for no-op tasks]
          - apply: bool (default True)
        """
        if self._disable_llm() or not self._have_openai():
            return self.generate_non_llm_plan(issue)

        # Try LLM plan; on any error, fall back.
        try:
            plan = self.generate_llm_plan(issue)
            if not plan or not isinstance(plan, list):
                return self.generate_non_llm_plan(issue)
            return plan
        except Exception:
            return self.generate_non_llm_plan(issue)

    def build_commit_message(self, issue: Dict[str, str]) -> str:
        """
        Create a concise, conventional commit message for the applied changes.
        """
        key = issue.get("key") or issue.get("id") or "TASK"
        summary = issue.get("summary") or issue.get("title") or "Automated change"
        lines = [
            f"feat: {key} — {summary}",
            "",
            f"Auto-authored by Co-Pilot on {self._now_iso()}",
            "",
            f"Refs: {key}",
        ]
        return "\n".join(lines)

    def build_mr_description(self, issue: Dict[str, str]) -> str:
        """
        MR body; the workflow CLI may extend this with diff stats.
        """
        key = issue.get("key") or issue.get("id") or "TASK"
        summary = issue.get("summary") or issue.get("title") or "Automated change"
        body = textwrap.dedent(f"""
        Auto-generated MR for {key}: {summary}

        This change was prepared by the Co-Pilot automation.
        """).strip()
        return body

    # --------------------------------
    # Non-LLM deterministic fallback
    # --------------------------------

    def generate_non_llm_plan(self, issue: Dict[str, str]) -> List[Dict]:
        """
        Deterministic, quota-free fallback: create a small notes file.
        IMPORTANT: Only one patch task to prevent duplicate-apply errors.
        """
        patch = self._make_placeholder_patch(issue)
        return [
            {
                "title": "Create placeholder notes file",
                "patch": patch,
                "apply": True,
            }
        ]

    def _make_placeholder_patch(self, issue: Dict[str, str]) -> str:
        """
        Build a minimal unified diff that adds notes/<KEY>.md with a small summary.
        """
        key = (issue.get("key") or issue.get("id") or "TASK").strip()
        summary = (issue.get("summary") or issue.get("title") or "Automated change").strip()
        fname = f"notes/{key}.md"

        content = textwrap.dedent(f"""\
        # {key} — {summary}

        This placeholder change was created in non-LLM mode (COPILOT_DISABLE_LLM=1).

        ## Jira
        - Key: {key}
        - Summary: {summary}

        ## Description
        This is a test to check if the Co-Pilot can fetch ticket data via Jira API.
        """)
        # Ensure trailing newline
        if not content.endswith("\n"):
            content += "\n"

        # Build a simple unified diff for a *new* file
        lines = content.splitlines(keepends=False)
        n = len(lines)
        plus_lines = "".join(f"+{ln}\n" for ln in lines)

        diff = textwrap.dedent(f"""\
        diff --git a/{fname} b/{fname}
        new file mode 100644
        index 0000000..1111111
        --- /dev/null
        +++ b/{fname}
        @@ -0,0 +{n} @@
        {plus_lines}""")

        return diff

    # ---------------------------
    # Optional LLM-based planning
    # ---------------------------

    def generate_llm_plan(self, issue: Dict[str, str]) -> List[Dict]:
        """
        Attempt to produce a better plan/diff using the LLM.
        If anything goes wrong, the caller will fall back to non-LLM.
        """
        # Import lazily to avoid hard dependency when running in non-LLM mode
        from copilot.ai.ai_generator import plan_diff_for_issue  # type: ignore

        # The generator should return either a single diff string or a list of task dicts.
        result = plan_diff_for_issue(self.repo_path, issue)

        # If it's a plain diff, wrap into a single task
        if isinstance(result, str):
            return [{
                "title": "Apply AI-authored diff",
                "patch": result,
                "apply": True,
            }]

        # If it's already a list of tasks, lightly validate shape
        tasks: List[Dict] = []
        if isinstance(result, list):
            for i, t in enumerate(result, start=1):
                title = t.get("title") or f"AI Task {i}"
                patch = t.get("patch")
                apply = t.get("apply", True)
                if patch:
                    tasks.append({"title": title, "patch": patch, "apply": bool(apply)})
            # Ensure we return something
            if tasks:
                return tasks

        # Fallback if shape is unexpected
        return self.generate_non_llm_plan(issue)

    # ---------------------------
    # Helpers
    # ---------------------------

    def _disable_llm(self) -> bool:
        flag = os.getenv("COPILOT_DISABLE_LLM", "").strip().lower()
        return flag in ("1", "true", "yes", "on")

    def _have_openai(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    @staticmethod
    def _now_iso() -> str:
        return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
