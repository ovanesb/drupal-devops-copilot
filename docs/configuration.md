## ⚙️ Configuration (environment variables)
Create a `.env` from `.env.example` (or export in your shell) <br />
`.env.example` contains full list of variables:

```dotenv
# --- Provider selection ---
# ollama | openai | openai_compat
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5-coder:14b-instruct-q4_K_M

# Ollama (local)
OLLAMA_HOST=http://127.0.0.1:11434

# OpenAI-compatible (optional)
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_API_KEY=sk-...

# GitLab
GITLAB_BASE_URL=https://gitlab.com
# to create MRs via API
GITLAB_TOKEN=<your token>

# Jira (optional)
# JIRA_BASE_URL=https://your-domain.atlassian.net
# JIRA_EMAIL=you@example.com
# JIRA_API_TOKEN=<token>

# Deploy target (used by scripts/ QA)
EC2_SSH_HOST=ubuntu@your-ec2-host
EC2_SSH_KEY=~/.ssh/your-key.pem

# LLM reliability & speed
# hint for Ollama
COPILOT_KEEP_ALIVE=15m
COPILOT_NUM_PREDICT=800
COPILOT_NUM_CTX=4096
COPILOT_TEMPERATURE=0.1
# seconds
COPILOT_REQUEST_TIMEOUT=300

# Debugging
# set 1 to write .copilot_debug/*
COPILOT_DEBUG_LLM=0
```

> The code automatically falls back from patch → manifest and repairs JSON/escapes for robustness.

---
[Back to README.md](../README.md)