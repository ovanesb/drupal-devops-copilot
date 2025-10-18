from __future__ import annotations
import shutil
import subprocess
import shlex
from typing import List

SUPPORTED_EXTS = (".php", ".module", ".inc", ".install", ".theme")


def php_lint(files: List[str]) -> None:
    """Run `php -l` on each PHP-ish file. Raises on first failure.

    Skips silently if no matching files. Raises RuntimeError if `php` not found.
    """
    php_bin = shutil.which("php")
    if not php_bin:
        raise RuntimeError("php binary not found in PATH")

    targets = [f for f in files if f.endswith(SUPPORTED_EXTS)]
    if not targets:
        return

    for f in targets:
        cmd = [php_bin, "-l", f]
        print("$", " ".join(shlex.quote(c) for c in cmd))
        subprocess.check_call(cmd)