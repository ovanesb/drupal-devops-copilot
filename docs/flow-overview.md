## 📄 `docs/flow-overview.md`

--- 
# ⚙️ Flow Overview

### AI Review → Merge → Deploy → QA Verify

The Drupal DevOps Co-Pilot orchestrates a full Jira → GitLab → EC2 → Drupal workflow.  
Each step can be run independently or combined for a fully automated pipeline.

---

## 🧩 Auto-Dev (Create & Prepare) Full Cycle

```bash
copilot-one-shot <JIRA-KEY>
```

### What happens
- Creates a feature branch from `main`
- Generates code via the LLM
- Commits and pushes changes
- Opens a Merge Request:
  - Title → `[<Jira key>]: <Jira ticket title>`
  - Labels → `["autodev"]`
  - Reviewer → `Copilot Developer` 
- Updates Jira:
  - Transition → `IN REVIEW`
  - Adds comment with MR link
- Posts AI review note on the MR
- Updates labels → `["ai-change", "ai-reviewed", "autodev"]`
- Confirms merge status (mergeable)
- Merges into staging branch
- Triggers deploy
- Updates Jira:
    - Transition → `IN STAGING`
    - Adds comment with merge details
- Connects to EC2 and runs Drush QA
- Monitors GitLab pipeline until completion
- Collects job statuses:
    ```bash {'jira:ready-for-qa': 'success', 'qa:smoke-env': 'success',
      'deploy:staging': 'success', 'phpcs': 'success', 'yamllint': 'success'}
    ```
- Updates Jira:
    - Transition → `READY FOR RELEASE` or `QA FAILED`
    - Adds comment with QA results

---

## 🧩 Step 1 Auto-Dev (Create & Prepare)

```bash
copilot-workflow <JIRA-KEY>
```

### What happens
- Creates a feature branch from `main`
- Generates code via the LLM
- Commits and pushes changes
- Opens a Merge Request:
    - Title → `[<Jira key>]: <Jira ticket title>`
    - Labels → `["autodev"]`
    - Reviewer → `Copilot Developer`
- Updates Jira:
    - Transition → `IN REVIEW`
    - Adds comment with MR link

## 🧠 Step 2 — AI Review & Merge

```bash
copilot-ai-review-merge "https://gitlab.com/<project>/-/merge_requests/<ID>" \
  --auto-merge \
  --deploy \
  --verbose
```

### What happens

- Posts AI review note on the MR
- Updates labels → `["ai-change", "ai-reviewed", "autodev"]`
- Confirms merge status (mergeable)
- Merges into staging branch
- Triggers deploy
- Updates Jira:
  - Transition → `IN STAGING` 
  - Adds comment with merge details

## 🚀 Step 3 — QA Verification

```bash
copilot-qa-ec2 <JIRA-KEY>
```

### What happens
- Connects to EC2 and runs Drush QA
- Monitors GitLab pipeline until completion
- Collects job statuses: 
    ```bash {'jira:ready-for-qa': 'success', 'qa:smoke-env': 'success',
      'deploy:staging': 'success', 'phpcs': 'success', 'yamllint': 'success'}
    ```
- Updates Jira:
  - Transition → `READY FOR RELEASE` or `QA FAILED`
  - Adds comment with QA results

---
## 🧭 Summary

| Command                       | Purpose                                |
| ----------------------------- | -------------------------------------- |
| `copilot-one-shot`            | Create branch, generate code, open MR  |
| `copilot-ai-review-merge`     | Perform AI review, merge, deploy       |
| `copilot-qa-ec2`              | Run Drush QA and update Jira           |

---
With these commands, you can automate the entire development workflow from Jira ticket creation to deployment and QA verification, streamlining your Drupal DevOps process.

---
[Back to README.md](../README.md)