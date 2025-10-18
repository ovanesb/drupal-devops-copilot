#!/usr/bin/env bash
set -euo pipefail
set -o pipefail

# ------------ Config (override via env) ------------
EC2_HOST="${EC2_HOST:-13.222.166.203}"
EC2_USER="${EC2_USER:-ubuntu}"
EC2_KEY="${EC2_KEY:-$HOME/aws/Drupal-demo-site.pem}"

# Branch to deploy
DEPLOY_BRANCH="${DEPLOY_BRANCH:-staging}"

# Paths on EC2
EC2_APP_PATH="${EC2_APP_PATH:-/srv/drupal/app}"   # git repo root (composer.json here)
EC2_STACK_DIR="${EC2_STACK_DIR:-/srv/drupal}"     # docker-compose.yml lives here

# Drush URI (defaults to container-local)
DRUSH_URI="${DRUSH_URI:-http://localhost}"

# (Optional) force the git 'origin' URL on EC2 (useful when SSH URLs differ)
DEPLOY_GIT_REMOTE_URL="${DEPLOY_GIT_REMOTE_URL:-}"

# (Optional) exact commit to deploy; if set, script will wait until origin/<branch> equals this SHA
EXPECT_SHA="${EXPECT_SHA:-}"
EXPECT_TIMEOUT="${EXPECT_TIMEOUT:-180}"
EXPECT_INTERVAL="${EXPECT_INTERVAL:-5}"

SSH="ssh -i ${EC2_KEY} -o StrictHostKeyChecking=no ${EC2_USER}@${EC2_HOST}"

echo "==> Deploying branch '${DEPLOY_BRANCH}' to ${EC2_USER}@${EC2_HOST}"
echo "==> EC2_STACK_DIR=${EC2_STACK_DIR}  EC2_APP_PATH=${EC2_APP_PATH}"

${SSH} \
  DEPLOY_BRANCH="${DEPLOY_BRANCH}" \
  EC2_APP_PATH="${EC2_APP_PATH}" \
  EC2_STACK_DIR="${EC2_STACK_DIR}" \
  DRUSH_URI="${DRUSH_URI}" \
  DEPLOY_GIT_REMOTE_URL="${DEPLOY_GIT_REMOTE_URL}" \
  EXPECT_SHA="${EXPECT_SHA}" \
  EXPECT_TIMEOUT="${EXPECT_TIMEOUT}" \
  EXPECT_INTERVAL="${EXPECT_INTERVAL}" \
  bash -s <<'__DEPLOY_EOF__' 2>&1 | sed -e 's/^/[EC2] /'

set -Eeuo pipefail
trap 'ec=$?; echo "!! ERROR on line $LINENO (exit $ec)"; exit $ec' ERR

step() { printf '\n=== STEP %s === %s\n\n' "$1" "$2"; }

: "${DEPLOY_BRANCH:?DEPLOY_BRANCH required}"
: "${EC2_APP_PATH:?EC2_APP_PATH required}"
: "${EC2_STACK_DIR:?EC2_STACK_DIR required}"
DRUSH_URI="${DRUSH_URI:-http://localhost}"

step 1 "Check docker compose in ${EC2_STACK_DIR}"
cd "${EC2_STACK_DIR}"
docker compose ps >/dev/null 2>&1 || { echo "docker compose not available"; exit 2; }

step 2 "Ensure stack is up"
docker compose up -d
docker compose ps

step 3 "Git checkout & fast-forward '${DEPLOY_BRANCH}' in ${EC2_APP_PATH}"
if [ -d "${EC2_APP_PATH}/.git" ]; then
  cd "${EC2_APP_PATH}"

  echo "-- current remotes:"
  git remote -v || true

  if [ -n "${DEPLOY_GIT_REMOTE_URL:-}" ]; then
    git remote set-url origin "${DEPLOY_GIT_REMOTE_URL}"
    echo "-- set origin -> ${DEPLOY_GIT_REMOTE_URL}"
  fi

  git reset --hard
  git clean -fd
  git fetch --prune origin

  # If EXPECT_SHA specified, we will wait until origin/<branch> equals that SHA
  if [ -n "${EXPECT_SHA:-}" ]; then
    echo "-- expecting remote ${DEPLOY_BRANCH} to be ${EXPECT_SHA}"
    end=$((SECONDS + ${EXPECT_TIMEOUT:-180}))
    while true; do
      git fetch --prune origin >/dev/null 2>&1 || true
      CUR_SHA="$(git rev-parse "origin/${DEPLOY_BRANCH}" || true)"
      echo "[wait] origin/${DEPLOY_BRANCH} = ${CUR_SHA}"
      if [ -n "${CUR_SHA}" ] && [ "${CUR_SHA}" = "${EXPECT_SHA}" ]; then
        echo "[wait] match achieved."
        break
      fi
      if [ ${SECONDS} -ge ${end} ]; then
        echo "!! timed out waiting for origin/${DEPLOY_BRANCH} to reach ${EXPECT_SHA}"
        break
      fi
      sleep "${EXPECT_INTERVAL:-5}"
    done
    # checkout the exact expected SHA if available; else branch
    if git cat-file -e "${EXPECT_SHA}^{commit}" 2>/dev/null; then
      git checkout -B "${DEPLOY_BRANCH}" "${EXPECT_SHA}" || true
    else
      git checkout -B "${DEPLOY_BRANCH}" "origin/${DEPLOY_BRANCH}"
    fi
  else
    # normal fast-forward to remote branch
    git checkout -B "${DEPLOY_BRANCH}" "origin/${DEPLOY_BRANCH}"
  fi

  LOCAL_SHA="$(git rev-parse HEAD)"
  REMOTE_SHA="$(git rev-parse "origin/${DEPLOY_BRANCH}")"
  echo "LOCAL  HEAD: ${LOCAL_SHA}"
  echo "REMOTE HEAD: ${REMOTE_SHA}"
else
  echo "ERROR: ${EC2_APP_PATH} is not a git repository."
  exit 3
fi

step 4 "Composer install in container"
time docker compose exec -T -w /var/www/html php \
  composer install --no-interaction --no-progress --prefer-dist </dev/null

step 5 "Restart containers (safe)"
docker compose up -d
docker compose ps

dr() {
  docker compose exec -T -w /var/www/html php \
    ./vendor/bin/drush --uri="${DRUSH_URI}" "$@" </dev/null
}

step 6 "Drush maintenance mode ON + cache rebuild"
echo "[MARK] pre-maint-on"
dr sset system.maintenance_mode 1 || true
dr cr || true
echo "[MARK] post-maint-on"

step 7 "Run database updates"
echo "[MARK] pre-updb"
dr updb -y
echo "[MARK] post-updb"

step 8 "Cache rebuild"
echo "[MARK] pre-cr-1"
dr cr
echo "[MARK] post-cr-1"

step 9 "Import configuration"
echo "[MARK] pre-cim"
dr cim -y || echo "[notice] cim returned non-zero (no changes?)"
echo "[MARK] post-cim"

step 10 "Run deploy hooks (if any)"
echo "[MARK] pre-deploy-hook"
if dr help deploy:hook >/dev/null 2>&1; then
  dr deploy:hook -y || true
else
  echo "(no deploy:hook command available — skipping)"
fi
echo "[MARK] post-deploy-hook"

step 11 "Final cache rebuild and maintenance mode OFF"
echo "[MARK] pre-final"
dr cr
dr sset system.maintenance_mode 0 || true
dr cr
echo "[MARK] post-final"

echo "== SHA deployed: $(git rev-parse HEAD) =="

step 12 "Deploy done"
__DEPLOY_EOF__

rc=${PIPESTATUS[0]}
if [[ $rc -ne 0 ]]; then
  echo "==> Remote deploy failed (ssh exit $rc)"; exit $rc
fi
echo "==> Deploy completed successfully."
