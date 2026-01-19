#!/usr/bin/env bash
# Install systemd services

set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Must run as root (use sudo)"
    exit 1
fi

echo "Installing systemd services..."

# Copy service files
cp deployment/fov-backend.service /etc/systemd/system/
cp deployment/fov-frontend.service /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable services (start on boot)
systemctl enable fov-backend
systemctl enable fov-frontend

echo "✓ Services installed"
echo
echo "To start services:"
echo "  sudo systemctl start fov-backend"
echo "  sudo systemctl start fov-frontend"
echo
echo "To check status:"
echo "  sudo systemctl status fov-backend"
echo "  sudo systemctl status fov-frontend"
echo
echo "To view logs:"
echo "  sudo journalctl -u fov-backend -f"
echo "  sudo journalctl -u fov-frontend -f"
