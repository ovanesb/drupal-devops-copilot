## 🔧 Troubleshooting

**Model returns invalid JSON**
- Ensure `COPILOT_NUM_PREDICT` isn’t too low (cut off output)
- Turn on `COPILOT_DEBUG_LLM=1` and inspect .copilot_debug/manifest_raw.txt
- Use `--force-manifest` for scaffolds

**PHP parse errors during QA**
- Sanitizer should unescape `\$var` and remove stray `declare(strict_types)`
- If needed, re-run `copilot-qa-ec2 <JIRA-KEY>` to validate again

**Writes to wrong docroot (`docroot/` vs `web/`)**
- Confirm your Drupal repo uses `web/` and keep prompts precise
- Guardrails default to `web/modules/custom/`

**GitLab rejects push**
- If you rewrote history: unprotect or temporarily allow force-push
- Verify `GITLAB_TOKEN` scope if using API features