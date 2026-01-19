#!/usr/bin/env bash
# One-command production deployment

set -euo pipefail

# Load configuration
if [ -f "deploy.config.local" ]; then
    source deploy.config.local
else
    echo "ERROR: deploy.config.local not found"
    echo "Copy deploy.config.example to deploy.config.local and customize"
    exit 1
fi

echo "=== FOV Dashboard Deployment ==="
echo "Target: $DEPLOY_SERVER"
echo "Domain: $DEPLOY_DOMAIN"
echo

# Step 1: Build frontend locally
echo "Building frontend..."
cd client
npm run build
cd ..
echo "✓ Frontend built"

# Step 2: Sync files to server
echo
echo "Syncing files to server..."
rsync -avz --delete \
    --exclude 'node_modules' \
    --exclude '.git' \
    --exclude '*.db' \
    --exclude 'venv' \
    --exclude '.env.local' \
    . "$DEPLOY_SERVER:$DEPLOY_DIR/"
echo "✓ Files synced"

# Step 3: Install and start on server
echo
echo "Setting up on server..."
ssh "$DEPLOY_SERVER" "bash -s" <<EOF
set -euo pipefail
cd $DEPLOY_DIR

# Backend setup
cd app
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Frontend setup
cd ../client
npm install --production

# Install systemd services
cd ..
sudo ./scripts/install_services.sh

# Restart services
echo "Restarting services..."
sudo systemctl restart fov-backend
sudo systemctl restart fov-frontend

echo "✓ Services restarted"
EOF

# Step 4: Health check
echo
echo "Waiting for backend to start..."
sleep 5

if curl -sf "http://$DEPLOY_SERVER:$BACKEND_PORT/api/health" > /dev/null; then
    echo "✓ Backend healthy"
else
    echo "❌ Backend health check failed"
    echo "Check logs: ssh $DEPLOY_SERVER 'sudo journalctl -u fov-backend -n 50'"
    exit 1
fi

echo
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo
echo "Access dashboard at: https://$DEPLOY_DOMAIN"
echo
echo "To check logs:"
echo "  ssh $DEPLOY_SERVER 'sudo journalctl -u fov-backend -f'"
echo "  ssh $DEPLOY_SERVER 'sudo journalctl -u fov-frontend -f'"
echo
