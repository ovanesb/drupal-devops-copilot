from __future__ import annotations
import os
import shutil
import subprocess
import shlex
from typing import List

TWIGCS_BIN = os.getenv("TWIGCS_BIN", "vendor/bin/twigcs")


def twigcs_check(paths: List[str]) -> None:
    """Run TwigCS on the provided paths (twig templates). Skips if missing.

    To force failure when missing, set TWIGCS_REQUIRED=1.
    """
    if not paths:
        return

    required = os.getenv("TWIGCS_REQUIRED", "0") == "1"

    twigcs_path = shutil.which(TWIGCS_BIN) or (TWIGCS_BIN if os.path.exists(TWIGCS_BIN) else None)
    if not twigcs_path:
        msg = f"TwigCS not found (looked for {TWIGCS_BIN}); skipping."
        if required:
            raise RuntimeError(msg)
        print("!", msg)
        return

    cmd = [twigcs_path] + paths
    print("$", " ".join(shlex.quote(c) for c in cmd))
    subprocess.check_call(cmd)