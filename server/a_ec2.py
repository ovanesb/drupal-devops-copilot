# server/qa_ec2.py
import os, httpx, asyncio
SITE = os.getenv("SITE_BASE_URL", "http://localhost")

async def _get(path: str) -> tuple[int, str]:
    url = SITE.rstrip("/") + path
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        return r.status_code, r.text[:2000]

async def smoke() -> list[str]:
    log = []
    for p in ("/", "/user/login"):
        code, body = await _get(p)
        ok = "OK" if 200 <= code < 400 else "FAIL"
        log.append(f"[qa] GET {p} → {code} {ok}")
    return log
