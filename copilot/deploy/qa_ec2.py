from __future__ import annotations
import os, httpx

SITE = os.getenv("SITE_BASE_URL", "http://localhost")

async def _get(path: str) -> tuple[int, str]:
    url = SITE.rstrip("/") + path
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url)
        return r.status_code, r.text[:1000]

async def smoke() -> list[str]:
    """
    Minimal HTTP smoke: homepage + login page.
    """
    log = []
    for p in ("/", "/user/login"):
        code, _ = await _get(p)
        ok = "OK" if 200 <= code < 400 else "FAIL"
        log.append(f"[qa] GET {p} → {code} {ok}")
    return log
