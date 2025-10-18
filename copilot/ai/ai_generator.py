# copilot/ai/ai_generator.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from importlib import resources as importlib_resources

# Jinja rendering helper (strict-undefined) from your utils
from copilot.utils.templating import render_template

# Context builder + providers live under copilot.context.*
# (We only need the builder instance passed in; providers are called via that.)
# from copilot.context.context_builder import ContextBuilder  # for type hints only


# ----------------------------
# Minimal OpenAI LLM client
# ----------------------------
try:
    from openai import OpenAI  # SDK v1.x
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


class LLMClient:
    """
    Thin wrapper around OpenAI's Chat Completions API (SDK v1.x).
    Configure with environment variables:
      - OPENAI_API_KEY
      - LLM_MODEL (optional; default: gpt-4o-mini)
    """

    def __init__(self):
        if OpenAI is None:
            raise RuntimeError(
                "OpenAI SDK not available. Install the 'openai' package or switch to your provider."
            )
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=api_key)
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    def chat(
        self,
        *,
        system: str,
        user_text: str,
        temperature: float = 0.2,
        max_tokens: Optional[int] = 2048,
    ) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system or ""},
                {"role": "user", "content": user_text},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()


# ----------------------------
# AIGenerator
# ----------------------------

@dataclass
class _Prompt:
    id: str
    version: str
    template: str
    purpose: Optional[str] = None


class AIGenerator:
    """
    Renders a prompt (Jinja) with inputs + collected context, injects a system persona,
    and calls the LLM client.

    Usage:
        ai = AIGenerator(registry, context_builder)
        text = ai.generate(
            prompt_id="git_mr_template",
            inputs={"title": "...", "summary": "..."},
            context_spec={"jira": {"key": "CCS-7"}, "git": {"diff": True}},
            agent="git_copilot",
        )
    """

    def __init__(self, registry, context_builder, llm: Optional[LLMClient] = None):
        self.registry = registry
        self.context_builder = context_builder
        self.llm = llm or LLMClient()
        self._personas = self._load_system_personas()

    # -------- public API --------

    def generate(
        self,
        *,
        prompt_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        context_spec: Optional[Dict[str, Any]] = None,
        agent: str = "default",
        temperature: float = 0.2,
        max_tokens: Optional[int] = 2048,
    ) -> str:
        # 1) Collect context (Jira/Git/Drush, etc.)
        context = self._collect_context(context_spec or {})
        # variables visible to the Jinja template
        vars_for_template: Dict[str, Any] = {}
        if inputs:
            vars_for_template.update(inputs)
        # expose providers at top-level (e.g., {{ jira.key }})
        vars_for_template.update(context)

        # 2) Resolve and render prompt template
        template_text = self._get_prompt_template(prompt_id)
        user_text = render_template(template_text, vars_for_template).strip()

        # 3) Pick system persona
        system_text = self._personas.get(agent) or self._personas.get("default", "")

        # 4) Call LLM
        return self.llm.chat(
            system=system_text,
            user_text=user_text,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # -------- helpers --------

    def _collect_context(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a context dict by calling provider.fetch(...) for each key in spec.
        Works whether your ContextBuilder exposes a .build(spec) or individual providers.
        """
        # If the builder has a single .build(spec) method, prefer it.
        build = getattr(self.context_builder, "build", None)
        if callable(build):
            try:
                ctx = build(spec)  # type: ignore[call-arg]
                if isinstance(ctx, dict):
                    return ctx
            except Exception:
                # fall back to per-provider fetch below
                pass

        # Per-provider fetch: for each key in the spec, call builder.<key>.fetch(spec[key])
        ctx: Dict[str, Any] = {}
        for key, value in (spec or {}).items():
            provider = getattr(self.context_builder, key, None)
            fetch = getattr(provider, "fetch", None)
            if callable(fetch):
                try:
                    ctx[key] = fetch(value if isinstance(value, dict) else {})
                except Exception:
                    # if a provider fails, skip it; templates should use |default
                    continue
        return ctx

    def _get_prompt_template(self, prompt_id: str) -> str:
        """
        Try the registry first if it exposes a renderer; otherwise load from package
        data (copilot/prompts/prompt_db.jsonl) and return the latest matching template.
        """
        # Attempt registry.render(...) if provided
        render = getattr(self.registry, "render", None)
        if callable(render):
            try:
                # Some registries accept (prompt_id, variables) — but we only need the template here.
                # If render returns a rendered string immediately, we can't use it here (we need template).
                # So prefer a 'get_template' if present.
                pass
            except Exception:
                pass

        # Try registry.get_template(prompt_id)
        get_tmpl = getattr(self.registry, "get_template", None)
        if callable(get_tmpl):
            try:
                tmpl_text = get_tmpl(prompt_id)
                if isinstance(tmpl_text, str) and tmpl_text.strip():
                    return tmpl_text
            except Exception:
                pass

        # Fallback: read from packaged prompt_db.jsonl
        try:
            prom_file = importlib_resources.files("copilot.prompts").joinpath("prompt_db.jsonl")
            latest: Optional[_Prompt] = None
            with prom_file.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("id") != prompt_id:
                        continue
                    candidate = _Prompt(
                        id=data["id"],
                        version=str(data.get("version", "0.0.0")),
                        template=str(data.get("template", "")),
                        purpose=data.get("purpose"),
                    )
                    latest = candidate  # last-in wins (treat as latest)
            if latest and latest.template:
                return latest.template
        except Exception as e:
            raise RuntimeError(f"Unable to load prompt '{prompt_id}': {e}") from e

        raise KeyError(f"Prompt '{prompt_id}' not found")

    def _load_system_personas(self) -> Dict[str, str]:
        """
        Load personas from system_messages.yaml shipped in copilot.prompts.
        """
        import yaml

        try:
            sys_file = importlib_resources.files("copilot.prompts").joinpath("system_messages.yaml")
            with sys_file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                # Coerce all persona texts to strings
                return {str(k): (str(v) if v is not None else "") for k, v in data.items()}
        except Exception as e:
            # If the file is missing, fall back to a minimal default persona
            return {
                "default": (
                    "You are Drupal DevOps Co-Pilot. Be concise and accurate. "
                    "If suggesting commands, prefer safe, idempotent steps. "
                    "If anything is destructive, clearly label it and provide a rollback."
                )
            }


__all__ = ["AIGenerator", "LLMClient"]
