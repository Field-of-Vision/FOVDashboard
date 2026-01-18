#!/usr/bin/env bash
set -euo pipefail

DOMAIN="aviva.fovdashboard.com"
EMAIL="timf34@gmail.com"
NGINX_SITE="/etc/nginx/sites-available/fovdashboard"

# 1) Make sure the include files exist
apt update
apt install -y certbot python3-certbot-nginx ufw

# 2) Drop the nginx config (now that /etc/letsencrypt/options-ssl-nginx.conf is there)
cat > "$NGINX_SITE" <<'EOF'
server {
    listen 80;
    server_name '"$DOMAIN"';
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name '"$DOMAIN"';

    ssl_certificate     /etc/letsencrypt/live/'"$DOMAIN"'/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/'"$DOMAIN"'/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://localhost:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade           $http_upgrade;
        proxy_set_header Connection        "upgrade";
        proxy_set_header Host              $host;
        proxy_read_timeout   3600s;
        proxy_send_timeout   3600s;
        proxy_buffering      off;
    }
}
EOF

ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 3) Obtain the cert and wire it into nginx
certbot --nginx \
  --redirect \
  --non-interactive \
  --agree-tos \
  -m "$EMAIL" \
  -d "$DOMAIN"

# 4) Firewall
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable