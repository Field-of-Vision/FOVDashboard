# CLAUDE.md - LLM Context for FOV Dashboard

This file provides complete technical context for AI assistants working on this codebase. It covers architecture, every file's purpose, deployment, configuration, data flows, and common operations.

## Project Overview

**What:** Real-time IoT device monitoring dashboard for multiple stadium locations (currently Marvel Stadium and Kia Arena in Melbourne, Australia).

**Who:** Field of Vision (FOV) — IoT tablets deployed at stadiums send telemetry (battery, temperature, firmware version) via MQTT to AWS IoT Core. This dashboard displays that data in real-time.

**Stack:**
- **Backend:** Python 3.11 + FastAPI + SQLAlchemy (SQLite) + AWS IoT SDK (`awscrt`/`awsiotsdk`)
- **Frontend:** React 18 + TypeScript + Tailwind CSS (Create React App / `react-scripts`)
- **Messaging:** AWS IoT Core MQTT broker (mTLS certificates)
- **Auth:** JWT (PyJWT) with role-based access (admin vs per-stadium)
- **Hosting:** AWS EC2 (t3.micro, Ubuntu) + Nginx reverse proxy + Let's Encrypt HTTPS

**Repository:** `https://github.com/Field-of-Vision/FOVDashboard.git`
**Production URL:** `https://fovdashboard.com`

---

## Directory Structure

```
FOVDashboard/
├── CLAUDE.md                          ← This file
├── .gitignore
│
└── FOVThingDashboard/                 ← Main application directory
    ├── aws-redeploy.sh                ← Deploy script: build locally, rsync to EC2, restart services
    ├── 00_bootstrap_nginx.sh          ← First-time server setup: install nginx, certbot, get HTTPS cert
    ├── 01_deploy_app.sh               ← Write nginx config + docker compose up (legacy, not current flow)
    ├── setup_nginx.sh                 ← Alternative nginx+certbot setup script
    ├── nginx.config                   ← Production nginx vhost for fovdashboard.com (HTTPS + WSS)
    ├── aviva-nginx.config             ← Reference nginx config for aviva subdomain
    ├── notes.md                       ← Dev notes / debug journal
    ├── README.md
    ├── .gitignore
    │
    ├── scripts/
    │   └── build_and_push.sh          ← Docker build+push script (not currently used; direct rsync flow instead)
    │
    ├── app/                           ← Python backend
    │   ├── main.py                    ← FastAPI app: endpoints, WebSocket, MQTT routing, relay handler
    │   ├── auth.py                    ← JWT creation/validation, password verification
    │   ├── stadiums_config.py         ← CENTRAL CONFIG: stadium definitions, passwords, relay mappings
    │   ├── device.py                  ← DeviceManager: CRUD for devices, in-memory cache + SQLite
    │   ├── database.py                ← SQLAlchemy models (Device, DeviceLog), init_db(), view creation
    │   ├── relay.py                   ← RelayManager: in-memory relay heartbeat tracking (90s timeout)
    │   ├── config.py                  ← FOVDashboardConfig: reads .env for IoT endpoint + cert paths
    │   ├── websockets_manager.py      ← WebSocketManager: stadium-scoped broadcast to connected clients
    │   ├── iot_device_simulator.py    ← Test tool: simulates device MQTT publishes
    │   ├── requirements.txt           ← Python dependencies
    │   ├── .env.example               ← Template for backend .env (not committed)
    │   ├── .env                       ← (gitignored) Actual backend env vars on server
    │   ├── fov_dashboard.db           ← (gitignored) SQLite database file
    │   │
    │   ├── aws_iot/
    │   │   ├── __init__.py
    │   │   ├── IOTClient.py           ← MQTT client wrapper (connect, subscribe, publish, auto-reconnect)
    │   │   └── IOTContext.py          ← AWS CRT bootstrap + IOTCredentials dataclass
    │   │
    │   └── certs/                     ← (gitignored) AWS IoT mTLS certificates
    │       ├── sydney/                ← ap-southeast-2 certs (currently active)
    │       │   ├── certificate.pem.crt
    │       │   ├── private.pem.key
    │       │   ├── public.pem.key
    │       │   ├── AmazonRootCA1.pem
    │       │   └── AmazonRootCA3.pem
    │       └── dublin/                ← eu-west-1 certs (for future Aviva Stadium)
    │
    └── client/                        ← React frontend
        ├── package.json
        ├── tsconfig.json
        ├── tailwind.config.js
        ├── .env.development           ← Dev env: REACT_APP_WS_BASE=ws://localhost:8000, REACT_APP_API_BASE=http://localhost:8000
        ├── .env.production            ← Prod env: wss://fovdashboard.com, https://fovdashboard.com
        ├── .env.example
        ├── .gitignore
        ├── public/                    ← Static assets (favicon, manifest, icons)
        ├── build/                     ← (gitignored) Production build output, served via `npx serve -s build -l 3000`
        │
        └── src/
            ├── index.tsx              ← React entry point
            ├── index.css              ← Tailwind imports + global styles
            ├── App.tsx                ← Root component: token state, login/logout, renders Dashboard or Login
            ├── App.css
            ├── config.ts              ← API_BASE and WS_BASE from env vars (with localhost fallbacks)
            ├── logo.svg
            │
            ├── Pages/
            │   ├── Login.tsx          ← Login page layout (green gradient background + LoginForm)
            │   └── Dashboard.tsx      ← Main dashboard: WebSocket connection, device grid, relay indicator
            │
            └── components/
                ├── LoginForm.tsx       ← Login form: POST /api/login, stores JWT in localStorage
                ├── DeviceComponent.tsx ← Device card: battery bar, temp, firmware, latency, click for history
                ├── DeviceHistoryModal.tsx ← Modal: paginated device log history table
                ├── RelayIndicator.tsx  ← Floating relay status indicator (per-stadium, top-right corner)
                └── ChampionRelay.tsx   ← DEPRECATED: old single-relay indicator (replaced by RelayIndicator)
```

---

## Architecture

```
IoT Tablets (ESP32 / Android)
    │
    │  MQTT publish (mTLS)
    │  Topics: {region}/{stadium}/{device_id}/{metric}
    │          fov/relay/{relay_id}/heartbeat
    ▼
AWS IoT Core (ap-southeast-2)
    │
    │  awsiotsdk subscription
    ▼
┌─────────────────────────────────────────────────┐
│  FastAPI Backend (Python, port 8000)            │
│                                                 │
│  ┌───────────┐  ┌──────────────┐                │
│  │ IOTClient │──│ message_     │──→ DeviceManager ──→ SQLite DB
│  │ (MQTT)    │  │ handler()    │       │              (fov_dashboard.db)
│  └───────────┘  └──────────────┘       │
│                                        ▼
│  ┌───────────┐  ┌──────────────┐  WebSocketManager
│  │ IOTClient │──│ relay_       │──→ (stadium-scoped broadcast)
│  │ (MQTT)    │  │ handler()    │       │
│  └───────────┘  └──────────────┘       │
│                                        ▼
│  REST API:                        WebSocket /ws
│  POST /api/login                  (real-time push)
│  GET  /api/devices                     │
│  GET  /api/relays                      │
│  GET  /api/device/{name}/history       │
│  GET  /api/meta/stadiums               │
│  GET  /api/health                      │
│  GET  /api/status                      │
└────────────────────────────────────────┤
                                         │
                        Nginx (port 443) │
                        ┌────────────────┤
                        │  / → :3000     │
                        │  /api/ → :8000 │
                        │  /ws → :8000   │
                        └────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────┐
│  React Frontend (port 3000, served via `serve`) │
│                                                 │
│  Login Page ──→ Dashboard                       │
│                 ├── Device cards (grid)          │
│                 ├── RelayIndicator (top-right)   │
│                 ├── Filter/Search/Sort controls  │
│                 └── Toast notifications          │
└─────────────────────────────────────────────────┘
```

---

## Production Deployment

### AWS Resources

| Resource | Value |
|----------|-------|
| **EC2 Instance ID** | `i-0a7267749f5b9e67b` |
| **Instance Type** | `t3.micro` (~$3.50/month) |
| **Region** | `ap-southeast-2` (Sydney) |
| **AMI** | `ami-0c73bd9145b5546f5` (Ubuntu 22.04) |
| **Elastic IP** | `54.153.141.18` |
| **EIP Allocation ID** | `eipalloc-0c9c14e2d3e5323e3` |
| **Security Group** | `sg-038c4a051f55e906d` (SSH + HTTP + HTTPS) |
| **SSH Key Pair** | `fov-dashboard-key` (private key: `fov-dashboard-key.pem`) |
| **Domain** | `fovdashboard.com` → DNS A record → `54.153.141.18` |
| **SSL** | Let's Encrypt via Certbot + Nginx (auto-renews) |
| **Process Manager** | systemd (`fov-backend`, `fov-frontend`) |
| **Reverse Proxy** | Nginx: `/` → `:3000`, `/api/` → `:8000`, `/ws` → `:8000` |
| **Remote Path** | `/opt/fovdashboard/FOVThingDashboard/` |

### SSH Access

```bash
ssh -i fov-dashboard-key.pem ubuntu@54.153.141.18
```

### Server-Side Layout

```
/opt/fovdashboard/FOVThingDashboard/
├── app/
│   ├── venv/                  ← Python virtualenv (created during initial setup)
│   ├── .env                   ← Production env vars (FOV_JWT_SECRET, IOT cert paths, SMTP, etc.)
│   ├── certs/sydney/          ← AWS IoT mTLS certificates
│   └── fov_dashboard.db       ← SQLite database (persistent)
└── client/
    └── build/                 ← Pre-built React app (built locally, rsynced to server)
```

### systemd Services

The backend runs via a Python venv + uvicorn. The frontend serves the pre-built React app:

```
fov-backend:  /opt/fovdashboard/FOVThingDashboard/app/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
fov-frontend: npx serve -s build -l 3000  (from client/ directory)
```

### How to Deploy Code to Production

**There is NO automatic deployment.** Pushing to GitHub does NOT update the server. You must manually deploy.

**Prerequisites:**
- `fov-dashboard-key.pem` — located at `FOVThingDashboard/fov-dashboard-key.pem` (gitignored). If missing, get it from a team member (see [Onboarding](#onboarding--new-team-member-setup)).
- Node.js 18+ installed locally (the frontend must be built on your machine — the t3.micro EC2 doesn't have enough RAM)
- `rsync` available (Linux/Mac have it by default; **Windows users** need WSL, Git Bash with rsync, or use the manual steps below)
- SSH access working: `ssh -i FOVThingDashboard/fov-dashboard-key.pem ubuntu@54.153.141.18`

#### Option A: Deploy Script (Linux/Mac, or WSL on Windows)

```bash
# From the repo root:
./FOVThingDashboard/aws-redeploy.sh 54.153.141.18

# Or with explicit key path:
./FOVThingDashboard/aws-redeploy.sh 54.153.141.18 --key FOVThingDashboard/fov-dashboard-key.pem
```

That single command does everything:
1. Builds the React frontend locally (`npm run build`)
2. Rsyncs your local codebase + build output to the server (excludes node_modules, .git, .env, certs, .db, venv)
3. SSHs to the server: installs any new Python deps, fixes permissions, restarts `fov-backend` + `fov-frontend` systemd services
4. Runs a health check against `/api/health`

**The script deploys whatever is in your local working directory**, not what's on GitHub. So commit + push first to keep the repo in sync.

#### Option B: Manual Deploy (Windows without WSL, or if the script fails)

```bash
# 1. Make sure .env.production has the right URLs
#    (the deploy script overwrites this, so check it):
#    REACT_APP_WS_BASE=wss://fovdashboard.com
#    REACT_APP_API_BASE=https://fovdashboard.com

# 2. Build the frontend locally
cd FOVThingDashboard/client
npm install --legacy-peer-deps
npm run build
cd ../..

# 3. Tar up the project (excluding large/sensitive dirs)
cd FOVThingDashboard
tar czf /tmp/fov-deploy.tar.gz \
    --exclude='node_modules' --exclude='.git' --exclude='*.db' \
    --exclude='venv' --exclude='app/.env' --exclude='app/certs' \
    --exclude='client/.env.production' --exclude='dashboard-sensitive-files' \
    --exclude='__pycache__' .

# 4. Copy to server and extract
scp -i fov-dashboard-key.pem /tmp/fov-deploy.tar.gz ubuntu@54.153.141.18:/tmp/
ssh -i fov-dashboard-key.pem ubuntu@54.153.141.18 bash <<'EOF'
  set -e
  cd /opt/fovdashboard/FOVThingDashboard
  sudo tar xzf /tmp/fov-deploy.tar.gz
  cd app && source venv/bin/activate && pip install -q -r requirements.txt && deactivate
  sudo chown -R www-data:www-data /opt/fovdashboard/FOVThingDashboard
  sudo systemctl restart fov-backend fov-frontend
  sleep 3
  curl -sf http://127.0.0.1:8000/api/health && echo "Backend healthy" || echo "HEALTH CHECK FAILED"
EOF
```

#### Recommended Full Deploy Flow

```bash
# Commit, push to GitHub, then deploy:
git add -A && git commit -m "your message"
git push origin main
./FOVThingDashboard/aws-redeploy.sh 54.153.141.18   # Linux/Mac
# OR use Option B manual steps above                  # Windows
```

#### Verify After Deploy

- `https://fovdashboard.com` — dashboard should load
- `https://fovdashboard.com/api/health` — should return `{"status": "ok"}`
- Check server logs if something is wrong: `ssh -i FOVThingDashboard/fov-dashboard-key.pem ubuntu@54.153.141.18 'sudo journalctl -u fov-backend -n 50 --no-pager'`

### Nginx Config (Production)

The production nginx config (`nginx.config`) serves `fovdashboard.com`:
- HTTP → HTTPS redirect
- SSL via Let's Encrypt (`/etc/letsencrypt/live/fovdashboard.com/`)
- `location /` → proxy to `:3000` (React `serve`)
- `location /api/` → proxy to `:8000` (FastAPI)
- `location /ws` → proxy to `:8000` with WebSocket upgrade headers, 3600s timeout

### First-Time Server Setup

Run `00_bootstrap_nginx.sh` on a fresh EC2 instance to:
1. Install nginx, certbot, ufw
2. Create initial HTTP vhost
3. Obtain Let's Encrypt certificate
4. Enable firewall (SSH + Nginx Full)

---

## Onboarding — New Team Member Setup

### What's NOT in the Repo (Secrets)

The following files are **gitignored** and must be shared securely (e.g., password manager, encrypted file transfer, or in-person). **Never commit these to the repo or send via Slack/email.**

| File | What It Is | Who Needs It |
|------|-----------|--------------|
| `fov-dashboard-key.pem` | SSH private key for the EC2 instance | Anyone deploying or SSHing to the server |
| `app/certs/sydney/*.pem, *.key, *.crt` | AWS IoT mTLS certificates (ap-southeast-2) | Anyone running the backend locally with real MQTT |
| `app/certs/dublin/*.pem, *.key, *.crt` | AWS IoT mTLS certificates (eu-west-1) | Future: only if Dublin stadiums are added |
| `app/.env` | Backend env vars (JWT secret, SMTP credentials) | Anyone running the backend locally |

### Step-by-Step for a New Developer

1. **Clone the repo:**
   ```bash
   git clone https://github.com/Field-of-Vision/FOVDashboard.git
   cd FOVDashboard
   ```

2. **Get secret files from a team member** (shared securely, not via git):
   - `fov-dashboard-key.pem` — place in the repo root (or wherever convenient; it's gitignored)
   - `app/certs/sydney/` folder — 5 files (certificate, private key, public key, 2x root CA)
   - `app/.env` — copy from `app/.env.example` and fill in real values, or get a copy from a colleague

3. **Set SSH key permissions** (required, or SSH will refuse the key):
   ```bash
   chmod 400 fov-dashboard-key.pem
   ```

4. **Verify SSH access to the server:**
   ```bash
   ssh -i fov-dashboard-key.pem ubuntu@54.153.141.18
   ```

5. **Set up local development** (see [Development Setup](#development-setup) section below):
   ```bash
   # Backend
   cd FOVThingDashboard/app
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

   # Frontend (separate terminal)
   cd FOVThingDashboard/client
   npm install --legacy-peer-deps
   npm start
   ```

6. **Deploy changes to production:**
   ```bash
   ./FOVThingDashboard/aws-redeploy.sh 54.153.141.18
   ```
   The script builds the frontend locally, rsyncs to the server, and restarts services. Requires `fov-dashboard-key.pem` in the repo root (default path).

### What's Safe in the Repo (Public)

These are committed and fine to be public:
- All application source code (backend + frontend)
- `stadiums_config.py` (contains plaintext passwords, but these are low-sensitivity internal credentials — change them if the repo goes public)
- Deployment scripts (`aws-redeploy.sh`, `00_bootstrap_nginx.sh`, etc.)
- Nginx config templates
- `.env.example` files (templates only, no real values)
- This `CLAUDE.md` file (contains AWS resource IDs, which are not secrets — you can't access them without AWS credentials)

### If the Repo Goes Public

If this repo is ever made public, these items in the committed code should be changed first:
- **`stadiums_config.py`** — change all passwords (`temp456`, `temp789`, `admin123`) and move to env vars
- **`CLAUDE.md`** — redact test credentials from the "Test Credentials" table

---

## Configuration

### Stadium Configuration (`app/stadiums_config.py`)

**Single source of truth for all stadium definitions.** Adding a stadium here is all that's needed — the frontend auto-discovers via `/api/meta/stadiums`.

```python
STADIUMS = {
    "marvel": {
        "name": "Marvel Stadium",
        "password": "temp456",
        "region": "ap-southeast-2",
        "iot_endpoint": "a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com",
        "relay_id": "championdata",   # maps this MQTT relay ID to this stadium
    },
    "kia": {
        "name": "Kia Arena",
        "password": "temp789",
        "region": "ap-southeast-2",
        "iot_endpoint": "a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com",
        # no relay_id yet — add when a relay device is deployed
    },
}

ADMIN_PASSWORD = "admin123"
```

**Fields:**
| Field | Required | Purpose |
|-------|----------|---------|
| `name` | Yes | Display name shown in UI |
| `password` | Yes | Plaintext login password (stadium slug is the username) |
| `region` | Yes | AWS region for MQTT topic prefix |
| `iot_endpoint` | Yes | AWS IoT Core endpoint URL |
| `relay_id` | No | MQTT relay device ID; enables relay status indicator for this stadium |
| `topic_prefix` | No | Override default `{region}/{slug}/+` subscription base |

### Backend Config (`app/config.py`)

Reads from `app/.env` with defaults for Sydney:

```python
IOT_ENDPOINT     = "a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com"
IOT_CERT_PATH    = "./certs/sydney/certificate.pem.crt"
IOT_PRIVATE_KEY_PATH = "./certs/sydney/private.pem.key"
IOT_ROOT_CA_PATH = "./certs/sydney/AmazonRootCA1.pem"
```

### Backend Environment Variables (`app/.env`)

```bash
# AWS IoT (defaults in config.py if not set)
IOT_ENDPOINT=a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com
IOT_CERT_PATH=./certs/sydney/certificate.pem.crt
IOT_PRIVATE_KEY_PATH=./certs/sydney/private.pem.key
IOT_ROOT_CA_PATH=./certs/sydney/AmazonRootCA1.pem

# JWT
FOV_JWT_SECRET=dev-secret-change-me    # CHANGE in production

# SQLite (optional, defaults to ./fov_dashboard.db)
DB_PATH=./fov_dashboard.db

# Relay offline threshold
RELAY_OFFLINE_GRACE_S=90

# Email alerts (optional, all must be set for emails to send)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
ALERT_EMAIL_TO=
ALERT_EMAIL_FROM=
```

### Frontend Environment

**Development** (`client/.env.development`):
```
REACT_APP_WS_BASE=ws://localhost:8000
REACT_APP_API_BASE=http://localhost:8000
```

**Production** (`client/.env.production`):
```
REACT_APP_WS_BASE=wss://fovdashboard.com
REACT_APP_API_BASE=https://fovdashboard.com
```

`config.ts` reads these via `process.env.REACT_APP_*` with localhost fallbacks.

---

## MQTT Topics

### Device Telemetry

```
{region}/{stadium}/{device_id}/{metric}

Examples:
  ap-southeast-2/marvel/fov-marvel-tablet-1/battery
  ap-southeast-2/marvel/fov-marvel-tablet-1/temperature
  ap-southeast-2/marvel/fov-marvel-tablet-1/version
  ap-southeast-2/marvel/fov-marvel-tablet-1/ota
  ap-southeast-2/kia/fov-kia-tablet-1/battery
```

**Subscriptions** (per stadium, set up in `start_iot_client()`):
- `{region}/{stadium}/+/battery` → `message_handler`
- `{region}/{stadium}/+/temperature` → `message_handler`
- `{region}/{stadium}/+/version` → `message_handler`
- `{region}/{stadium}/+/ota` → `message_handler`
- `{region}/{stadium}/+/latency/echo` → `latency_echo_handler`

### Relay Heartbeat

```
fov/relay/{relay_id}/heartbeat

Example:
  fov/relay/championdata/heartbeat
```

**Subscription:** `fov/relay/+/heartbeat` → `relay_handler`

The `relay_handler` uses `RELAY_TO_STADIUM` (built from `stadiums_config.py`) to tag each relay with its stadium, enabling per-stadium filtering.

### Latency Ping

```
{region}/{stadium}/latency/ping     ← published by backend every 60s
{region}/{stadium}/+/latency/echo   ← device echoes back, backend measures RTT
```

### Payload Formats

```json
// Battery
{"Battery Percentage": 85}
// or
{"Battery_Percentage": 85}

// Temperature
{"Temperature": 23.5}

// Version
{"Version": "1.1.0"}

// Relay heartbeat (varies by relay firmware)
{"uptime": 12345, ...}

// Latency ping
{"ID": "uuid-string", "ts": 1234567890.123}
```

---

## Data Flows

### 1. Device Message → Dashboard Update

```
MQTT message on {region}/{stadium}/{device}/battery
    ↓
message_handler() in main.py
    ↓ parse topic → extract stadium, device_name, metric_type
    ↓
device_manager.update_device(name, metric, stadium, value)
    ↓ find/create device in SQLite by (name, stadium) composite key
    ↓ parse JSON payload to extract actual value
    ↓ update last_metric_values JSON, last_message_time, wifi_connected=True
    ↓ insert into device_logs table
    ↓ update in-memory cache (self.devices dict)
    ↓ return device_dict
    ↓
schedule_notification(device_name, device_data, stadium=stadium)
    ↓ thread-safe: asyncio.run_coroutine_threadsafe()
    ↓
WebSocketManager.notify_clients(topic, message, stadium)
    ↓ iterate all connected WebSocket clients
    ↓ send to admins + clients whose ctx.stadium matches
    ↓
Frontend Dashboard.tsx ws.onmessage
    ↓ JSON.parse → setDevices(prev => ({...prev, [topic]: data}))
    ↓ React re-renders affected DeviceComponent
```

### 2. Authentication

```
User → POST /api/login {username, password}
    ↓
main.py login()
    ↓ if username == "admin": verify_admin_password() (plaintext compare with ADMIN_PASSWORD)
    ↓ else: verify_stadium_password() (plaintext compare with STADIUMS[slug]["password"])
    ↓
create_access_token(sub_type, sub_value, expires_seconds=43200)
    ↓ JWT payload: {sub_type: "admin"|"stadium", sub: "admin"|slug, iat, exp}
    ↓ signed with FOV_JWT_SECRET (HS256)
    ↓
Response: {token, role, stadium?}
    ↓
Frontend stores in localStorage, attaches as Authorization: Bearer {token}
    ↓
All protected endpoints use Depends(get_current_subject) → decode JWT
    ↓ is_admin(claims) → admin sees everything
    ↓ stadium_from_claims(claims) → filter by stadium
```

### 3. Relay Heartbeat → Status Indicator

```
MQTT message on fov/relay/championdata/heartbeat
    ↓
relay_handler() in main.py
    ↓ extract relay_id from topic
    ↓ RELAY_TO_STADIUM.get("championdata") → "marvel"
    ↓
relay_manager.upsert(rid, pkt)
    ↓ update in-memory dict: last_seen=utcnow(), alive=True
    ↓ tag: relays[rid]["stadium"] = "marvel"
    ↓
schedule_notification("relay:championdata", relay_data, stadium="marvel")
    ↓
WebSocket → only admin + marvel clients receive it
    ↓
Frontend Dashboard.tsx
    ↓ data.topic.startsWith("relay:") → setRelays({...prev, [rid]: data.message})
    ↓
RelayIndicator component
    ↓ matches stadiumMeta entries that have relay_id against relays state
    ↓ renders green/red dot per stadium's relay
```

### 4. Periodic Status Check (every 30s)

```
check_system_status() coroutine (started at app startup)
    ↓
device_manager.check_wifi_status()
    ↓ any device with last_message_time > 61s ago → wifi_connected=False
    ↓ notify WebSocket clients of changed devices
    ↓
relay_manager.refresh()
    ↓ any relay with last_seen > 90s ago → alive=False
    ↓ email alert on state transitions (alive → offline, offline → alive)
    ↓ notify WebSocket clients of changed relays
```

---

## Database Schema

```sql
-- SQLAlchemy models in database.py

CREATE TABLE devices (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,                -- device_id from MQTT topic
    stadium TEXT NOT NULL,             -- stadium slug (e.g., "marvel")
    wifi_connected BOOLEAN DEFAULT 0,  -- online/offline (set by check_wifi_status)
    last_message_time DATETIME,        -- last MQTT message timestamp
    first_seen DATETIME,               -- when device was first created
    last_metric_values TEXT,           -- JSON: {"battery": "85", "temperature": "23.5", "version": "1.1.0"}
    UNIQUE(name, stadium)              -- composite key
);
-- Indexes: idx_device_last_message (last_message_time), stadium, name

CREATE TABLE device_logs (
    id INTEGER PRIMARY KEY,
    device_id INTEGER REFERENCES devices(id),
    timestamp DATETIME NOT NULL,
    metric_type TEXT NOT NULL,          -- 'battery', 'temperature', 'version', 'ota', 'latency'
    metric_value TEXT NOT NULL          -- raw value string
);
-- Index: idx_device_metric_time (device_id, metric_type, timestamp)

-- Normalized view for history queries (auto-created by init_db)
CREATE VIEW device_logs_norm AS
    SELECT dl.id, dl.timestamp AS ts, d.name AS device,
           d.stadium, dl.metric_type AS metric, dl.metric_value AS value
    FROM device_logs dl JOIN devices d ON dl.device_id = d.id;
```

The relay system is **in-memory only** (`RelayManager.relays` dict) — no database table. Relay state resets on backend restart.

---

## API Reference

### `POST /api/login`
Login. Returns JWT token.
```json
// Request
{"username": "marvel", "password": "temp456"}
// Response
{"token": "eyJ...", "role": "stadium", "stadium": "marvel"}
```

### `GET /api/devices` (auth required)
Current device state. Admin sees all; stadium user sees only their devices.
```json
// Response (keyed by device name)
{
  "fov-marvel-tablet-1": {
    "name": "fov-marvel-tablet-1",
    "stadium": "marvel",
    "wifiConnected": true,
    "batteryCharge": 85.0,
    "temperature": 23.5,
    "latencyMs": 142.5,
    "firmwareVersion": "1.1.0",
    "otaStatus": "N/A",
    "lastMessageTime": "2026-02-16T10:00:00",
    "firstSeen": "2026-01-15T08:00:00"
  }
}
```

### `GET /api/relays` (auth required)
Current relay state. Admin sees all; stadium user sees only relays tagged with their stadium.
```json
{
  "championdata": {
    "alive": true,
    "last_seen": "2026-02-16T10:00:00Z",
    "stadium": "marvel",
    "uptime": 12345
  }
}
```

### `GET /api/device/{device_name}/history` (auth required)
Paginated device log history.
- Query params: `metric_type`, `hours` (default 24), `last_id`, `page_size` (default 50)
```json
{
  "logs": [{"id": 100, "ts": "2026-02-16T10:00:00", "metric": "battery", "value": "85"}],
  "hasMore": true,
  "lastId": 100
}
```

### `GET /api/meta/stadiums` (public)
Stadium metadata for UI labels + relay mapping.
```json
{
  "marvel": {"name": "Marvel Stadium", "relay_id": "championdata"},
  "kia": {"name": "Kia Arena", "relay_id": null}
}
```

### `GET /api/health` (public)
Simple health check. Returns `{"status": "ok"}`. Accepts GET, HEAD, POST.

### `GET /api/status` (public)
Debug info: certificate status, device count, WebSocket connections, CPU/memory, relay state.

### `WebSocket /ws?token={jwt}`
Real-time push. Requires JWT in query param.

**Protocol:**
- Server sends initial device state + relay state on connect (filtered by role)
- Server pushes updates as `{"topic": "device_name", "message": {...}}` or `{"topic": "relay:rid", "message": {...}}`
- Keepalive: server sends `"ping"` every 60s, client responds `"pong"` (and vice versa)
- Client receives `"pong"` responses to its own pings

---

## Backend Files — Detailed

### `main.py` (~560 lines)

The central orchestrator. Key sections:

| Section | Lines | Purpose |
|---------|-------|---------|
| Imports + globals | 1-51 | STADIUMS import, `RELAY_TO_STADIUM` reverse lookup, managers |
| `send_email()` | 52-76 | SMTP email alerts for relay state changes |
| `schedule_notification()` | 118-130 | Thread-safe bridge: MQTT thread → asyncio WebSocket broadcast |
| `message_handler()` | 133-156 | Device telemetry: parse topic, update DB, notify clients |
| `latency_echo_handler()` | 160-204 | RTT measurement: match echo to pending ping, compute latency |
| `start_iot_client()` | 207-260 | Create one IOTClient per unique endpoint, subscribe per-stadium topics, start ping loop |
| `relay_handler()` | 263-278 | Relay heartbeat: upsert state, tag with stadium, notify |
| `login()` | 308-320 | POST /api/login |
| `meta_stadiums()` | 334-341 | GET /api/meta/stadiums (includes relay_id) |
| `websocket_endpoint()` | 339-408 | WebSocket: auth, initial state, keepalive loop |
| `get_devices()` | 411-421 | GET /api/devices (filtered by JWT) |
| `get_relays()` | 424-446 | GET /api/relays (filtered by JWT + stadium tag) |
| `get_device_history()` | 448-480 | GET /api/device/{name}/history (paginated) |
| `check_system_status()` | 482-532 | Periodic: device wifi timeout + relay liveness + email alerts |
| `startup_event()` | 534-555 | Start IoT client thread + status checker task + ping housekeeping |

### `auth.py`

- `JWT_SECRET`: from env `FOV_JWT_SECRET`, default `"dev-secret-change-me"`
- `create_access_token()`: 12-hour expiry, HS256
- `get_current_subject()`: FastAPI dependency — extracts JWT from `Authorization: Bearer` header or `access_token` cookie
- `is_admin()` / `stadium_from_claims()`: role helpers

### `device.py` — `DeviceManager`

- In-memory cache: `self.devices: Dict[str, Dict]` (loaded from DB at startup)
- `update_device(name, metric_type, stadium, value)`: find-or-create in DB, parse metric JSON, log to device_logs, update cache
- `check_wifi_status()`: marks devices offline if no message for >61 seconds
- `get_device_history()`: SQL query against `device_logs_norm` view, cursor-based pagination

### `relay.py` — `RelayManager`

- In-memory only: `self.relays: Dict[str, dict]`
- `upsert(rid, pkt)`: set `last_seen=utcnow()`, `alive=True`
- `refresh()`: check all relays, set `alive=False` if `last_seen` > timeout (default 90s)

### `websockets_manager.py` — `WebSocketManager`

- Class-level `clients` dict: `{WebSocket: {"stadium": Optional[str], "is_admin": bool}}`
- `notify_clients(topic, message, stadium)`: sends to admins + matching stadium clients
- Drops disconnected clients on send failure

### `config.py` — `FOVDashboardConfig`

Reads `.env` via `python-dotenv`. Fields: `endpoint`, `cert_path`, `private_key_path`, `root_ca_path`, `relay_topic`.

### `aws_iot/IOTClient.py`

Wraps `awsiotsdk` MQTT connection. Features:
- mTLS connection via `mqtt_connection_builder.mtls_from_path`
- `subscribe(topic, handler)`: remembers subscriptions for auto-resubscribe
- `_on_interrupted` / `_on_resumed`: CRT handles reconnect; client re-subscribes if session not preserved
- `publish(topic, payload)`: QoS 0

### `aws_iot/IOTContext.py`

`IOTCredentials` dataclass (cert paths, endpoint, client_id, port=8883). `IOTContext` creates CRT event loop + bootstrap.

### `iot_device_simulator.py`

Test tool that connects to AWS IoT Core and publishes fake telemetry:
```bash
python iot_device_simulator.py --stadium marvel --device fov-marvel-tablet-test-2 --interval 5
```
Publishes version once on startup, then loops: temperature (random 50-100) + battery (random 0-100).

---

## Frontend Files — Detailed

### `App.tsx`

Root component. Manages `token` state (from localStorage). Shows `LoginPage` or `Dashboard` + floating Logout button.

### `Pages/Login.tsx`

Full-screen green gradient with `LoginForm` centered.

### `Pages/Dashboard.tsx` (~360 lines)

The main dashboard page. Key logic:

1. **State:** `devices`, `relays`, `stadiumMeta`, `connectionStatus`, `filter`, `query`, `sortAsc`
2. **On mount (`useEffect`):**
   - Fetch `/api/meta/stadiums` → `stadiumMeta` (name + relay_id per stadium)
   - Fetch `/api/devices` → initial device state
   - Fetch `/api/relays` → initial relay state
   - Connect WebSocket with JWT token
3. **WebSocket messages:**
   - `topic.startsWith("relay:")` → update `relays` state
   - Otherwise → update `devices` state + trigger toast on online/offline transitions
4. **Renders:**
   - `RelayIndicator`: builds entries from `stadiumMeta` (stadiums with `relay_id`) matched against `relays` state. Admin sees all; stadium user sees only their relay.
   - Filter buttons (All/Online/Offline) with counts
   - Search bar + sort toggle
   - Device grid: filtered, sorted `DeviceComponent` cards
   - Connection status badge
   - Toast container

### `components/LoginForm.tsx`

Form → `POST /api/login` → stores token/role/stadium in localStorage → calls `onLogin(token)`.

### `components/DeviceComponent.tsx`

Card showing: WiFi status dot, battery bar + percentage, temperature, latency RTT (if >= 0), firmware version. Clicking opens `DeviceHistoryModal`.

### `components/DeviceHistoryModal.tsx`

Modal with scrollable table of device logs. Infinite scroll pagination via `last_id`. Formats battery/temperature values from JSON.

### `components/RelayIndicator.tsx`

Floating indicator (fixed top-right, z-50). Receives `entries: {stadiumName, alive, lastSeen}[]`. Renders one status line per entry with online/offline + last seen time. Hidden when WebSocket disconnected or no entries.

### `config.ts`

```typescript
export const API_BASE = process.env.REACT_APP_API_BASE ?? "http://localhost:8000";
export const WS_BASE  = process.env.REACT_APP_WS_BASE  ?? (protocol === "https:" ? "wss://..." : "ws://...");
```

---

## Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- AWS IoT certificates in `app/certs/sydney/`
- Backend `.env` file (copy from `.env.example`)

### Running Locally

```bash
# Terminal 1 - Backend
cd FOVThingDashboard/app
python -m venv venv
source venv/bin/activate        # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd FOVThingDashboard/client
npm install --legacy-peer-deps
npm start                       # dev server on port 3000
```

### Test Credentials

| Username | Password | Role | Sees |
|----------|----------|------|------|
| `admin` | `admin123` | Admin | All devices + all relays |
| `marvel` | `temp456` | Stadium | Marvel devices + Marvel relay |
| `kia` | `temp789` | Stadium | Kia devices only (no relay yet) |

### Simulating Devices

```bash
cd FOVThingDashboard/app
source venv/bin/activate

# Simulate a Marvel tablet
python iot_device_simulator.py --stadium marvel --device fov-test-1 --interval 5

# Simulate a Kia tablet
python iot_device_simulator.py --stadium kia --device fov-kia-test-1 --interval 10
```

Or use the AWS IoT Console MQTT test client to publish directly:
- Topic: `ap-southeast-2/marvel/test_device/battery`
- Payload: `{"Battery Percentage": 75}`

---

## Common Modifications

### Add a New Stadium

**Only edit:** `app/stadiums_config.py`

```python
"new_stadium": {
    "name": "New Stadium",
    "password": "secure_password",
    "region": "ap-southeast-2",
    "iot_endpoint": "a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com",
    # "relay_id": "new_relay",  # add when relay device is deployed
},
```

Restart backend. Frontend auto-discovers via `/api/meta/stadiums`.

### Add a Relay for an Existing Stadium

1. Deploy relay hardware, configure it to publish to `fov/relay/<relay_id>/heartbeat`
2. Add `"relay_id": "<relay_id>"` to the stadium in `stadiums_config.py`
3. Restart backend. The `RELAY_TO_STADIUM` dict auto-builds, `relay_handler` starts tagging, frontend shows the indicator.

### Add a New Metric (e.g., "humidity")

1. **Backend (`main.py`):** Add subscription in `start_iot_client()`: `client.subscribe(topic=f"{base}/humidity", handler=message_handler)`
2. **Backend (`device.py`):** Add parsing logic in `update_device()` for the new metric key
3. **Frontend (`DeviceComponent.tsx`):** Add display element for humidity

### Change Auth to Use Password Hashing

Edit `auth.py`:
- `verify_stadium_password()`: replace `==` with `bcrypt.verify(password, hash)`
- `verify_admin_password()`: same
- Update `stadiums_config.py` passwords to bcrypt hashes

### Add a New AWS Region

Currently all stadiums use Sydney (`ap-southeast-2`) certs. To add Dublin:
1. Place Dublin certs in `app/certs/dublin/`
2. Add a stadium with `"iot_endpoint": "xxx-ats.iot.eu-west-1.amazonaws.com"`
3. The backend already creates one IOTClient per unique endpoint, so it will auto-connect to Dublin

---

## Debugging & Troubleshooting

### Backend Not Starting

```bash
# Check systemd logs on server
sudo journalctl -u fov-backend -n 50 --no-pager

# Common issues:
# - Missing .env file or cert paths
# - Port 8000 already in use
# - Python package missing (run pip install -r requirements.txt)
```

### Devices Not Appearing

1. Check MQTT topic format: `{region}/{stadium}/{device_id}/{metric}`
2. Verify stadium slug in topic matches key in `stadiums_config.py`
3. Check backend logs for `"Received message from topic"` prints
4. Verify AWS IoT certificates are valid and paths correct in `.env`

### Relay Not Showing

1. Verify relay publishes to `fov/relay/<relay_id>/heartbeat`
2. Check `stadiums_config.py` has matching `"relay_id": "<relay_id>"`
3. Check backend logs for `relay_handler` output
4. Hit `GET /api/relays` to see if relay state exists

### WebSocket Not Connecting

1. Check browser console for WebSocket connection errors
2. Verify nginx WebSocket upgrade headers (location /ws block)
3. Check `proxy_read_timeout` is set high enough (3600s in nginx config)
4. Verify JWT token isn't expired (12-hour expiry)

### Database Issues

```bash
# On server
cd /opt/fovdashboard/FOVThingDashboard/app
sqlite3 fov_dashboard.db

sqlite> SELECT * FROM devices;
sqlite> SELECT COUNT(*) FROM device_logs;
sqlite> SELECT * FROM device_logs_norm ORDER BY id DESC LIMIT 10;
```

If the database gets corrupted, deleting `fov_dashboard.db` and restarting the backend recreates it (devices will re-register on next MQTT message).

### Test Endpoints

```bash
# Health check
curl http://localhost:8000/api/health

# Login
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Get devices (with token)
curl http://localhost:8000/api/devices \
  -H "Authorization: Bearer <token>"

# Stadium metadata
curl http://localhost:8000/api/meta/stadiums
```

---

## Security Notes

**Current state (acceptable for internal tool):**
- Passwords are plaintext in `stadiums_config.py`
- JWT secret defaults to `"dev-secret-change-me"` — **must set `FOV_JWT_SECRET` in production `.env`**
- CORS allows specific origins (fovdashboard.com, localhost)
- AWS IoT uses mTLS certificates (secure)
- Certificates and `.env` files are gitignored

**If security needs to be hardened:**
- Hash passwords with bcrypt (see `passlib[bcrypt]` already in requirements.txt)
- Rotate JWT secret periodically
- Lock down CORS origins
- Add rate limiting to login endpoint
- Move secrets to AWS Secrets Manager or environment variables

---

## Python Dependencies (`requirements.txt`)

| Package | Purpose |
|---------|---------|
| `fastapi` 0.114 | Web framework |
| `uvicorn` 0.30 | ASGI server |
| `SQLAlchemy` 2.0 | ORM / database |
| `PyJWT` 2.9 | JWT encoding/decoding |
| `awscrt` 0.21 + `awsiotsdk` 1.22 | AWS IoT Core MQTT client |
| `python-dotenv` | `.env` file loading |
| `psutil` | System metrics for /api/status |
| `passlib[bcrypt]` | Password hashing (available but not yet used) |

## Frontend Dependencies (`package.json`)

| Package | Purpose |
|---------|---------|
| `react` 18 + `react-dom` 18 | UI framework |
| `react-scripts` 5 | Build tooling (CRA) |
| `typescript` 5 | Type checking |
| `tailwindcss` 3 | Utility CSS |
| `lucide-react` | Icons (Battery, Wifi, Thermometer, etc.) |
| `react-toastify` | Toast notifications for device state changes |
| `serve` | Static file server for production (`npx serve -s build -l 3000`) |

---

## Testing Checklist

When making changes, verify:
- [ ] Backend starts without errors (`python -m uvicorn main:app`)
- [ ] Frontend compiles without TypeScript errors (`npx tsc --noEmit`)
- [ ] Login works for admin and stadium users
- [ ] Admin sees all devices, stadium user sees only theirs
- [ ] Relay indicator shows for stadiums with `relay_id`, hidden for others
- [ ] Admin sees all relay indicators, stadium user sees only theirs
- [ ] MQTT messages update dashboard in real-time (use simulator)
- [ ] Device going offline triggers toast notification
- [ ] Device history modal loads on card click
- [ ] Logout clears token and returns to login page

---

**Last Updated:** 2026-02-16
