# Dockerfile

FROM python:3.10-slim

# Add Git and optionally curl for future
RUN apt-get update && \
    apt-get install -y git curl && \
    apt-get clean

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "scripts/run_task.py"]
