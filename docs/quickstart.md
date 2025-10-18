## 🚀 Quickstart (local)

```bash
# 1) Clone
git clone https://gitlab.com/your-org/drupal-devops-copilot.git
cd drupal-devops-copilot

# 2) Python virtualenv
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt

# 3) (Option A) Local LLM with Ollama
# Install: https://ollama.com/download
ollama pull qwen2.5-coder:14b-instruct-q4_K_M

# 4) (Option B) Or use OpenAI-compatible endpoint
# Set OPENAI_BASE_URL + OPENAI_API_KEY instead of Ollama

# 5) Prepare a Drupal repo to act on
mkdir -p work
git clone https://gitlab.com/your-org/drupal-project.git work/drupal-project
```

Create a `.env` in project root (see Configuration below) and then:
```bash
# Smoke test: list help
python -m copilot.cli.one_shot --help
```

---
[Back to README.md](../README.md)