# CLAUDE.md - LLM Context for FOV Dashboard

This file provides technical context for AI assistants working on this codebase.

## Project Overview

**Purpose:** Real-time IoT device monitoring dashboard for multiple stadium locations
**Stack:** FastAPI (Python backend) + React (TypeScript frontend) + AWS IoT Core (MQTT)
**Database:** SQLite
**Authentication:** JWT with role-based access (admin vs stadium-specific)

## Architecture Flow

```
IoT Devices (ESP32/similar)
    ↓ (MQTT publish to AWS IoT Core)
    ↓ Topics: {region}/{stadium}/{device_id}/{metric}
    ↓
AWS IoT Core MQTT Broker
    ↓ (AWS IoT SDK subscription)
    ↓
FastAPI Backend (main.py)
    ├─→ MQTT Client (aws_iot/)
    ├─→ Device Manager (device.py)
    ├─→ SQLite Database (fov_dashboard.db)
    ├─→ WebSocket Manager (websockets_manager.py)
    └─→ REST API + WebSocket Server
            ↓
React Frontend (TypeScript)
    ├─→ Login (JWT auth)
    ├─→ Dashboard (real-time updates via WebSocket)
    └─→ Device Cards (battery, temp, version, OTA)
```

## Key Files and Responsibilities

### Backend (`FOVThingDashboard/app/`)

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, API endpoints, WebSocket handler, MQTT message router |
| `auth.py` | JWT creation/validation, password verification (plaintext) |
| `stadiums_config.py` | **CENTRAL CONFIG** - Stadium definitions, passwords, AWS regions |
| `device.py` | `DeviceManager` class - CRUD operations for devices in SQLite |
| `database.py` | SQLAlchemy setup, Device model definition |
| `relay.py` | `RelayManager` class - tracks relay device status |
| `config.py` | Configuration loader (reads from env vars) |
| `websockets_manager.py` | Manages WebSocket connections, broadcasts updates to clients |
| `aws_iot/IOTClient.py` | AWS IoT MQTT client wrapper |
| `aws_iot/IOTContext.py` | AWS IoT connection context, credentials management |

### Frontend (`FOVThingDashboard/client/src/`)

| File | Purpose |
|------|---------|
| `App.tsx` | Main app component, auth state, logout button |
| `components/LoginForm.tsx` | Login form, fetches stadium list from `/api/meta/stadiums` |
| `components/Dashboard.tsx` | Main dashboard, displays device cards, WebSocket connection |
| `services/api.ts` | API client, HTTP requests with JWT token in Authorization header |

## Data Flow

### 1. Device Registration (MQTT → Backend → DB)

```python
# When device publishes FIRST message to ANY topic:
# Topic: eu-west-1/aviva/device001/battery
# Payload: {"value": 85}

# main.py mqtt_message_callback():
1. Parse topic: region="eu-west-1", stadium="aviva", device_id="device001", metric="battery"
2. Check if device exists in DB (device_manager.get_device_by_name_and_stadium())
3. If not exists: Create device (device_manager.create_device())
4. Update device metric (device_manager.update_device())
5. Broadcast to WebSocket clients (websockets_manager.broadcast())
```

### 2. Authentication Flow

```
User submits login form → POST /api/auth/login
    ↓
Backend checks:
  - If username == "admin": verify_admin_password() → plaintext comparison with ADMIN_PASSWORD
  - Else: verify_stadium_password() → plaintext comparison with STADIUMS[username]["password"]
    ↓
If valid: create_access_token() → JWT with payload:
  {
    "sub_type": "admin" or "stadium",
    "sub": "admin" or stadium_slug,
    "iat": timestamp,
    "exp": timestamp + 12 hours
  }
    ↓
Frontend stores token in localStorage
    ↓
All subsequent requests include: Authorization: Bearer {token}
```

### 3. Device Filtering by Role

```python
# In main.py, GET /api/devices endpoint:

claims = get_current_subject(creds)  # Decode JWT

if is_admin(claims):
    # Admin sees ALL devices
    devices = device_manager.get_all_devices()
else:
    # Stadium user sees only their devices
    stadium = stadium_from_claims(claims)
    devices = device_manager.get_devices_by_stadium(stadium)
```

### 4. WebSocket Real-Time Updates

```
Backend receives MQTT message → Updates DB → Broadcasts to WebSocket clients
    ↓
Frontend Dashboard.tsx useEffect():
  - Connects to ws://localhost:8000/ws with JWT token
  - Receives JSON updates: {"type": "device_update", "device": {...}}
  - Updates React state → Re-renders device cards
```

## Configuration

### Stadium Configuration (`stadiums_config.py`)

**This is the single source of truth for stadium definitions.**

```python
STADIUMS = {
    "stadium_slug": {  # Used as username for login
        "name": "Display Name",
        "password": "plaintext_password",  # ⚠️ No hashing (not security-sensitive)
        "region": "aws-region",            # e.g., "eu-west-1"
        "iot_endpoint": "xxxxx-ats.iot.{region}.amazonaws.com",
    },
}

ADMIN_PASSWORD = "plaintext_admin_password"
```

**Adding a new stadium:** Just add to this dict + restart backend. No code changes needed.

### MQTT Topic Pattern

```
{region}/{stadium}/{device_id}/{metric}

Metrics:
- battery → Battery percentage (0-100)
- temperature → Temperature in Celsius
- version → Firmware version string
- ota → OTA update status/response
```

The backend subscribes to: `{region}/{stadium}/+/{metric}` (+ is wildcard for any device_id)

## Database Schema

```sql
-- SQLAlchemy model in database.py
CREATE TABLE devices (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,           -- device_id from MQTT topic
    stadium TEXT NOT NULL,        -- stadium slug
    region TEXT NOT NULL,         -- AWS region
    battery_percentage INTEGER,   -- 0-100
    temperature REAL,             -- Celsius
    version TEXT,                 -- Firmware version
    last_seen DATETIME,           -- Last MQTT message timestamp
    UNIQUE(name, stadium)         -- One device per stadium (can have same name across stadiums)
);

-- Relay monitoring (separate table, see relay.py)
CREATE TABLE relays (
    id INTEGER PRIMARY KEY,
    device_name TEXT UNIQUE,
    last_seen DATETIME
);
```

## Common Modifications

### Add a New Metric (e.g., "humidity")

1. **Backend (`main.py`):**
   - Add to `SUBSCRIBED_METRICS` list
   - Add column to Device model in `database.py`: `humidity = Column(Float)`
   - Update `device.py` update logic to handle humidity

2. **Frontend (`Dashboard.tsx`):**
   - Add humidity display to device card

### Change Authentication System

All auth logic is in `auth.py`:
- `verify_stadium_password()` - Currently plaintext comparison
- `verify_admin_password()` - Currently plaintext comparison
- To add hashing: Import bcrypt, change comparison to `bcrypt.verify(password, hash)`

### Add New Stadium

**Only need to edit:** `stadiums_config.py`

```python
STADIUMS = {
    # ... existing ...
    "new_stadium": {
        "name": "New Stadium",
        "password": "password123",
        "region": "us-east-1",
        "iot_endpoint": "xxxxx-ats.iot.us-east-1.amazonaws.com",
    },
}
```

Restart backend. Frontend auto-discovers via `/api/meta/stadiums`.

### Debug MQTT Issues

```python
# In main.py, mqtt_message_callback() has extensive logging:
print(f"📨 MQTT message: {topic} → {payload}")

# Check:
1. Is backend subscribed to correct topics? (Check _setup_mqtt_subscriptions())
2. Are devices publishing to correct topic format?
3. Is AWS IoT certificate valid? (Check IOT_CERT_PATH in .env)
```

## Security Notes

**Current state:**
- Passwords are **plaintext** in `stadiums_config.py` (not security-sensitive per requirements)
- JWT secret is in `.env` (change `FOV_JWT_SECRET` in production)
- CORS is open in dev (middleware in `main.py`)

**Production changes needed:**
- Set strong JWT secret
- Configure CORS to only allow production domain
- Use HTTPS (Nginx reverse proxy with Let's Encrypt)

## Running the Project

### Development (Local)

```bash
# Terminal 1 - Backend
cd FOVThingDashboard/app
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 - Frontend
cd FOVThingDashboard/client
npm start
```

### Testing Credentials

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Admin (sees all) |
| `aviva` | `temp123` | Aviva only |
| `marvel` | `temp456` | Marvel only |
| `kia` | `temp789` | Kia only |

## API Reference

### Authentication

```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "aviva",
  "password": "temp123"
}

Response:
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "role": "stadium",
  "stadium": "aviva"
}
```

### Get Devices (Filtered by Role)

```http
GET /api/devices
Authorization: Bearer {token}

Response:
[
  {
    "id": 1,
    "name": "device001",
    "stadium": "aviva",
    "region": "eu-west-1",
    "battery_percentage": 85,
    "temperature": 23.5,
    "version": "v1.2.3",
    "last_seen": "2025-01-18T12:00:00"
  }
]
```

### Trigger OTA Update

```http
POST /api/devices/{device_id}/ota
Authorization: Bearer {token}
Content-Type: application/json

{
  "version": "v1.3.0",
  "url": "https://example.com/firmware.bin"
}
```

### WebSocket (Real-Time Updates)

```javascript
// Frontend connects with JWT in query param
const ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);

// Receives updates:
{
  "type": "device_update",
  "device": {
    "id": 1,
    "name": "device001",
    "battery_percentage": 86,
    // ... other fields
  }
}
```

## Error Handling

### Common Issues

1. **"Token expired" (401):**
   - JWT tokens expire after 12 hours
   - Frontend should redirect to login

2. **"Not authenticated" (401):**
   - Token missing or invalid
   - Check Authorization header format: `Bearer {token}`

3. **Device not appearing:**
   - Check MQTT topic format matches: `{region}/{stadium}/{device_id}/{metric}`
   - Verify stadium slug in topic matches `stadiums_config.py`

4. **MQTT connection fails:**
   - Check AWS IoT certificates in `.env` (`IOT_CERT_PATH`, `IOT_PRIVATE_KEY_PATH`, `IOT_ROOT_CA_PATH`)
   - Verify endpoint URL is correct

## Code Style

- **Backend:** Python, FastAPI async patterns, type hints
- **Frontend:** TypeScript, React hooks, Tailwind CSS
- **Database:** SQLAlchemy ORM, avoid raw SQL

## Future Enhancements (Not Implemented)

- [ ] Historical data charts (currently only shows latest values)
- [ ] Email alerts for low battery (SMTP setup exists but not fully tested)
- [ ] Multi-region MQTT clients (currently only connects to one region's IoT endpoint)
- [ ] Device grouping/tagging
- [ ] User management UI (currently only via `stadiums_config.py`)

## Debugging Tips

### Enable Verbose Logging

```python
# In main.py, add:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test MQTT Without Devices

Use AWS IoT MQTT test client:
1. Go to AWS IoT Console → Test
2. Publish to: `eu-west-1/aviva/test_device/battery`
3. Payload: `{"value": 75}`
4. Should appear in dashboard immediately

### Check Database

```bash
cd FOVThingDashboard/app
sqlite3 fov_dashboard.db
sqlite> SELECT * FROM devices;
```

## File Locations

- **Database:** `FOVThingDashboard/app/fov_dashboard.db`
- **Backend env:** `FOVThingDashboard/app/.env`
- **Frontend env (dev):** `FOVThingDashboard/client/.env.development`
- **Frontend env (prod):** `FOVThingDashboard/client/.env.production`
- **AWS certs:** `FOVThingDashboard/app/aws-iot-certs/`

## Critical Functions

### `main.py:mqtt_message_callback(client, userdata, message)`

**Called when:** Any MQTT message received
**Does:**
1. Parse topic into region/stadium/device_id/metric
2. Create device if not exists
3. Update device metric in DB
4. Broadcast to WebSocket clients

### `device.py:DeviceManager.update_device()`

**Called when:** Device data needs updating
**Does:**
1. Find device in DB
2. Update only changed fields
3. Set `last_seen` to current timestamp
4. Commit to DB

### `websockets_manager.py:WebSocketManager.broadcast()`

**Called when:** Device data changes
**Does:**
1. Serialize device to JSON
2. Send to all connected WebSocket clients
3. Handle disconnections gracefully

## Testing Checklist

When making changes, verify:
- [ ] Backend starts without errors
- [ ] Frontend compiles without TypeScript errors
- [ ] Login works for admin and stadium users
- [ ] Admin sees all devices, stadium users see only theirs
- [ ] MQTT messages update dashboard in real-time
- [ ] OTA button triggers MQTT publish
- [ ] Logout clears token and redirects to login

---

**Last Updated:** 2025-01-18
**Codebase Version:** Post-plaintext-auth simplification
