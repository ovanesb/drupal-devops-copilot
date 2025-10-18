## 🧰 CLI reference
```bash
# One-shot end-to-end
copilot-one-shot <JIRA-KEY>

# Prepare branch, run LLM, open MR (no auto-merge)
copilot-workflow <JIRA-KEY>

# AI review + (optional) auto-merge + (optional) deploy
copilot-ai-review-merge "<MR_URL>" [--auto-merge] [--deploy] [--verbose]

# Run QA on EC2 target (Drush checks)
copilot-qa-ec2 <JIRA-KEY>
```

Common flags::
- `--provider ollama|openai|openai_compat`
- `--model qwen2.5-coder:14b-instruct-q4_K_M` (good local balance)
  or `qwen2.5-coder:7b-instruct-q4_0` (lighter)
- `--allow-outside-custom` (debug only; disables path guardrails)

---
[Back to README.md](../README.md)