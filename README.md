# FOV Dashboard

Real-time IoT device monitoring dashboard for multiple stadium locations. Built with FastAPI (backend) and React (frontend), connected to AWS IoT Core via MQTT.

## Quick Start

### Prerequisites
- **Python 3.12+**
- **Node.js 18+**
- AWS IoT certificates (provided separately)

### 1. Backend Setup

```bash
cd FOVThingDashboard/app

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs at: `http://localhost:8000`

### 2. Frontend Setup

```bash
cd FOVThingDashboard/client

# Install dependencies
npm install

# Run development server
npm start
```

Frontend runs at: `http://localhost:3000`

## Login Credentials

| Username | Password | Access |
|----------|----------|--------|
| `admin` | `admin123` | All stadiums |
| `aviva` | `temp123` | Aviva Stadium only |
| `marvel` | `temp456` | Marvel Stadium only |
| `kia` | `temp789` | Kia Arena only |

## Configuration

### Adding a New Stadium

1. **Edit `FOVThingDashboard/app/stadiums_config.py`:**

```python
STADIUMS = {
    # ... existing stadiums ...
    "new_stadium": {
        "name": "New Stadium Name",
        "password": "your_password",
        "region": "ap-southeast-2",  # AWS region
        "iot_endpoint": "xxxxx-ats.iot.ap-southeast-2.amazonaws.com",
    },
}
```

2. **Restart backend** - The new stadium appears automatically in the login dropdown.

### Environment Variables

Key variables in `FOVThingDashboard/app/.env`:

```bash
# JWT Secret (change in production!)
FOV_JWT_SECRET=dev-change-me

# Relay monitoring
RELAY_OFFLINE_GRACE_S=90

# AWS IoT certificates (paths relative to app/)
IOT_CERT_PATH=./aws-iot-certs/...
IOT_PRIVATE_KEY_PATH=./aws-iot-certs/...
IOT_ROOT_CA_PATH=./aws-iot-certs/...

# Email alerts (optional)
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your-email@gmail.com
# SMTP_PASS=your-16-char-app-password
# ALERT_EMAIL_FROM=alerts@example.com
# ALERT_EMAIL_TO=admin@example.com
```

## Architecture

### Multi-Stadium Support

Each stadium has its own AWS region and IoT endpoint. Devices publish to topics:

```
{region}/{stadium}/{device_id}/{metric}
```

**Examples:**
- `eu-west-1/aviva/device001/battery`
- `ap-southeast-2/marvel/device002/temperature`
- `ap-southeast-2/kia/device003/version`

The backend automatically subscribes to all configured stadiums.

### Authentication

- **JWT tokens** (12-hour expiration)
- **Stadium users** see only their devices
- **Admin** sees all devices from all stadiums
- Tokens stored in browser localStorage (persists across sessions)

## Project Structure

```
FOVThingDashboard/
├── app/                    # FastAPI backend
│   ├── main.py            # Main application
│   ├── auth.py            # JWT authentication
│   ├── stadiums_config.py # Stadium definitions
│   ├── device.py          # Device management
│   ├── database.py        # SQLite database
│   └── aws_iot/           # AWS IoT MQTT client
├── client/                # React frontend
│   └── src/
│       ├── App.tsx        # Main app + logout
│       ├── components/
│       │   ├── LoginForm.tsx
│       │   └── Dashboard.tsx
│       └── services/
│           └── api.ts     # Backend API calls
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login (returns JWT)
- `GET /api/meta/stadiums` - List available stadiums

### Devices
- `GET /api/devices` - List devices (filtered by role)
- `GET /api/devices/{device_id}` - Get device details
- `POST /api/devices/{device_id}/ota` - Trigger OTA update

### WebSocket
- `WS /ws` - Real-time device updates

## Deployment (Digital Ocean)

### One-Command Deploy

On a fresh Ubuntu droplet:

```bash
# 1. Clone the repo
git clone <your-repo-url> /opt/fovdashboard
cd /opt/fovdashboard/FOVThingDashboard

# 2. Copy your AWS IoT certificates to:
#    app/certs/sydney/certificate.pem.crt
#    app/certs/sydney/private.pem.key
#    app/certs/sydney/AmazonRootCA1.pem

# 3. Run bootstrap (installs everything, configures Nginx + SSL)
sudo ./bootstrap.sh --domain=your-domain.com
```

That's it! The script will:
- Install Python, Node, Nginx, Certbot
- Create .env files with secure defaults
- Build the frontend
- Configure Nginx with SSL (Let's Encrypt)
- Start systemd services

### Manual Deployment

If you prefer manual control:
1. Change `FOV_JWT_SECRET` to a secure random value
2. Update `client/.env.production` with your domain
3. Configure Nginx reverse proxy
4. Use SSL certificates (Let's Encrypt)
5. Set up monitoring for `/api/health`

## Troubleshooting

**Backend won't start:**
- Check AWS IoT certificates are in correct paths
- Verify `.env` file exists in `app/`

**Frontend can't connect:**
- Check `client/.env.development` has correct backend URL
- Ensure backend is running on port 8000

**Login fails:**
- Verify credentials in `stadiums_config.py`
- Check browser console for JWT errors

**No devices showing:**
- Confirm devices are publishing to correct MQTT topics
- Check backend logs for MQTT connection errors

## Support

For issues or questions, contact the FOV development team.
