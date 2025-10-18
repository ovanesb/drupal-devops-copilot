from __future__ import annotations
from typing import Optional, Dict, Any

from copilot.ai.ai_generator import AIGenerator


class DiffAgent:
    """Asks the LLM to produce a **unified diff** for a single, atomic task.

    The prompt used is `code_author_diff` from the prompt DB and should instruct
    the model to return *only* a patch that `git apply` can consume.
    """

    def __init__(self, ai: AIGenerator):
        self.ai = ai

    def generate_patch(
        self,
        *,
        task_text: str,
        jira_key: str,
        extra_context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.15,
        max_tokens: Optional[int] = 4096,
    ) -> str:
        ctx = {"jira": {"key": jira_key}}
        if extra_context:
            # shallow merge for convenience
            ctx.update(extra_context)

        raw = self.ai.generate(
            prompt_id="code_author_diff",
            inputs={"task_text": task_text},
            context_spec=ctx,
            agent="default",
            temperature=temperature,
            max_tokens=max_tokens,
        )

        patch = _strip_fences(raw).strip()
        return patch


def _strip_fences(text: str) -> str:
    """Remove accidental markdown code fences/backticks if the model emitted any."""
    lines = text.strip().splitlines()
    if not lines:
        return text
    # Remove leading fence
    if lines[0].startswith("```"):
        lines = lines[1:]
    # Remove trailing fence
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines)