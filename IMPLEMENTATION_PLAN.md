# FOV Dashboard - Implementation Plan

## Overview

Code review revealed 10 bugs and a migration need from DigitalOcean to AWS EC2.
Phase 1 focuses on fixing all bugs. Phase 2 (AWS deployment) will be planned separately.

---

## Phase 1: Bug Fixes

### 1.1 - [CRITICAL] Create missing `device_logs_norm` SQL view
- **File:** `FOVThingDashboard/app/database.py`
- **Problem:** `device.py:138-175` queries view `device_logs_norm` that doesn't exist. `/api/device/{name}/history` crashes.
- **Fix:** In `init_db()`, after `Base.metadata.create_all(engine)`, execute:
  ```sql
  CREATE VIEW IF NOT EXISTS device_logs_norm AS
  SELECT dl.id, dl.timestamp AS ts, d.name AS device,
         d.stadium, dl.metric_type AS metric, dl.metric_value AS value
  FROM device_logs dl JOIN devices d ON dl.device_id = d.id
  ```
- **Also:** Add `from sqlalchemy import text` to imports
- **Status:** [x] Done

### 1.2 - [CRITICAL] Refactor `config.py` to use env vars + remove dead code
- **File:** `FOVThingDashboard/app/config.py`
- **Problem:** All IoT config hardcoded. Dead topic fields (`region_prefix`, `version_topic`, etc.) never used by `main.py`. `.env` is ignored.
- **Fix:** Keep only used fields (`endpoint`, cert paths, `relay_topic`). Read from `os.getenv()` with sensible defaults. Add `python-dotenv` and `load_dotenv()`.
- **Note:** Multi-region support is preserved in `main.py:start_iot_client()` which builds subscriptions per-stadium from `stadiums_config.py`.
- **Status:** [x] Done

### 1.3 - [HIGH] Fix `.env` file
- **File:** `FOVThingDashboard/app/.env`
- **Problem:** `IOT_ENDPOINT` truncated (missing region). Cert paths reference wrong directory.
- **Fix:** Correct endpoint to `a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com`. Align cert paths with actual directory structure.
- **Status:** [x] Done

### 1.4 - [HIGH] Update simulator stadium choices
- **File:** `FOVThingDashboard/app/iot_device_simulator.py`
- **Problem:** `choices=["aviva", "marvel"]` but aviva disabled, kia missing.
- **Fix:** Update to `choices=["marvel", "kia"]`. Add kia to `DEFAULT_REGION_BY_STADIUM`. Update docstring.
- **Status:** [x] Done

### 1.5 - [MEDIUM] Add JSON error handling to `relay_handler`
- **File:** `FOVThingDashboard/app/main.py:277-281`
- **Problem:** `json.loads()` crashes on malformed MQTT payload.
- **Fix:** Wrap in try/except.
- **Status:** [x] Done

### 1.6 - [MEDIUM] Remove dead `TypeError` catch in message handlers
- **File:** `FOVThingDashboard/app/main.py:151-156` and `205-210`
- **Problem:** try/except TypeError for old `update_device` signature masks real bugs. `device.py` already handles both signatures internally.
- **Fix:** Remove try/except, call `update_device()` directly in both `message_handler` and `latency_echo_handler`.
- **Status:** [x] Done

### 1.7 - [MEDIUM] Fix Device.name uniqueness (per-stadium instead of global)
- **File:** `FOVThingDashboard/app/database.py:15`, `FOVThingDashboard/app/device.py`
- **Problem:** `name = Column(String, unique=True)` prevents same device name across stadiums.
- **Fix:** Remove `unique=True`, add composite unique index `(name, stadium)`. Update `device.py` queries to filter by both. Delete existing `fov_dashboard.db` to reset.
- **Status:** [x] Done

### 1.8 - [MEDIUM] Clean unused imports in `main.py`
- **File:** `FOVThingDashboard/app/main.py`
- **Fix:** Remove `defaultdict` (line 6), `timezone` (line 7), `Response` from FastAPI import (line 8), redundant `import os` (line 287).
- **Status:** [x] Done

### 1.9 - [LOW] Fix bootstrap.sh WS_BASE bug
- **File:** `FOVThingDashboard/bootstrap.sh:127`
- **Problem:** Writes `REACT_APP_WS_BASE=wss://$DOMAIN/ws` but frontend appends `/ws`, causing doubled path.
- **Fix:** Change to `REACT_APP_WS_BASE=wss://$DOMAIN`.
- **Status:** [x] Done

### 1.10 - [LOW] Make STADIUM_LABELS dynamic + update stale aviva refs
- **Files:** `FOVThingDashboard/client/src/Pages/Dashboard.tsx:33-36`, `FOVThingDashboard/bootstrap.sh:304`
- **Problem:** Hardcoded STADIUM_LABELS has aviva (disabled) but not kia.
- **Fix:** Fetch labels from `/api/meta/stadiums` on Dashboard mount instead of hardcoding. Update bootstrap.sh credential output.
- **Status:** [x] Done

### 1.11 - Add `python-dotenv` to requirements.txt
- **File:** `FOVThingDashboard/app/requirements.txt`
- **Fix:** Add `python-dotenv>=1.0.0`. (Dependency of fix 1.2)
- **Status:** [x] Done

### 1.12 - Test with IoT device simulator
- **Action:** Run `python iot_device_simulator.py --stadium marvel` to verify full pipeline works after fixes.
- **Verify:** Backend starts, simulator connects, messages flow through, device history endpoint works.
- **Status:** [x] Done

### 1.13 - Update CLAUDE.md
- **File:** `CLAUDE.md`
- **Action:** Update documentation to reflect changes made (config.py refactor, removed dead code, dynamic stadium labels, etc.)
- **Status:** [x] Done

---

## Phase 2: AWS EC2 Deployment

### 2.1 - Updated `bootstrap.sh` for EC2
- **File:** `FOVThingDashboard/bootstrap.sh`
- **Changes:** Added `--ip-only` flag, HTTP-only nginx config, auto-detect public IP from EC2 metadata, protocol-aware frontend env
- **Status:** [x] Done

### 2.2 - Created `aws-deploy.sh`
- **File:** `FOVThingDashboard/aws-deploy.sh`
- **What:** One-command EC2 launch script. Creates security group, key pair, launches t3.micro with user-data bootstrap.
- **Config:** Region=ap-southeast-2, AMI=ami-0c73bd9145b5546f5 (Ubuntu 22.04), repo=Field-of-Vision/FOVDashboard
- **Status:** [x] Done

### 2.3 - Created `aws-redeploy.sh`
- **File:** `FOVThingDashboard/aws-redeploy.sh`
- **What:** Code update script. Rsyncs changes, rebuilds frontend, restarts services.
- **Status:** [x] Done

### 2.4 - Deploy and verify
- **Action:** Run `./aws-deploy.sh`, SCP certs, test with simulator
- **Instance:** i-0a7267749f5b9e67b, IP: 54.252.193.6 (ap-southeast-2)
- **Result:** Backend connected to AWS IoT Core, simulator publishes messages, all endpoints working
- **Status:** [x] Done

### Deployment Notes
- **t3.micro has only 1GB RAM** - not enough for React builds. Frontend must be built locally and SCP'd to server.
- **bootstrap.sh** creates a 2GB swap file and skips frontend build if `client/build/` already exists.
- **aws-redeploy.sh** builds frontend locally, then syncs code + build to server via rsync/scp.
- **IP changes on stop/start** - use an Elastic IP if you need a stable address.

### Deployment Steps
```bash
# 1. From FOVThingDashboard/ directory:
./aws-deploy.sh

# 2. Wait ~5 min for bootstrap, then build frontend locally and SCP:
cd client && npm run build && cd ..
scp -i fov-dashboard-key.pem -r client/build ubuntu@<IP>:/tmp/client-build
ssh -i fov-dashboard-key.pem ubuntu@<IP> 'sudo cp -r /tmp/client-build /opt/fovdashboard/FOVThingDashboard/client/build && sudo chown -R www-data:www-data /opt/fovdashboard/FOVThingDashboard/client/build && sudo systemctl restart fov-frontend'

# 3. SCP AWS IoT certs:
scp -i fov-dashboard-key.pem app/certs/sydney/certificate.pem.crt app/certs/sydney/private.pem.key app/certs/sydney/AmazonRootCA1.pem ubuntu@<IP>:/tmp/
ssh -i fov-dashboard-key.pem ubuntu@<IP> 'sudo mkdir -p /opt/fovdashboard/FOVThingDashboard/app/certs/sydney && sudo cp /tmp/certificate.pem.crt /tmp/private.pem.key /tmp/AmazonRootCA1.pem /opt/fovdashboard/FOVThingDashboard/app/certs/sydney/ && sudo chown -R www-data:www-data /opt/fovdashboard/FOVThingDashboard/app/certs'

# 4. Restart backend:
ssh -i fov-dashboard-key.pem ubuntu@<IP> 'sudo systemctl restart fov-backend'

# 5. Open http://<IP> in browser

# 6. For code updates:
./aws-redeploy.sh <IP>
```
