#!/usr/bin/env bash
set -euo pipefail

DOMAIN="aviva.fovdashboard.com"
EMAIL="timf34@gmail.com"
SITE="/etc/nginx/sites-available/bootstrap-fov"

apt update
apt install -y nginx certbot python3-certbot-nginx ufw

# --- plain-HTTP v-host -------------------------------------------------
cat > "$SITE" <<EOF
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};

    location /      { proxy_pass http://localhost:3000;  proxy_set_header Host \$host; }
    location /api/  { proxy_pass http://localhost:8000;  proxy_set_header Host \$host; }
    location /ws    {
        proxy_pass http://localhost:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
    }
}
EOF

ln -sf "$SITE" /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# --- obtain cert & let the plugin upgrade the v-host to HTTPS ---------
certbot --nginx \
        --redirect \
        --non-interactive \
        --agree-tos \
        -m "$EMAIL" \
        -d "$DOMAIN" -d "www.${DOMAIN}"

# --- minimal firewall -------------------------------------------------
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
