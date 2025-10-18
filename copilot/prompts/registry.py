# copilot/prompts/registry.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict
import json
import os
from pathlib import Path

import yaml
from copilot.utils.templating import render_template

@dataclass
class PromptTemplate:
    id: str
    version: str
    purpose: str
    template: str


class PromptRegistry:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or os.getenv("COPILOT_PROMPTS_DIR", "copilot/prompts"))
        self._system_map = None
        self._prompts = None

    # --- System messages ---
    def get_system_message(self, agent: str) -> str:
        if self._system_map is None:
            with open(self.base_dir / "system_messages.yaml", "r", encoding="utf-8") as f:
                self._system_map = yaml.safe_load(f)
        if agent not in self._system_map:
            agent = "default"
        return self._system_map[agent]

    # --- Prompt DB ---
    def _load_prompts(self):
        prompts = {}
        with open(self.base_dir / "prompt_db.jsonl", "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                obj = json.loads(line)
                key = (obj["id"], obj["version"])
                prompts[key] = PromptTemplate(**obj)
        self._prompts = prompts

    def get_prompt(self, prompt_id: str, version: str = "latest") -> PromptTemplate:
        if self._prompts is None:
            self._load_prompts()
        if version == "latest":
            # Naive latest: pick the highest semver-ish string; customize if needed.
            versions = [v for (pid, v) in self._prompts.keys() if pid == prompt_id]
            if not versions:
                raise KeyError(f"Prompt not found: {prompt_id}")
            version = sorted(versions)[-1]
        key = (prompt_id, version)
        if key not in self._prompts:
            raise KeyError(f"Prompt not found: {prompt_id}@{version}")
        return self._prompts[key]

    def render_prompt(self, prompt: PromptTemplate, data: Dict[str, Any]) -> str:
        return render_template(prompt.template, data)