from __future__ import annotations
import shutil
import subprocess
import shlex
from typing import List

YAMLLINT_BIN = "yamllint"  # system tool


def yaml_lint(paths: List[str]) -> None:
    """Run yamllint if available. Skips silently if not installed or no paths.
    """
    if not paths:
        return

    yamllint = shutil.which(YAMLLINT_BIN)
    if not yamllint:
        print("! yamllint not found; skipping YAML lint")
        return

    cmd = [yamllint] + paths
    print("$", " ".join(shlex.quote(c) for c in cmd))
    subprocess.check_call(cmd)