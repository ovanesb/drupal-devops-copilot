# copilot/codegen/patch_applier.py
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable, List, Optional, Tuple


class PatchApplyError(Exception):
    """Raised when the sanitized patch still fails to apply."""
    pass


class PatchApplier:
    """
    Applies unified-diff patches safely:
      • extracts only proper 'diff --git' blocks,
      • optionally restricts to allowed directories / file suffixes,
      • strips all 'index …' lines that often break `git apply`,
      • writes to a temp file and runs `git apply --index`.
    """

    DIFF_START = re.compile(r"^diff --git a/(.+?) b/(.+?)\s*$")
    # Valid 'index' lines are hex..hex (optionally with a mode); we drop all to be robust.
    INDEX_LINE = re.compile(r"^index\s+[0-9a-f]{1,40}\.\.[0-9a-f]{1,40}(?:\s+\d+)?\s*$", re.I)

    def __init__(
        self,
        allowed_dirs: Optional[Iterable[str]] = None,
        allowed_suffixes: Optional[Iterable[str]] = None,
    ) -> None:
        # Normalize prefixes to ensure trailing slash behavior is consistent.
        self.allowed_dirs = tuple(d if d.endswith("/") else f"{d}/" for d in (allowed_dirs or ()))
        self.allowed_suffixes = tuple(allowed_suffixes or ())

    # ---------- parsing ----------

    def _parse_blocks(self, text: str) -> List[Tuple[str, List[str]]]:
        """
        Split raw text into diff blocks starting with 'diff --git ...'.
        Returns list of (target_path, lines_for_block).
        """
        lines = text.splitlines(keepends=True)
        blocks: List[Tuple[str, List[str]]] = []

        i = 0
        n = len(lines)
        while i < n:
            m = self.DIFF_START.match(lines[i])
            if not m:
                i += 1
                continue

            b_path = m.group(2)  # path after b/
            block: List[str] = [lines[i]]
            i += 1

            # Accumulate until next diff start or EOF
            while i < n and not self.DIFF_START.match(lines[i]):
                block.append(lines[i])
                i += 1

            # Prefer explicit '+++ b/...' if present
            tgt = b_path
            for ln in block:
                if ln.startswith("+++ b/"):
                    tgt = ln.strip()[6:]
                    break

            blocks.append((tgt, block))

        return blocks

    # ---------- filtering / cleaning ----------

    def _accept_path(self, path: str) -> bool:
        if self.allowed_dirs:
            if not any(path.startswith(pref) for pref in self.allowed_dirs):
                return False
        if self.allowed_suffixes:
            if not any(path.endswith(suf) for suf in self.allowed_suffixes):
                return False
        return True

    def _clean_block(self, block: List[str]) -> List[str]:
        """
        Remove all 'index …' lines (valid or not). `git apply` doesn't need them and
        LLMs often produce malformed ones (e.g., non-hex chars).
        """
        cleaned: List[str] = []
        for ln in block:
            if ln.startswith("index "):
                continue
            cleaned.append(ln)
        return cleaned

    def _assemble(self, blocks: List[List[str]]) -> str:
        out: List[str] = []
        for b in blocks:
            out.extend(b)
            if not (b and b[-1].endswith("\n")):
                out.append("\n")
        return "".join(out)

    # ---------- public API ----------

    def apply_patch(self, repo_dir: str | Path, patch_text: str) -> None:
        """
        Sanitize and apply patch to repo via `git apply --index`.
        Raises PatchApplyError on failure (includes snippet of sanitized patch).
        """
        repo = Path(repo_dir).resolve()

        # Extract blocks
        blocks = self._parse_blocks(patch_text)

        # Filter and clean
        kept: List[List[str]] = []
        for tgt, block in blocks:
            if self._accept_path(tgt):
                kept.append(self._clean_block(block))

        if not kept:
            raise PatchApplyError("No eligible changes found after guardrails filtering.")

        clean_patch = self._assemble(kept)

        # Write to temporary file
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".patch") as tf:
            tf.write(clean_patch)
            tmp_path = tf.name

        try:
            cmd = ["git", "-C", str(repo), "apply", "--index", tmp_path]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                snippet = "\n".join(clean_patch.splitlines()[:60])
                raise PatchApplyError(
                    f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
                    f"{proc.stderr.strip()}\n\n"
                    f"--- first 60 lines of sanitized patch ---\n{snippet}\n"
                    f"----------------------------------------"
                )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


__all__ = ["PatchApplier", "PatchApplyError"]
