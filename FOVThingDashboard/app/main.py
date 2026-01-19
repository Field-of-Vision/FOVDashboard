import asyncio
import json
import os
import time
import uuid
from collections import defaultdict
from datetime import timezone
from fastapi import FastAPI, WebSocket, HTTPException, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from datetime import datetime, timedelta
from threading import Thread
from typing import Optional
from pydantic import BaseModel  # added

from aws_iot.IOTClient import IOTClient
from aws_iot.IOTContext import IOTContext, IOTCredentials
from database import init_db
from device import DeviceManager
from relay import RelayManager
from config import FOVDashboardConfig
from websockets_manager import WebSocketManager
import smtplib
from email.message import EmailMessage
from email.utils import formatdate


# auth helpers (added) - JWT functions
from auth import (
    create_access_token,
    decode_token,
    get_current_subject,
    is_admin,
    stadium_from_claims,
    verify_admin_password,
    verify_stadium_password,
)

# stadiums (NEW)
from stadiums_config import STADIUMS

app = FastAPI()
SessionFactory = init_db()
device_manager = DeviceManager(SessionFactory)
config = FOVDashboardConfig()
relay_manager  = RelayManager()

ALERT_GRACE_S = int(os.getenv("RELAY_OFFLINE_GRACE_S", "90"))
_last_relay_alert_state: dict[str, bool] = {}  # remember prior state to avoid spam

# Global event loop reference for thread-safe task scheduling
_main_loop: Optional[asyncio.AbstractEventLoop] = None

def send_email(subject: str, body: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd  = os.getenv("SMTP_PASS")
    to   = os.getenv("ALERT_EMAIL_TO")
    frm  = os.getenv("ALERT_EMAIL_FROM", user)

    if not all([host, port, user, pwd, to]):
        print("Email not sent: SMTP env not set"); return

    try:
        msg = EmailMessage()
        msg["From"] = frm
        msg["To"] = to
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg.set_content(body)

        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
    except Exception as e:
        print(f"Email send failed: {e}")


# store send-timestamp per ping-id
_pending_pings: dict[str, float] = {}
PING_INTERVAL_S = 60          # one RTT measurement per minute
PING_TIMEOUT_S   = 120        # throw away unanswered pings after 2 min

# from awscrt import io
# io.init_logging(io.LogLevel.Trace, 'stderr')     # <— full wire-level trace

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
	"https://fovdashboard.com",
        "https://www.fovdashboard.com",
        "http://fovdashboard.com",
        "https://aviva.fovdashboard.com",
        "https://marvel.fovdashboard.com",
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8000",
        ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def initialize_iot_client_for_endpoint(endpoint: str) -> IOTClient:
    """Create a client bound to a specific IoT endpoint."""
    iot_context = IOTContext()
    client_id = f"FOVDashboardClient-{uuid.uuid4()}"
    print(f"Client ID: {client_id} (endpoint {endpoint})")
    iot_credentials = IOTCredentials(
        cert_path=config.cert_path,
        client_id=client_id,
        endpoint=endpoint,
        priv_key_path=config.private_key_path,
        ca_path=config.root_ca_path
    )
    return IOTClient(iot_context, iot_credentials)

def schedule_notification(device_name: str, device_data: dict, stadium: Optional[str] = None):
    """
    Thread-safe wrapper to schedule async WebSocket notifications from MQTT threads.
    Uses asyncio.run_coroutine_threadsafe to avoid creating new event loops.
    """
    if _main_loop and not _main_loop.is_closed():
        # Schedule coroutine to run in main event loop
        asyncio.run_coroutine_threadsafe(
            WebSocketManager.notify_clients(device_name, device_data, stadium=stadium),
            _main_loop
        )
    else:
        print("WARNING: Main event loop not available, skipping WebSocket notification")

# --- message handler (tag stadium + pass it to WS) ---
def message_handler(topic, payload, *a, **kw):
    try:
        message_str = payload.decode("utf-8", errors="ignore")
        print(f"Received message from topic '{topic}': {message_str}")

        parts = topic.split('/')
        if len(parts) < 4:
            print(f"Unexpected topic format: {topic}")
            return

        # region/stadium/device/metric
        stadium = parts[1]
        device_name = parts[2]
        metric_type = parts[-1]

        # Update device and get latest state (support both update_device signatures)
        try:
            device_data = device_manager.update_device(device_name, metric_type, stadium, message_str)
        except TypeError:
            # older signature: (name, metric, value)
            device_data = device_manager.update_device(device_name, metric_type, message_str)
            device_data["stadium"] = stadium

        # Notify only relevant clients
        schedule_notification(device_name, device_data, stadium=stadium)

    except Exception as e:
        print(f"Error handling message: {str(e)}")
        import traceback
        traceback.print_exc()


# --- latency echo handler (stadium-aware, backward compatible) ---
def latency_echo_handler(topic, payload, *a, **kw):
    try:
        message_str = payload.decode("utf-8", errors="ignore")
        print(f"Received echo from topic '{topic}': {message_str}")

        # Parse payload JSON safely
        try:
            msg = json.loads(message_str)
        except Exception:
            msg = {}

        ping_id = msg.get("ID")

        # Parse topic shapes
        parts = topic.split('/')
        stadium = None
        dev = None

        # Preferred: region/stadium/device/echo
        if len(parts) >= 4:
            stadium = parts[1]
            dev = parts[2]
        # Legacy: esp32/<device>/echo (no stadium)
        elif len(parts) >= 3 and parts[0].lower() == "esp32":
            dev = parts[1]
        # Fallback: payload contains device_id
        else:
            dev = msg.get("device_id", "unknown")

        if not ping_id or ping_id not in _pending_pings:
            print(f"Unknown or stale ping ID: {ping_id}, ignoring")
            return

        rtt_ms = (time.time() - _pending_pings.pop(ping_id)) * 1000.0
        print(f"RTT {dev}: {rtt_ms:.1f} ms")

        # Update device — prefer (name, metric, stadium, value), fall back to (name, metric, value)
        try:
            state = device_manager.update_device(dev, "latency", stadium, f"{rtt_ms:.2f}")
        except TypeError:
            state = device_manager.update_device(dev, "latency", f"{rtt_ms:.2f}")
            if stadium:
                state["stadium"] = stadium

        # Fan-out only to that stadium (admins always receive)
        schedule_notification(dev, state, stadium=stadium)

    except Exception as exc:
        print(f"latency-echo handler failed: {exc}")
        import traceback
        traceback.print_exc()


def start_iot_client():
    """
    Start IoT Clients per unique endpoint, connect, and subscribe to per-stadium topics.
    Also start a ping loop that publishes a latency ping per stadium.
    """
    # Build/Connect one client per unique endpoint
    clients_by_endpoint: dict[str, IOTClient] = {}

    # Keep (client, ping_topic) per stadium for the ping loop
    ping_targets: list[tuple[IOTClient, str]] = []

    for slug, st in STADIUMS.items():
        ep = (st.get("iot_endpoint") or "").strip()
        endpoint = ep if (".iot." in ep and ep.endswith(".amazonaws.com")) else config.endpoint
        if endpoint not in clients_by_endpoint:
            c = initialize_iot_client_for_endpoint(endpoint)
            c.connect()
            clients_by_endpoint[endpoint] = c
        client = clients_by_endpoint[endpoint]

        # Derive base from topic_prefix, default to region/slug/+
        base = st.get("topic_prefix") or f"{st['region']}/{slug}/+"

        # Subscriptions
        client.subscribe(topic=f"{base}/version",       handler=message_handler)
        client.subscribe(topic=f"{base}/battery",       handler=message_handler)
        client.subscribe(topic=f"{base}/temperature",   handler=message_handler)
        client.subscribe(topic=f"{base}/ota",           handler=message_handler)
        client.subscribe(topic=f"{base}/latency/echo",  handler=latency_echo_handler)

        # Ping topic: remove trailing '/+' from base and append /latency/ping
        base_no_plus = base[:-2] if base.endswith("/+") else base
        ping_topic = f"{base_no_plus}/latency/ping"
        ping_targets.append((client, ping_topic))

    # Relay heartbeat — subscribe on every client (cheap & safe)
    for client in clients_by_endpoint.values():
        client.subscribe(topic="fov/relay/+/heartbeat", handler=relay_handler)

    # latency — publish one ping per stadium every minute
    def ping_loop() -> None:
        while True:
            now = time.time()
            ping_id = str(uuid.uuid4())
            payload = json.dumps({"ID": ping_id, "ts": now})
            for client, topic in ping_targets:
                try:
                    client.publish(topic=topic, payload=payload)
                    _pending_pings[ping_id] = now
                except Exception as exc:
                    print(f"latency-ping publish failed to {topic}: {exc}")
            time.sleep(PING_INTERVAL_S)

    Thread(target=ping_loop, name="latency-ping", daemon=True).start()


def relay_handler(topic, payload, *a, **kw):
    rid  = topic.split('/')[2]              # fov/relay/<id>/heartbeat
    pkt  = json.loads(payload.decode())
    relay_manager.upsert(rid, pkt)
    schedule_notification(f"relay:{rid}", relay_manager.relays[rid], stadium=None)

@app.get("/api/status")
async def status():
    """Return system status information for debugging"""
    import psutil
    import os
    
    # Check if certificates exist
    cert_files = {
        "cert_path": os.path.exists(config.cert_path),
        "private_key_path": os.path.exists(config.private_key_path),
        "root_ca_path": os.path.exists(config.root_ca_path)
    }
    
    # Get system information
    mem = psutil.virtual_memory()
    
    return {
        "status": "online",
        "certificates": cert_files,
        "device_count": len(device_manager.devices),
        "websocket_connections": len(WebSocketManager.clients),
        "system": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_used_percent": mem.percent,
            "memory_available_mb": mem.available / (1024 * 1024)
        },
        "server_time": datetime.utcnow().isoformat(),
        "relays": relay_manager.relays,
    }

# --- AUTH: minimal login route (added) ---
class LoginBody(BaseModel):
    username: str   # "admin" or stadium slug, e.g. "aviva"
    password: str

@app.post("/api/login")
async def login(body: LoginBody):
    u = body.username.strip().lower()
    if u == "admin":
        if not verify_admin_password(u, body.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_access_token("admin", "admin")
        return {"token": token, "role": "admin"}
    else:
        if not verify_stadium_password(u, body.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_access_token("stadium", u)
        return {"token": token, "role": "stadium", "stadium": u}

# --- health (public, for UptimeRobot / tests) ---
@app.api_route("/api/health", methods=["GET","HEAD","POST"])
def health():
    return {"status": "ok"}

# --- meta: stadium names for UI labels (NEW, optional) ---
@app.get("/api/meta/stadiums")
def meta_stadiums():
    return {slug: {"name": st.get("name", slug)} for slug, st in STADIUMS.items()}

# --- WebSocket: REQUIRE JWT via ?token=... and filter initial state (changed) ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print("WebSocket connection attempt")

    # Require token in query
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return

    try:
        claims = decode_token(token)
    except Exception as e:
        print("JWT decode failed:", e)
        await websocket.close(code=4401)
        return

    stadium = stadium_from_claims(claims)   # str or None
    admin   = is_admin(claims)              # bool

    try:
        await WebSocketManager.connect(websocket, stadium=stadium, is_admin=admin)

        # Initial device state (filtered)
        if admin:
            initial_devices = device_manager.devices.items()
        else:
            initial_devices = [
                (name, data)
                for name, data in device_manager.devices.items()
                if data.get("stadium") == stadium
            ]
        for device_name, device_data in initial_devices:
            try:
                await websocket.send_json({"topic": device_name, "message": jsonable_encoder(device_data)})
            except Exception as e:
                print(f"Error sending initial device data: {e}")

        # Initial relays (only if you later tag relays with stadium)
        if admin:
            initial_relays = relay_manager.relays.items()
        else:
            initial_relays = [
                (rid, st)
                for rid, st in relay_manager.relays.items()
                if st.get("stadium") == stadium  # works once you add tagging
            ]
        for rid, state in initial_relays:
            try:
                await websocket.send_json({"topic": f"relay:{rid}", "message": jsonable_encoder(state)})
            except Exception as e:
                print(f"Error sending initial relay data: {e}")

        # Keepalive loop (unchanged)
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60)
                await websocket.send_text("pong")
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text("ping")
                except Exception:
                    break
            except Exception as e:
                print(f"WebSocket receive error: {e}")
                break
    except Exception as e:
        print(f"WebSocket connection error: {str(e)}")
    finally:
        await WebSocketManager.disconnect(websocket)
        print("WebSocket connection closed")

# --- Protected REST: filter by stadium (changed) ---
@app.get("/api/devices")
async def get_devices(claims: dict = Depends(get_current_subject)):
    """Get current state, scoped by JWT (admin sees all)."""
    if is_admin(claims):
        return device_manager.devices
    st = stadium_from_claims(claims)
    return {
        name: data
        for name, data in device_manager.devices.items()
        if data.get("stadium") == st
    }

@app.get("/api/relays")
async def get_relays(claims: dict = Depends(get_current_subject)):
    """
    Return the in-memory relay state so the UI can show it
    without waiting for the next heartbeat.
    """
    if is_admin(claims):
        return {
            rid: {
                **st,
                "last_seen": st["last_seen"].isoformat() + "Z" if isinstance(st["last_seen"], datetime) else st["last_seen"]
            }
            for rid, st in relay_manager.relays.items()
        }
    st_slug = stadium_from_claims(claims)
    return {
        rid: {
            **st,
            "last_seen": st["last_seen"].isoformat() + "Z" if isinstance(st["last_seen"], datetime) else st["last_seen"]
        }
        for rid, st in relay_manager.relays.items()
        if st.get("stadium") == st_slug  # will include nothing until you tag relays
    }

@app.get("/api/device/{device_name}/history")
async def get_device_history(
    device_name: str,
    metric_type: Optional[str] = None,
    hours: Optional[int] = 24,
    last_id: Optional[int] = None,
    page_size: int = 50,
    claims: dict = Depends(get_current_subject),   # added
):
    """Get historical logs for a device with pagination"""
    # Authorization guard (prevents cross-stadium access)
    if not is_admin(claims):
        st = stadium_from_claims(claims)
        dev = device_manager.devices.get(device_name)
        if not dev or dev.get("stadium") != st:
            raise HTTPException(status_code=404, detail="Device not found")

    try:
        start_time = datetime.utcnow() - timedelta(hours=hours) if hours else None
        logs, has_more = device_manager.get_device_history(
            device_name,
            metric_type=metric_type,
            start_time=start_time,
            page_size=page_size,
            last_id=last_id
        )
        return {
            "logs": logs,
            "hasMore": has_more,
            "lastId": logs[-1]['id'] if logs else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def check_system_status():
    """Periodic task to update device WiFi status *and* relay liveness"""
    while True:
        # --- devices ---------------------------------------------------
        changed = device_manager.check_wifi_status()
        for name in changed:
            st = device_manager.devices[name].get("stadium")
            await WebSocketManager.notify_clients(name, device_manager.devices[name], stadium=st)

        # --- relays  ----------------------------------------------------
        relay_manager.refresh()
        now = datetime.utcnow()

        for rid, st in relay_manager.relays.items():
            # normalize last_seen (may be ISO string)
            last_seen = st.get("last_seen")
            if isinstance(last_seen, str):
                try:
                    last_seen = datetime.fromisoformat(last_seen.replace("Z", ""))
                except Exception:
                    last_seen = None

            alive = bool(st.get("alive", False))

            # email only when state flips; don't alert on first sighting
            prev = _last_relay_alert_state.get(rid)
            if prev is None:
                _last_relay_alert_state[rid] = alive
            elif prev != alive:
                _last_relay_alert_state[rid] = alive
                if not alive:
                    send_email(
                        subject=f"[FOV] Relay {rid} OFFLINE",
                        body=(
                            f"Relay {rid} has been offline for >{ALERT_GRACE_S}s.\n"
                            f"Last seen: {(last_seen.isoformat() + 'Z') if last_seen else 'unknown'}"
                        )
                    )
                else:
                    send_email(
                        subject=f"[FOV] Relay {rid} RECOVERED",
                        body=f"Relay {rid} heartbeat recovered at {now.isoformat()}Z"
                    )

            # existing WS fan-out (kept)
            if not st.get("_sent") or st["_sent"] != st["alive"]:
                await WebSocketManager.notify_clients(f"relay:{rid}", st, stadium=st.get("stadium"))
                st["_sent"] = st["alive"]


        await asyncio.sleep(30)

@app.on_event("startup")
async def startup_event():
    global _main_loop
    _main_loop = asyncio.get_running_loop()

    # Start IoT clients (per endpoint) in a background thread
    iot_thread = Thread(target=start_iot_client)
    iot_thread.daemon = False   # make it non-daemon so it keeps container alive
    iot_thread.start()

    # Start the device/relay status checker
    asyncio.create_task(check_system_status())

    async def _latency_housekeeping():
        while True:
            cutoff = time.time() - PING_TIMEOUT_S
            old = [k for k, ts in _pending_pings.items() if ts < cutoff]
            for k in old:
                _pending_pings.pop(k, None)
            await asyncio.sleep(PING_TIMEOUT_S)

    asyncio.create_task(_latency_housekeeping())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
