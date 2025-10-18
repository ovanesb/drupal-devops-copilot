# copilot/context/providers/drush_provider.py
from __future__ import annotations
from typing import Any, Dict
import subprocess

class DrushProvider:
    def fetch(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if spec.get("status"):
            try:
                out = subprocess.check_output(["drush", "status", "--format=json"], text=True)
                data["status_json"] = out
            except Exception as e:
                data["status_error"] = str(e)
        return data