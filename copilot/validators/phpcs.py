from __future__ import annotations
import os
import shutil
import subprocess
import shlex
from typing import List

PHPCS_BIN = os.getenv("PHPCS_BIN", "vendor/bin/phpcs")
PHPCS_STANDARD = os.getenv("PHPCS_STANDARD", "Drupal,DrupalPractice")
PHPCS_EXTS = os.getenv("PHPCS_EXTS", "php,module,inc,install,theme")


def phpcs_check(files: List[str]) -> None:
    """Run PHPCS on the provided files. Skips if none or binary missing.

    To force a failure when PHPCS is missing, set PHPCS_REQUIRED=1.
    """
    if not files:
        return

    required = os.getenv("PHPCS_REQUIRED", "0") == "1"

    # Resolve binary: support both PATH lookup and repo-local path
    phpcs_path = shutil.which(PHPCS_BIN) or (PHPCS_BIN if os.path.exists(PHPCS_BIN) else None)
    if not phpcs_path:
        msg = f"PHPCS not found (looked for {PHPCS_BIN}); skipping."
        if required:
            raise RuntimeError(msg)
        print("!", msg)
        return

    cmd = [
        phpcs_path,
        "--standard=" + PHPCS_STANDARD,
        "--extensions=" + PHPCS_EXTS,
        "--report=full",
    ] + files

    # Optional: support PHP version gate; default allow 8.1+
    phpver = os.getenv("PHPCS_PHP_VERSION", "8.1-")
    if phpver:
        cmd += ["--runtime-set", "testVersion", phpver]

    print("$", " ".join(shlex.quote(c) for c in cmd))
    subprocess.check_call(cmd)