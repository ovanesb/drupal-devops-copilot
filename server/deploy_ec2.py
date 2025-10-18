# server/deploy_ec2.py
import os, asyncio, asyncssh, shlex
from typing import Iterable, List, Tuple

HOST = os.getenv("DEPLOY_HOST")
USER = os.getenv("DEPLOY_USER", "ubuntu")
KEY  = os.getenv("DEPLOY_SSH_KEY")
WORK = os.getenv("DEPLOY_WORKDIR", "/srv/drupal")

ALLOWED_DIR = "modules/custom"
ALLOWED_EXT = (".php", ".module", ".info.yml", ".yml", ".twig", ".json", ".md", ".libraries.yml")

def _filter_paths(paths: Iterable[str]) -> List[str]:
    out = []
    for p in paths:
        if p.startswith(ALLOWED_DIR + "/") and p.endswith(ALLOWED_EXT):
            out.append(p)
    return sorted(set(out))

async def _ssh(cmd: str) -> Tuple[int, List[str]]:
    lines: List[str] = []
    async with asyncssh.connect(HOST, username=USER, client_keys=[KEY], known_hosts=None) as conn:
        proc = await conn.create_process(cmd)
        async for line in proc.stdout: lines.append(line.rstrip("\n"))
        async for line in proc.stderr: lines.append(line.rstrip("\n"))
        rc = await proc.wait()
        return rc, lines

async def sync_changed_files(repo_root: str, changed: List[str]) -> Tuple[bool, List[str]]:
    """
    rsync allowed changed files to EC2:/srv/drupal/app/
    """
    files = _filter_paths(changed)
    if not files:
        return True, ["[deploy] No allowed changed files to sync (skipping rsync)."]

    # Build include file list for rsync
    include_list = "\n".join(files) + "\n"
    include_path = os.path.join(repo_root, ".copilot_rsync_include.txt")
    with open(include_path, "w") as f:
        f.write(include_list)

    # rsync: only include our files, plus parent dirs; everything else exclude
    rsync_cmd = (
        f'rsync -avz --delete-after '
        f'--files-from={shlex.quote(include_path)} '
        f'-e "ssh -i {shlex.quote(KEY)} -o StrictHostKeyChecking=no" '
        f'{shlex.quote(repo_root)}/ '
        f'{USER}@{HOST}:{WORK}/app/'
    )
    # run locally
    proc = await asyncio.create_subprocess_shell(rsync_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, text=True)
    out = []
    async for line in proc.stdout: out.append(line.rstrip("\n"))
    rc = await proc.wait()
    try: os.remove(include_path)
    except: pass
    return rc == 0, ["[deploy] rsync"] + out

async def drush_pipeline(needs_composer: bool = False) -> Tuple[bool, List[str]]:
    cmds = [
        f"cd {WORK}",
        "docker compose up -d",
        "sleep 5",
    ]
    if needs_composer:
        cmds += [
            "docker compose exec -T php composer install --no-interaction --prefer-dist -d /var/www/html",
        ]
    cmds += [
        "docker compose exec -T php ./vendor/bin/drush cim -y",
        "docker compose exec -T php ./vendor/bin/drush updb -y",
        "docker compose exec -T php ./vendor/bin/drush cr",
        "docker compose exec -T php ./vendor/bin/drush status --fields=bootstrap"
    ]
    return await _ssh(" && ".join(cmds))
