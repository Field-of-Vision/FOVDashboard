#!/usr/bin/env bash
# aws-redeploy.sh - Push code updates to a running FOV Dashboard EC2 instance
#
# Usage:
#   ./aws-redeploy.sh <public-ip>
#   ./aws-redeploy.sh <public-ip> --key path/to/key.pem
#
# What it does:
#   1. Build frontend locally (t3.micro doesn't have enough RAM)
#   2. Rsync code + build to the server (excludes node_modules, .git, .env, certs, *.db, venv)
#   3. Reinstall backend dependencies (if requirements.txt changed)
#   4. Restart services
#   5. Health check

set -euo pipefail

# --- Parse args ---
REMOTE_HOST="${1:?Usage: ./aws-redeploy.sh <ip-or-hostname> [--key path/to/key.pem]}"
shift

SSH_KEY="fov-dashboard-key.pem"
while [[ $# -gt 0 ]]; do
    case $1 in
        --key) SSH_KEY="$2"; shift 2 ;;
        --key=*) SSH_KEY="${1#*=}"; shift ;;
        *) shift ;;
    esac
done

REMOTE_USER="ubuntu"
REMOTE_DIR="/opt/fovdashboard/FOVThingDashboard"
SSH_OPTS="-i $SSH_KEY -o StrictHostKeyChecking=no"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors
GREEN='\033[0;32m'
NC='\033[0m'
echo_step() { echo -e "${GREEN}==>${NC} $1"; }

echo "========================================="
echo "FOV Dashboard - Redeploy"
echo "========================================="
echo "Target: ${REMOTE_USER}@${REMOTE_HOST}"
echo "Key:    ${SSH_KEY}"
echo ""

# --- Step 1: Build frontend locally ---
echo_step "Building frontend locally..."
cd "$SCRIPT_DIR/client"

# Set production env for the target IP
cat > .env.production <<EOF
REACT_APP_WS_BASE=ws://${REMOTE_HOST}
REACT_APP_API_BASE=http://${REMOTE_HOST}
EOF

npm install --legacy-peer-deps --silent 2>&1 | tail -3
npm run build
echo "  Frontend built"
cd "$SCRIPT_DIR"

# --- Step 2: Sync code + build ---
echo_step "Syncing code to server..."
rsync -avz --delete \
    --exclude 'node_modules' \
    --exclude '.git' \
    --exclude '*.db' \
    --exclude 'venv' \
    --exclude 'app/.env' \
    --exclude 'app/certs' \
    --exclude 'client/.env.production' \
    --exclude 'client/node_modules' \
    -e "ssh $SSH_OPTS" \
    "$SCRIPT_DIR/" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

echo "  Code synced (including pre-built frontend)"

# --- Step 3: Update backend + restart on server ---
echo_step "Updating server..."
ssh $SSH_OPTS "${REMOTE_USER}@${REMOTE_HOST}" bash <<REMOTE_EOF
set -euo pipefail

echo "--- Backend dependencies ---"
cd ${REMOTE_DIR}/app
source venv/bin/activate
pip install -q -r requirements.txt
deactivate

echo "--- Fix permissions ---"
sudo chown -R www-data:www-data ${REMOTE_DIR}

echo "--- Restart services ---"
sudo systemctl restart fov-backend fov-frontend

echo "--- Health check ---"
sleep 3
if curl -sf http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo "Backend healthy"
else
    echo "Backend health check failed!"
    sudo journalctl -u fov-backend --no-pager -n 20
fi
REMOTE_EOF

echo ""
echo "========================================="
echo "Redeploy complete!"
echo "========================================="
echo "Dashboard: http://${REMOTE_HOST}"
echo ""
