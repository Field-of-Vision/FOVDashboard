#!/usr/bin/env bash
# scripts/setup.sh - Interactive deployment setup wizard

set -euo pipefail

echo "=== FOV Dashboard Setup Wizard ==="
echo

# Step 1: Check prerequisites
echo "Checking prerequisites..."
command -v python3 >/dev/null || { echo "ERROR: Python 3.12+ required"; exit 1; }
command -v node >/dev/null || { echo "ERROR: Node.js 18+ required"; exit 1; }
command -v git >/dev/null || { echo "ERROR: Git required"; exit 1; }
echo "✓ Prerequisites found"
echo

# Step 2: Backend .env setup
if [ ! -f "app/.env" ]; then
    echo "Creating backend .env file..."

    read -p "Enter JWT secret (press Enter for auto-generated): " jwt_secret
    if [ -z "$jwt_secret" ]; then
        # Generate random 32-character hex string
        jwt_secret=$(openssl rand -hex 32 2>/dev/null || cat /dev/urandom | tr -dc 'a-f0-9' | head -c 64)
    fi

    read -p "Enter relay offline grace period in seconds [90]: " grace
    grace=${grace:-90}

    cat > app/.env <<EOF
# JWT Configuration (CRITICAL - keep secret!)
FOV_JWT_SECRET=$jwt_secret

# Relay Monitoring
RELAY_OFFLINE_GRACE_S=$grace

# AWS IoT Certificates (paths relative to app/)
IOT_CERT_PATH=./certs/sydney/certificate.pem.crt
IOT_PRIVATE_KEY_PATH=./certs/sydney/private.pem.key
IOT_ROOT_CA_PATH=./certs/sydney/AmazonRootCA1.pem
IOT_ENDPOINT=a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com

# Email Alerts (optional - leave commented to disable)
#SMTP_HOST=smtp.gmail.com
#SMTP_PORT=587
#SMTP_USER=your-email@gmail.com
#SMTP_PASS=your-16-char-app-password
#ALERT_EMAIL_FROM=alerts@example.com
#ALERT_EMAIL_TO=admin@example.com
EOF
    echo "✓ Backend .env created at app/.env"
    echo
else
    echo "✓ Backend .env already exists"
    echo
fi

# Step 3: AWS IoT Certificate Setup
echo "AWS IoT Certificate Setup:"
echo "You need three files from AWS IoT Console:"
echo "  1. Certificate file (.pem.crt)"
echo "  2. Private key file (.pem.key)"
echo "  3. Amazon Root CA 1 (download from AWS)"
echo

if [ ! -d "app/certs/sydney" ]; then
    mkdir -p app/certs/sydney
    echo "Created app/certs/sydney directory"
fi

echo "Place your AWS IoT certificates in: app/certs/sydney/"
echo "  - certificate.pem.crt"
echo "  - private.pem.key"
echo "  - AmazonRootCA1.pem"
echo

# Wait for user to place certificates
read -p "Press Enter once certificates are in place..."

# Validate certificates exist
if [ ! -f "app/certs/sydney/certificate.pem.crt" ]; then
    echo "❌ ERROR: certificate.pem.crt not found"
    echo "   Expected location: app/certs/sydney/certificate.pem.crt"
    exit 1
fi
if [ ! -f "app/certs/sydney/private.pem.key" ]; then
    echo "❌ ERROR: private.pem.key not found"
    echo "   Expected location: app/certs/sydney/private.pem.key"
    exit 1
fi
if [ ! -f "app/certs/sydney/AmazonRootCA1.pem" ]; then
    echo "❌ ERROR: AmazonRootCA1.pem not found"
    echo "   Expected location: app/certs/sydney/AmazonRootCA1.pem"
    exit 1
fi

echo "✓ All AWS IoT certificates found"
echo

# Step 4: Frontend .env setup
if [ ! -f "client/.env.development" ]; then
    echo "Creating frontend .env.development (for local testing)..."
    cat > client/.env.development <<EOF
# Local development endpoints
REACT_APP_WS_BASE=ws://localhost:8000/ws
REACT_APP_API_BASE=http://localhost:8000
EOF
    echo "✓ Frontend .env.development created"
fi

# Production .env (for deployment)
read -p "Enter production domain (e.g., fovdashboard.com) or leave blank for later: " domain
if [ -n "$domain" ]; then
    cat > client/.env.production <<EOF
# Production endpoints
REACT_APP_WS_BASE=wss://$domain/ws
REACT_APP_API_BASE=https://$domain
EOF
    echo "✓ Frontend .env.production created"
fi
echo

# Step 5: Install dependencies
read -p "Install dependencies now? (y/n): " install
if [ "$install" = "y" ] || [ "$install" = "Y" ]; then
    echo
    echo "Installing backend dependencies..."
    cd app

    # Create venv if not exists
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi

    # Activate and install
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    cd ..

    echo "Installing frontend dependencies..."
    cd client
    npm install
    cd ..

    echo "✓ Dependencies installed"
    echo
fi

# Step 6: Summary
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo
echo "To start the application locally:"
echo
echo "  Terminal 1 (Backend):"
echo "    cd FOVThingDashboard/app"
echo "    source venv/bin/activate"
echo "    python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo
echo "  Terminal 2 (Frontend):"
echo "    cd FOVThingDashboard/client"
echo "    npm start"
echo
echo "Login credentials:"
echo "  • admin / admin123 (all stadiums)"
echo "  • aviva / temp123 (Aviva only)"
echo "  • marvel / temp456 (Marvel only)"
echo "  • kia / temp789 (Kia only)"
echo
echo "For production deployment, run: ./scripts/deploy.sh"
echo
