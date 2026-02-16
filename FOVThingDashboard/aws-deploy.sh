#!/usr/bin/env bash
# aws-deploy.sh - Launch FOV Dashboard on a fresh EC2 instance
#
# Prerequisites:
#   - AWS CLI configured with credentials (aws configure)
#   - Default region set to ap-southeast-2 (or pass --region)
#
# Usage:
#   ./aws-deploy.sh
#
# What it does:
#   1. Creates security group (SSH + HTTP + HTTPS)
#   2. Creates a new key pair (saves .pem locally)
#   3. Launches t3.micro Ubuntu 22.04 instance with user-data bootstrap
#   4. Waits for instance to be running
#   5. Prints public IP, SSH command, and next steps
#
# After launch, you must SCP the AWS IoT certificates to the instance.

set -euo pipefail

# --- Configuration ---
REGION="${AWS_DEFAULT_REGION:-ap-southeast-2}"
INSTANCE_TYPE="t3.micro"
KEY_NAME="fov-dashboard-key"
SG_NAME="fov-dashboard-sg"
REPO_URL="https://github.com/Field-of-Vision/FOVDashboard.git"

# Ubuntu 22.04 LTS AMI (ap-southeast-2) - looked up via aws ec2 describe-images
AMI="ami-0c73bd9145b5546f5"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_step() { echo -e "${GREEN}==>${NC} $1"; }
echo_warn() { echo -e "${YELLOW}NOTE:${NC} $1"; }
echo_error() { echo -e "${RED}ERROR:${NC} $1"; exit 1; }

echo "========================================="
echo "FOV Dashboard - AWS EC2 Deploy"
echo "========================================="
echo "Region: $REGION"
echo "Instance: $INSTANCE_TYPE"
echo "AMI: $AMI (Ubuntu 22.04)"
echo ""

# --- Step 1: Security Group ---
echo_step "Setting up security group..."

SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SG_NAME" \
    --query 'SecurityGroups[0].GroupId' \
    --output text \
    --region "$REGION" 2>/dev/null || echo "None")

if [[ "$SG_ID" == "None" || -z "$SG_ID" ]]; then
    SG_ID=$(aws ec2 create-security-group \
        --group-name "$SG_NAME" \
        --description "FOV Dashboard - SSH, HTTP, HTTPS" \
        --region "$REGION" \
        --query 'GroupId' --output text)
    echo "  Created security group: $SG_ID"

    # Allow SSH, HTTP, HTTPS
    aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --region "$REGION" \
        --protocol tcp --port 22 --cidr 0.0.0.0/0 2>/dev/null || true
    aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --region "$REGION" \
        --protocol tcp --port 80 --cidr 0.0.0.0/0 2>/dev/null || true
    aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --region "$REGION" \
        --protocol tcp --port 443 --cidr 0.0.0.0/0 2>/dev/null || true
    echo "  Ingress rules: SSH(22), HTTP(80), HTTPS(443)"
else
    echo "  Using existing security group: $SG_ID"
fi

# --- Step 2: Key Pair ---
echo_step "Setting up key pair..."

KEY_EXISTS=$(aws ec2 describe-key-pairs \
    --key-names "$KEY_NAME" \
    --region "$REGION" \
    --query 'KeyPairs[0].KeyName' \
    --output text 2>/dev/null || echo "None")

if [[ "$KEY_EXISTS" == "None" ]]; then
    aws ec2 create-key-pair \
        --key-name "$KEY_NAME" \
        --region "$REGION" \
        --query 'KeyMaterial' \
        --output text > "${KEY_NAME}.pem"
    chmod 400 "${KEY_NAME}.pem"
    echo "  Created key pair: $KEY_NAME"
    echo "  Private key saved to: $(pwd)/${KEY_NAME}.pem"
else
    echo "  Using existing key pair: $KEY_NAME"
    if [[ ! -f "${KEY_NAME}.pem" ]]; then
        echo_warn "Key pair exists in AWS but .pem file not found locally."
        echo "  If you lost the .pem file, delete the key pair and re-run:"
        echo "    aws ec2 delete-key-pair --key-name $KEY_NAME --region $REGION"
    fi
fi

# --- Step 3: User Data Script ---
echo_step "Preparing user-data bootstrap..."

# The user-data script runs as root on first boot
USER_DATA=$(cat <<'USERDATA_END'
#!/bin/bash
set -euxo pipefail
exec > /var/log/fov-bootstrap.log 2>&1

export DEBIAN_FRONTEND=noninteractive

echo "=== FOV Dashboard EC2 Bootstrap ==="
echo "Started at: $(date)"

# Install git
apt-get update
apt-get install -y git

# Clone the repo
git clone REPO_URL_PLACEHOLDER /opt/fovdashboard

# Run the bootstrap script in IP-only mode
cd /opt/fovdashboard/FOVThingDashboard
chmod +x bootstrap.sh
./bootstrap.sh --ip-only

echo "=== Bootstrap complete at: $(date) ==="
echo "NOTE: AWS IoT certificates still need to be copied to /opt/fovdashboard/FOVThingDashboard/app/certs/sydney/"
USERDATA_END
)

# Replace repo URL placeholder
USER_DATA="${USER_DATA//REPO_URL_PLACEHOLDER/$REPO_URL}"

# --- Step 4: Launch Instance ---
echo_step "Launching EC2 instance..."

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id "$AMI" \
    --instance-type "$INSTANCE_TYPE" \
    --key-name "$KEY_NAME" \
    --security-group-ids "$SG_ID" \
    --user-data "$USER_DATA" \
    --region "$REGION" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=fov-dashboard}]" \
    --query 'Instances[0].InstanceId' \
    --output text)

echo "  Instance ID: $INSTANCE_ID"

# --- Step 5: Wait for Running ---
echo_step "Waiting for instance to be running..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"

PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --region "$REGION" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "  Public IP: $PUBLIC_IP"

# --- Done! ---
echo ""
echo "========================================="
echo "EC2 Instance Launched!"
echo "========================================="
echo ""
echo "Instance ID:  $INSTANCE_ID"
echo "Public IP:    $PUBLIC_IP"
echo "Region:       $REGION"
echo ""
echo "SSH access:"
echo "  ssh -i ${KEY_NAME}.pem ubuntu@${PUBLIC_IP}"
echo ""
echo "Bootstrap is running in the background (takes ~5 minutes)."
echo "Check progress with:"
echo "  ssh -i ${KEY_NAME}.pem ubuntu@${PUBLIC_IP} 'tail -f /var/log/fov-bootstrap.log'"
echo ""
echo "========================================="
echo "NEXT STEPS (after bootstrap completes):"
echo "========================================="
echo ""
echo "1. Copy AWS IoT certificates to the instance:"
echo "   scp -i ${KEY_NAME}.pem -r app/certs/sydney/ ubuntu@${PUBLIC_IP}:/tmp/certs/"
echo "   ssh -i ${KEY_NAME}.pem ubuntu@${PUBLIC_IP} 'sudo mkdir -p /opt/fovdashboard/FOVThingDashboard/app/certs/sydney && sudo cp /tmp/certs/* /opt/fovdashboard/FOVThingDashboard/app/certs/sydney/ && sudo chown -R www-data:www-data /opt/fovdashboard/FOVThingDashboard/app/certs'"
echo ""
echo "2. Restart the backend to connect to AWS IoT:"
echo "   ssh -i ${KEY_NAME}.pem ubuntu@${PUBLIC_IP} 'sudo systemctl restart fov-backend'"
echo ""
echo "3. Open in browser:"
echo "   http://${PUBLIC_IP}"
echo ""
echo "4. Verify with simulator (from your local machine):"
echo "   cd app && python iot_device_simulator.py --stadium marvel"
echo ""
