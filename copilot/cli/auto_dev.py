#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, List

# ---------- Shell helpers ----------

def sh(cmd: list[str], cwd: Optional[str] = None, check: bool = True) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}")
    return result

def run_out(cmd: list[str], cwd: Optional[str] = None) -> str:
    return subprocess.check_output(cmd, cwd=cwd, text=True).strip()

def ensure_repo(repo_path: str) -> None:
    if not (Path(repo_path) / ".git").exists():
        raise RuntimeError(f"Not a git repo: {repo_path}")

# ---------- Small utils ----------

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    return v if v not in (None, "") else default

def slugify_machine_name(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "co_pilot_created_module"

def current_branch(repo: str) -> str:
    return run_out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)

def git_add(repo: str, paths: List[str]) -> None:
    if paths:
        sh(["git", "add"] + paths, cwd=repo)

# ---------- Docroot detection (web/, env override, fallback) ----------

def get_docroot(repo_path: str) -> Path:
    """
    1) COPILOT_DOCROOT env (e.g. 'web', 'docroot', '.')
    2) '<repo>/web' if exists
    3) repo root
    """
    repo = Path(repo_path)
    env = os.getenv("COPILOT_DOCROOT", "").strip()
    if env:
        p = (repo / env).resolve()
        if p.exists():
            return p
        if env in (".", "./"):
            return repo.resolve()
    web = repo / "web"
    if web.exists():
        return web.resolve()
    return repo.resolve()

def module_custom_dir(repo_path: str) -> Path:
    d = get_docroot(repo_path) / "modules" / "custom"
    d.mkdir(parents=True, exist_ok=True)
    return d

# ---------- Module scaffold ----------

def write_file(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

def scaffold_drupal11_module(repo: str, machine_name: str) -> list[str]:
    """
    Create a minimal Drupal 11 module with one Block plugin under:
      <docroot>/modules/custom/<machine_name>/
    Returns paths relative to repo root that were created.
    """
    base = module_custom_dir(repo) / machine_name
    info_yml = base / f"{machine_name}.info.yml"
    module_php = base / f"{machine_name}.module"
    block_php = base / "src" / "Plugin" / "Block" / "CoPilotCreatedModuleBlock.php"

    info_yml_body = f"""name: '{machine_name.replace("_", " ").title()}'
type: module
description: 'A Drupal module added by the Co-Pilot.'
core_version_requirement: ^11
package: Custom
"""
    module_php_body = """<?php

/**
 * @file
 * Minimal module file. Main functionality is provided by a Block plugin.
 */
"""

    block_php_body = f"""<?php

namespace Drupal\\{machine_name}\\Plugin\\Block;

use Drupal\\Core\\Block\\BlockBase;

/**
 * Provides a 'Co-Pilot Created Module' block.
 *
 * @Block(
 *   id = "{machine_name}_block",
 *   admin_label = @Translation("Co-Pilot Created Module Block"),
 * )
 */
class CoPilotCreatedModuleBlock extends BlockBase {{

  /**
   * {{@inheritdoc}}
   */
  public function build() {{
    return [
      '#markup' => $this->t('This is the content of the Co-Pilot Created Module block.'),
    ];
  }}

}}
"""

    write_file(info_yml, info_yml_body)
    write_file(module_php, module_php_body)
    write_file(block_php, block_php_body)

    # Return repo-relative paths
    rel_paths = [
        str(info_yml.relative_to(repo)),
        str(module_php.relative_to(repo)),
        str(block_php.relative_to(repo)),
    ]
    return rel_paths

# ---------- Main ----------

def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Drupal DevOps Co-Pilot — deterministic auto-dev scaffolder (writes and stages files; no commit/push/MR)"
    )
    p.add_argument("issue_key", help="Jira issue key, e.g., CCS-62")
    p.add_argument("--repo", required=True, help="Path to target git repo")
    p.add_argument("--execute", action="store_true", help="Write files and stage them (git add)")
    p.add_argument("--module-name", default=_env("COPILOT_MODULE_NAME", "co_pilot_created_module"),
                   help="Drupal machine name for the module (default: co_pilot_created_module)")
    args = p.parse_args(argv)

    repo = os.path.abspath(args.repo)
    ensure_repo(repo)

    machine_name = slugify_machine_name(args.module_name)
    print(f"[CFG] issue_key={args.issue_key} execute={args.execute} repo={repo}")
    print(f"[CFG] module={machine_name} branch={current_branch(repo)}")
    print(f"[CFG] docroot={get_docroot(repo)}")

    created: list[str] = []

    if args.execute:
        created = scaffold_drupal11_module(repo, machine_name)
        # Stage files only; commit/push/MR are handled by copilot-workflow
        git_add(repo, created)
        print("\n>>> Created & staged files:")
        for f in created:
            print(" -", f)
        print("\nDone.")
    else:
        # Dry-run: show what WOULD be created, without touching FS
        base = module_custom_dir(repo) / machine_name  # ensures custom dir exists; we won't write files
        info_yml = base / f"{machine_name}.info.yml"
        module_php = base / f"{machine_name}.module"
        block_php = base / "src" / "Plugin" / "Block" / "CoPilotCreatedModuleBlock.php"
        created = [
            str(info_yml.relative_to(repo)),
            str(module_php.relative_to(repo)),
            str(block_php.relative_to(repo)),
        ]
        print(">>> Plan (dry-run): would create files:")
        for f in created:
            print(" -", f)

    # JSON summary for the caller
    print(json.dumps({
        "ok": True,
        "issue_key": args.issue_key,
        "branch": current_branch(repo),
        "created_files": created,
        "executed": bool(args.execute),
        "committed": False,
        "mr_url": "",
    }))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
