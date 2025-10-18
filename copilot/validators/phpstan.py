from __future__ import annotations
import os
import shutil
import subprocess
import shlex
from typing import List

PHPSTAN_BIN = os.getenv("PHPSTAN_BIN", "vendor/bin/phpstan")
PHPSTAN_LEVEL = os.getenv("PHPSTAN_LEVEL", "max")


def phpstan_check(paths: List[str]) -> None:
    """Run PHPStan on the given paths. Skips if none or binary missing.

    To force failure when missing, set PHPSTAN_REQUIRED=1.
    """
    if not paths:
        return

    required = os.getenv("PHPSTAN_REQUIRED", "0") == "1"

    phpstan_path = shutil.which(PHPSTAN_BIN) or (PHPSTAN_BIN if os.path.exists(PHPSTAN_BIN) else None)
    if not phpstan_path:
        msg = f"PHPStan not found (looked for {PHPSTAN_BIN}); skipping."
        if required:
            raise RuntimeError(msg)
        print("!", msg)
        return

    cmd = [phpstan_path, "analyse", "-l", PHPSTAN_LEVEL] + paths
    print("$", " ".join(shlex.quote(c) for c in cmd))
    subprocess.check_call(cmd)