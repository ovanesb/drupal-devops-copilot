# copilot/scaffolds/drupal_module.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

INFO_TEMPLATE = """name: '{name}'
type: module
description: '{description}'
core_version_requirement: ^11 || ^10
package: 'Custom'
"""

MODULE_TEMPLATE = """<?php

/**
 * @file
 * {name} module file.
 */

/**
 * Implements hook_help().
 */
function {machine}_help($route_name, \Drupal\Core\Routing\RouteMatchInterface $route_match) {
  if ($route_name === 'help.page.{machine}') {
    return t('{help_text}');
  }
  return '';
}
"""

ROUTING_TEMPLATE = """help.page.{machine}:
  path: '/admin/help/{machine}'
  defaults:
    _title: '{name} help'
    _controller: '\\Drupal\\system\\Controller\\HelpController::help'
  requirements:
    _permission: 'access administration pages'
"""

README_TEMPLATE = """# {name}

{description}

## What it does

- Demonstration module scaffolded by Co-Pilot.
- Provides a simple `hook_help()` page under `/admin/help/{machine}`.

## How to test

- Enable the module in Extend.
- Visit `/admin/help/{machine}` and confirm the help text appears.

"""

def scaffold_module(
    repo_root: str,
    machine: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    help_text: Optional[str] = None,
) -> Path:
    """
    Create a minimal Drupal 10/11 compatible custom module skeleton.

    Returns the module directory Path.
    """
    name = name or machine.replace("_", " ").title()
    description = description or f"{name} module."
    help_text = help_text or f"Help for {name}."

    base = Path(repo_root)
    mod_dir = base / "modules" / "custom" / machine
    mod_dir.mkdir(parents=True, exist_ok=True)

    # info.yml
    (mod_dir / f"{machine}.info.yml").write_text(
        INFO_TEMPLATE.format(name=name, description=description), encoding="utf-8"
    )

    # .module
    (mod_dir / f"{machine}.module").write_text(
        MODULE_TEMPLATE.format(name=name, machine=machine, help_text=help_text),
        encoding="utf-8",
    )

    # routing.yml (optional but nice for help page)
    (mod_dir / f"{machine}.routing.yml").write_text(
        ROUTING_TEMPLATE.format(name=name, machine=machine),
        encoding="utf-8",
    )

    # README
    (mod_dir / "README.md").write_text(
        README_TEMPLATE.format(name=name, description=description, machine=machine),
        encoding="utf-8",
    )

    return mod_dir
