# copilot/context/providers/git_provider.py
from __future__ import annotations
from typing import Any, Dict
import subprocess

class GitProvider:
    def fetch(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if spec.get("diff"):
            base = spec.get("base", "origin/develop")
            head = spec.get("head", "HEAD")
            diff_cmd = ["git", "diff", f"{base}..{head}", "--name-status"]
            data["diff_summary"] = subprocess.check_output(diff_cmd, text=True).strip()
        return data