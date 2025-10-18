# tests/test_prompt_engine.py
from copilot.prompts.registry import PromptRegistry
from copilot.utils.templating import render_template


def test_render_template_basic():
    out = render_template("Hello {{ name }}", {"name": "Ovanes"})
    assert out == "Hello Ovanes"


def test_registry_loads_system_messages(tmp_path):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system_messages.yaml").write_text("default: 'Hi'\n", encoding="utf-8")
    (prompts_dir / "prompt_db.jsonl").write_text("", encoding="utf-8")

    reg = PromptRegistry(base_dir=str(prompts_dir))
    assert reg.get_system_message("default") == "Hi"