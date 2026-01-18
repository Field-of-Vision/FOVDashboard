#!/usr/bin/env bash
set -euo pipefail

# --- inputs ---
SERVERS=(${SERVERS:-root@209.97.185.144})   # space-separated; add Sydney if you use it
REMOTE_DIR="${REMOTE_DIR:-/opt/FOVdashboard/FOVThingDashboard - Copy}"
BACKEND_IMAGE="${BACKEND_IMAGE:-docker.io/YOUR_DOCKER_USERNAME/fov-backend}" #insert own credenials
FRONTEND_IMAGE="${FRONTEND_IMAGE:-docker.io/YOUR_DOCKER_USERNAME/fov-frontend}" #insert own credentials
VERSION="${VERSION:-$(cat .deploy_version)}"
HEALTH_PATH="${HEALTH_PATH:-/api/health}"
HEALTH_WAIT="${HEALTH_WAIT:-60}" # seconds

if [[ -z "${VERSION:-}" ]]; then
  echo "No VERSION found (set VERSION=... or run build_and_push.sh first)"; exit 1
fi

for HOST in "${SERVERS[@]}"; do
  echo "=== Deploying $VERSION to $HOST ==="

  # Update remote .env.deploy with images + version
  ssh -o StrictHostKeyChecking=no "$HOST" "bash -lc '
    set -e
    mkdir -p $REMOTE_DIR
    cd $REMOTE_DIR
    # keep a backup of previous env
    if [ -f .env.deploy ]; then cp .env.deploy .env.deploy.bak || true; fi
    cat > .env.deploy <<ENV
BACKEND_IMAGE=$BACKEND_IMAGE
FRONTEND_IMAGE=$FRONTEND_IMAGE
VERSION=$VERSION
ENV
    echo \"Remote .env.deploy set to VERSION=$VERSION\"
  '"

  # Pull + restart
  ssh -o StrictHostKeyChecking=no "$HOST" "bash -lc '
    set -e
    cd $REMOTE_DIR
    docker compose --env-file .env.deploy pull
    docker compose --env-file .env.deploy up -d --remove-orphans
  '"

  # Health check (backend)
  echo "Waiting for health @ $HOST ..."
  if ! ssh -o StrictHostKeyChecking=no "$HOST" "bash -lc '
      for i in \$(seq 1 $HEALTH_WAIT); do
        if curl -fsS http://127.0.0.1:8000$HEALTH_PATH >/dev/null; then exit 0; fi
        sleep 1
      done
      exit 1
    '"
  then
    echo "Health check FAILED on $HOST"
    exit 1
  fi

  echo "OK on $HOST"
done

echo "=== Deploy complete: $VERSION ==="
