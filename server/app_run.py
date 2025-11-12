import asyncio, json, shlex, uuid, re
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()
_jobs: dict[str, asyncio.Queue[str] | None] = {}

class RunRequest(BaseModel):
    workflow: dict
    dry_run: bool = False

def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

MR_URL_RE = re.compile(r"https?://[^ \n\r\t>]+/-/merge_requests/\d+")

async def run_cmd(queue: asyncio.Queue[str], label: str, cmd: str) -> int:
    await queue.put(sse("step", {"label": label, "cmd": cmd}))
    p = await asyncio.create_subprocess_exec(
        *shlex.split(cmd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    while True:
        line = await p.stdout.readline()
        if not line:
            break
        text = line.decode(errors="ignore")
        await queue.put(sse("log", {"label": label, "line": text}))
    rc = await p.wait()
    await queue.put(sse("done", {"label": label, "rc": rc}))
    return rc

def pick_jira_key(workflow: dict) -> str | None:
    # Minimal: JiraTrigger node’s data.label OR data.projectKey can carry the key
    nodes = workflow.get("nodes") or []
    for n in nodes:
        if (n.get("type") or "").lower().replace("_","") in ("jiratrigger",):
            data = n.get("data") or {}
            # Prefer a concrete key if user typed it as the node title/label
            key = data.get("label") or data.get("projectKey")
            if key and "-" in key:
                return key
    # Fallback: first node title that looks like JIRA-123
    for n in nodes:
        data = (n.get("data") or {})
        lbl = data.get("label")
        if isinstance(lbl, str) and "-" in lbl:
            return lbl
    return None

@router.post("/run")
async def run(req: RunRequest):
    job_id = str(uuid.uuid4())
    q: asyncio.Queue[str] = asyncio.Queue()
    _jobs[job_id] = q

    async def worker():
        try:
          # 1) Resolve JIRA key
          jira_key = pick_jira_key(req.workflow)
          if not jira_key:
              await q.put(sse("error", {"msg": "No JIRA key found in workflow (set JiraTrigger title to e.g. CCS-123)"}))
              return

          # 2) Execute happy path
          rc = await run_cmd(q, "workflow", f"copilot-workflow {shlex.quote(jira_key)}")
          if rc != 0:
              await q.put(sse("error", {"msg": f"copilot-workflow failed ({rc})"}))
              return

          # 3) Parse MR URL from previous output (optional). If not found, use auto mode.
          #    The frontend doesn’t pass logs here, so we’ll rely on auto mode:
          mr_url = f"auto://{jira_key}"

          # 4) Review (and maybe merge/deploy)
          # If the workflow includes a Deploy node, add --deploy
          has_deploy = any((n.get("type") or "").lower() == "deploy" for n in req.workflow.get("nodes") or [])
          deploy_flag = " --deploy" if has_deploy and not req.dry_run else ""
          rc = await run_cmd(q, "review", f'copilot-ai-review-merge "{mr_url}"{deploy_flag}')
          if rc != 0:
              await q.put(sse("error", {"msg": f"ai-review-merge failed ({rc})"}))
              return

          # 5) QA if present
          has_qa = any((n.get("type") or "").lower() in ("qa",) for n in req.workflow.get("nodes") or [])
          if has_qa and not req.dry_run:
              rc = await run_cmd(q, "qa", f"copilot-qa-ec2 {shlex.quote(jira_key)}")
              if rc != 0:
                  await q.put(sse("error", {"msg": f"qa-ec2 failed ({rc})"}))
                  return

          await q.put(sse("complete", {"job_id": job_id}))
        except Exception as e:
          await q.put(sse("error", {"msg": str(e)}))
        finally:
          await q.put("")  # sentinel
          _jobs[job_id] = None

    asyncio.create_task(worker())
    return {"job_id": job_id}

@router.get("/stream/{job_id}")
async def stream(job_id: str):
    q = _jobs.get(job_id)
    if not isinstance(q, asyncio.Queue):
        raise HTTPException(status_code=404, detail="job not found")

    async def gen():
        while True:
            item = await q.get()
            if item == "":
                break
            yield item

    return StreamingResponse(gen(), media_type="text/event-stream")
