# Contributing to Drupal DevOps Co-Pilot

Thank you for helping make Drupal DevOps Co-Pilot better!  
We welcome contributions of all kinds — ideas, bug fixes, documentation, and feature improvements.

---

## 🧱 Project Goals

The goal of this project is to build an **AI-powered assistant for Drupal developers and DevOps engineers**, automating repetitive workflows like:

- Branch creation, commits, and merge requests
- Drush QA, EC2 deployments, and Jira transitions
- AI-based code generation and review

Please keep changes aligned with these goals — this ensures the project stays lean, open, and useful.

---

## ⚙️ Getting Started

### 1. Fork and clone
```bash
git clone https://github.com/your-username/drupal-devops-copilot.git
cd drupal-devops-copilot
```

### 2. Create a feature branch
```bash
git checkout -b feature/my-awesome-improvement
```
### 3. Set up your environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,llm,ui]"
```

### 4. Run checks
```bash
ruff . || true
python -m unittest || true
```

### 5. Submit your PR
Open a pull request with a clear title and short description.<br />
If it’s linked to an issue, include the issue number (e.g., `“Fixes #42”`).

---
## 🧩 Commit Message Convention
Follow Conventional Commits for clarity and automation:

```acss
    feat(ai): add manifest fallback for module generation
    fix(cli): correct invalid JSON escape handling
    docs(readme): update setup section
```
This keeps the changelog clean and predictable.

---
## 💬 Questions or Ideas?

Start a GitHub Discussion under:
- 💡 Ideas for feature suggestions
- 🛠 Q&A for setup help
- 🧭 RFCs for architectural proposals

---
Thank you for contributing! <br />
— _Ovanes Budakyan & Contributors_

---
[Back to README.md](../README.md)