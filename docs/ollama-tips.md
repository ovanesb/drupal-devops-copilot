## 🖥️ Local LLM (Ollama) tips
Workflow (safe path)
```bash
# Install Ollama
# macOS: brew install ollama
# Linux: see https://ollama.com

ollama pull qwen2.5-coder:14b-instruct-q4_K_M
ollama run  qwen2.5-coder:14b-instruct-q4_K_M "hello"

# confirm model is warm (keep_alive)
ollama ps
```

Tuning:
- Lower latency: keep model warm (`COPILOT_KEEP_ALIVE=15m`)
- Control output: `COPILOT_NUM_PREDICT`, `COPILOT_NUM_CTX`, `COPILOT_TEMPERATURE`
- If you see timeouts, reduce `NUM_PREDICT` or try the 7B quantized coder