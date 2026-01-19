#!/usr/bin/env bash
# bootstrap.sh - One-command setup & deploy on a fresh Digital Ocean droplet
#
# Usage:
#   1. Clone repo to droplet: git clone <repo> /opt/fovdashboard
#   2. Copy AWS IoT certs to: /opt/fovdashboard/app/certs/sydney/
#   3. Run: sudo ./bootstrap.sh --domain your-domain.com
#
# This script will:
#   - Install Python, Node, Nginx, Certbot
#   - Create .env files with secure defaults
#   - Install dependencies
#   - Build frontend
#   - Configure Nginx with SSL
#   - Start systemd services

set -euo pipefail

# --- Configuration ---
DOMAIN="${1#--domain=}"
DOMAIN="${DOMAIN:-}"
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$INSTALL_DIR/app"
CLIENT_DIR="$INSTALL_DIR/client"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_step() { echo -e "${GREEN}==>${NC} $1"; }
echo_warn() { echo -e "${YELLOW}WARNING:${NC} $1"; }
echo_error() { echo -e "${RED}ERROR:${NC} $1"; exit 1; }

# --- Parse arguments ---
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain=*) DOMAIN="${1#*=}"; shift ;;
        --domain) DOMAIN="$2"; shift 2 ;;
        --skip-ssl) SKIP_SSL=1; shift ;;
        *) shift ;;
    esac
done

if [[ -z "$DOMAIN" ]]; then
    echo "Usage: sudo ./bootstrap.sh --domain=your-domain.com"
    echo ""
    echo "Options:"
    echo "  --domain=DOMAIN   Your domain name (required)"
    echo "  --skip-ssl        Skip SSL certificate setup"
    exit 1
fi

# --- Check if running as root ---
if [[ $EUID -ne 0 ]]; then
    echo_error "This script must be run as root (use sudo)"
fi

echo "========================================="
echo "FOV Dashboard Bootstrap"
echo "========================================="
echo "Domain: $DOMAIN"
echo "Install directory: $INSTALL_DIR"
echo ""

# --- Step 1: Install system dependencies ---
echo_step "Installing system dependencies..."
apt-get update
apt-get install -y python3 python3-venv python3-pip nodejs npm nginx certbot python3-certbot-nginx curl

# Upgrade npm to latest
npm install -g npm@latest

echo "✓ System dependencies installed"

# --- Step 2: Create backend .env ---
echo_step "Creating backend .env..."
if [[ ! -f "$APP_DIR/.env" ]]; then
    JWT_SECRET=$(openssl rand -hex 32)
    cat > "$APP_DIR/.env" <<EOF
# JWT Configuration (auto-generated - keep secret!)
FOV_JWT_SECRET=$JWT_SECRET

# Relay Monitoring
RELAY_OFFLINE_GRACE_S=90

# AWS IoT Certificates
IOT_CERT_PATH=./certs/sydney/certificate.pem.crt
IOT_PRIVATE_KEY_PATH=./certs/sydney/private.pem.key
IOT_ROOT_CA_PATH=./certs/sydney/AmazonRootCA1.pem
IOT_ENDPOINT=a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com

# Email Alerts (optional)
#SMTP_HOST=smtp.gmail.com
#SMTP_PORT=587
#SMTP_USER=your-email@gmail.com
#SMTP_PASS=your-app-password
#ALERT_EMAIL_FROM=alerts@example.com
#ALERT_EMAIL_TO=admin@example.com
EOF
    echo "✓ Backend .env created"
else
    echo "✓ Backend .env already exists"
fi

# --- Step 3: Validate AWS IoT certificates ---
echo_step "Checking AWS IoT certificates..."
CERT_DIR="$APP_DIR/certs/sydney"
if [[ ! -f "$CERT_DIR/certificate.pem.crt" ]] || \
   [[ ! -f "$CERT_DIR/private.pem.key" ]] || \
   [[ ! -f "$CERT_DIR/AmazonRootCA1.pem" ]]; then
    echo_warn "AWS IoT certificates not found in $CERT_DIR"
    echo "Please copy your certificates to:"
    echo "  - $CERT_DIR/certificate.pem.crt"
    echo "  - $CERT_DIR/private.pem.key"
    echo "  - $CERT_DIR/AmazonRootCA1.pem"
    echo ""
    echo "The backend will start but won't connect to AWS IoT until certificates are added."
else
    echo "✓ AWS IoT certificates found"
fi

# --- Step 4: Create frontend .env.production ---
echo_step "Creating frontend .env.production..."
cat > "$CLIENT_DIR/.env.production" <<EOF
REACT_APP_WS_BASE=wss://$DOMAIN/ws
REACT_APP_API_BASE=https://$DOMAIN
EOF
echo "✓ Frontend .env.production created"

# --- Step 5: Install backend dependencies ---
echo_step "Installing backend dependencies..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
echo "✓ Backend dependencies installed"

# --- Step 6: Install frontend dependencies and build ---
echo_step "Installing frontend dependencies and building..."
cd "$CLIENT_DIR"
npm install
npm run build
echo "✓ Frontend built"

# --- Step 7: Set permissions ---
echo_step "Setting permissions..."
chown -R www-data:www-data "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/scripts/"*.sh
echo "✓ Permissions set"

# --- Step 8: Install systemd services ---
echo_step "Installing systemd services..."

# Backend service
cat > /etc/systemd/system/fov-backend.service <<EOF
[Unit]
Description=FOV Dashboard Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Frontend service
cat > /etc/systemd/system/fov-frontend.service <<EOF
[Unit]
Description=FOV Dashboard Frontend (React)
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$CLIENT_DIR
ExecStart=/usr/bin/npx serve -s build -l 3000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable fov-backend fov-frontend
echo "✓ Systemd services installed"

# --- Step 9: Configure Nginx ---
echo_step "Configuring Nginx..."
cat > /etc/nginx/sites-available/fovdashboard <<EOF
server {
    listen 80;
    server_name $DOMAIN www.$DOMAIN;

    # Redirect to HTTPS (Certbot will modify this)
    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl;
    server_name $DOMAIN www.$DOMAIN;

    # SSL certificates (Certbot will add these)
    # ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    # ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;

    # Frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # WebSocket
    location /ws {
        proxy_pass http://127.0.0.1:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/fovdashboard /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test and reload nginx
nginx -t
systemctl reload nginx
echo "✓ Nginx configured"

# --- Step 10: SSL Certificate ---
if [[ -z "${SKIP_SSL:-}" ]]; then
    echo_step "Setting up SSL certificate with Let's Encrypt..."
    certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos --email "admin@$DOMAIN" || {
        echo_warn "SSL setup failed. You can run manually later:"
        echo "  sudo certbot --nginx -d $DOMAIN"
    }
else
    echo_warn "Skipping SSL setup (--skip-ssl flag)"
fi

# --- Step 11: Start services ---
echo_step "Starting services..."
systemctl start fov-backend
systemctl start fov-frontend
echo "✓ Services started"

# --- Step 12: Health check ---
echo_step "Running health check..."
sleep 3

if curl -sf http://127.0.0.1:8000/api/health > /dev/null 2>&1; then
    echo "✓ Backend healthy"
else
    echo_warn "Backend health check failed - check logs with: journalctl -u fov-backend"
fi

# --- Done! ---
echo ""
echo "========================================="
echo "Bootstrap Complete!"
echo "========================================="
echo ""
echo "Dashboard URL: https://$DOMAIN"
echo ""
echo "Login credentials:"
echo "  • admin / admin123 (all stadiums)"
echo "  • aviva / temp123 (Aviva only)"
echo "  • marvel / temp456 (Marvel only)"
echo "  • kia / temp789 (Kia only)"
echo ""
echo "Useful commands:"
echo "  Check status:    sudo systemctl status fov-backend fov-frontend"
echo "  View logs:       sudo journalctl -u fov-backend -f"
echo "  Restart:         sudo systemctl restart fov-backend fov-frontend"
echo ""
