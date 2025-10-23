from fastapi import FastAPI

app = FastAPI(title="Drupal DevOps Co-Pilot API")

@app.get("/healthz")
def healthz():
    return {"status": "ok"}
