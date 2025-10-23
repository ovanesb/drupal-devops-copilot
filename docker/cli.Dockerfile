FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    git openssh-client && \
    rm -rf /var/lib/apt/lists/*

# bring in the repo (pruned by .dockerignore)
COPY . .

# editable install if packaging exists; fallback otherwise
RUN bash -lc 'if [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then \
      pip install -e .; \
    else \
      pip install --no-cache-dir click; \
    fi'

RUN pip install --no-cache-dir requests python-dotenv
ENTRYPOINT ["bash","-lc"]
