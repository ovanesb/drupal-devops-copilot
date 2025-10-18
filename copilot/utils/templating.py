# copilot/utils/templating.py
from __future__ import annotations
from jinja2 import Environment, BaseLoader, StrictUndefined

_env = Environment(loader=BaseLoader(), undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)

def render_template(template: str, data: dict) -> str:
    return _env.from_string(template).render(**data)