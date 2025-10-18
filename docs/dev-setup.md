
## 📄 `docs/dev-setup.md`


# 💻 Working in a New Terminal Session

A quick guide to get your local environment ready for the Drupal DevOps Co-Pilot.

---

## 1️⃣ Activate your virtual environment

```bash
  cd drupal-devops-copilot
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -e ".[dev,llm,ui]"
```

## 2️⃣ Sanity-check the environment

```bash
  which python
  which pip
  python -c "import sys; print(sys.executable)"
```

Each should point to something like:
```
/path/to/drupal-devops-copilot/.venv/bin/python
```

## 3️⃣ Install dependencies (if needed)
```bash
  pip install -U pip
  pip install -e ".[dev,llm,ui]"
  pip install fastapi "uvicorn[standard]" pydantic python-dotenv requests
```

## 4️⃣ Run the backend
From the project root:
```bash
  uvicorn server.app:app --reload --host 127.0.0.1 --port 8000
```

## 5️⃣ Run the frontend (UI)
From the `ui` folder:
```bash
  cd ui
  npm install
  npm run dev
```
The UI will start on http://localhost:3000 <br />
It communicates with the backend via http://127.0.0.1:8000.

## 6️⃣ Verify setup
In a terminal with the venv active:
```bash
  copilot-one-shot --help
```
You should see available commands such as:
```bash
  copilot-workflow
  copilot-ai-review-merge
  copilot-qa-ec2
```

---
## 🧠 Tips

- Run backend + frontend in separate terminals for clarity.
- Use `COPILOT_DEBUG_LLM=1` to write debug files under `.copilot_debug/`.
- If using Ollama, keep it warm with `COPILOT_KEEP_ALIVE=15m`.
- If switching between projects, deactivate and reactivate the venv to reload `.env` variables.

---
[Back to README.md](../README.md)