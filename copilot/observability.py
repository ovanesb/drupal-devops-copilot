# copilot/observability.py
from __future__ import annotations
import io
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

AUDIT_LOG = os.getenv("COPILOT_AUDIT_LOG", "runtime/audit.log.jsonl")
os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)

_lock = threading.Lock()

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def audit_log(
    *,
    run_id: str,
    action: str,
    status: str,
    params: Dict[str, Any] | None = None,
    message: str | None = None,
    extra: Dict[str, Any] | None = None,
) -> None:
    """
    Append one JSON line to the audit file.
    status: "start" | "ok" | "error" | "skip"
    """
    rec = {
        "ts": _now_iso(),
        "run_id": run_id,
        "action": action,
        "status": status,
        "params": params or {},
        "message": message or "",
        **(extra or {}),
    }
    line = json.dumps(rec, ensure_ascii=False)
    with _lock:
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")

def _read_lines(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def list_events(limit: int = 200) -> List[Dict[str, Any]]:
    lines = _read_lines(AUDIT_LOG)
    if not lines:
        return []
    tail = lines[-limit:]
    events: List[Dict[str, Any]] = []
    for ln in tail:
        try:
            events.append(json.loads(ln))
        except Exception:
            continue
    return events

def list_run(run_id: str) -> List[Dict[str, Any]]:
    lines = _read_lines(AUDIT_LOG)
    out: List[Dict[str, Any]] = []
    for ln in lines:
        try:
            rec = json.loads(ln)
            if rec.get("run_id") == run_id:
                out.append(rec)
        except Exception:
            continue
    return out
