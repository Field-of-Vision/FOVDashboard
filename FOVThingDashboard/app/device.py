from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import text  # ✅ added
from database import Device, DeviceLog  # keep this import


class DeviceManager:
    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory
        self.devices: Dict[str, Dict] = {}
        self._load_devices_from_db()

    def _serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        return dt.isoformat() if dt else None

    def _load_devices_from_db(self):
        session = self.session_factory()
        try:
            db_devices = session.query(Device).all()
            for device in db_devices:
                self.devices[device.name] = self._device_to_dict(device)
        finally:
            session.close()

    def _device_to_dict(self, device: "Device") -> Dict:
        latest_values = json.loads(device.last_metric_values) if device.last_metric_values else {}
        return {
            "name": device.name,
            "wifiConnected": device.wifi_connected,
            "batteryCharge": float(latest_values.get("battery", 0)),
            "temperature": float(latest_values.get("temperature", 0)),
            "latencyMs": float(latest_values.get("latency", -1)),
            "firmwareVersion": latest_values.get("version", "N/A"),
            "otaStatus": latest_values.get("ota", "N/A"),
            "lastMessageTime": self._serialize_datetime(device.last_message_time),
            "firstSeen": self._serialize_datetime(device.first_seen),
            # ✅ include stadium for filtering (works even if column missing)
            "stadium": getattr(device, "stadium", None),
        }

    def get_or_create_device(self, name: str) -> "Device":
        session = self.session_factory()
        try:
            device = session.query(Device).filter(Device.name == name).first()
            if not device:
                device = Device(
                    name=name,
                    first_seen=datetime.utcnow(),
                    last_metric_values=json.dumps({})
                )
                session.add(device)
                session.commit()
                self.devices[name] = self._device_to_dict(device)
            return device
        finally:
            session.close()

    # Backward + forward compatible signature:
    # - new style: update_device(name, metric, stadium, value)
    # - old style: update_device(name, metric, value)
    def update_device(
        self,
        name: str,
        metric_type: str,
        stadium_or_value: Optional[str] = None,
        value: Optional[str] = None,
    ) -> Dict:
        if value is None:
            # old call: (name, metric, value)
            stadium = None
            value = stadium_or_value
        else:
            # new call: (name, metric, stadium, value)
            stadium = stadium_or_value

        session = self.session_factory()
        try:
            device = session.query(Device).filter(Device.name == name).first()
            if not device:
                device = Device(name=name, first_seen=datetime.utcnow())
                session.add(device)
                session.flush()

            # ✅ store stadium on the row if provided & column exists
            if stadium and hasattr(device, "stadium") and getattr(device, "stadium") != stadium:
                setattr(device, "stadium", stadium)

            # Log entry
            log = DeviceLog(
                device_id=device.id,
                metric_type=metric_type,
                metric_value=value or "",
                timestamp=datetime.utcnow()
            )
            session.add(log)

            # Update last known state
            current_values = json.loads(device.last_metric_values) if device.last_metric_values else {}
            # Parse JSON metric body if needed
            actual_value = value or ""
            try:
                parsed = json.loads(value) if value else {}
                if metric_type == "battery":
                    actual_value = str(parsed.get("Battery_Percentage", parsed.get("Battery Percentage", 0)))
                elif metric_type == "temperature":
                    actual_value = str(parsed.get("Temperature", 0))
            except json.JSONDecodeError:
                pass

            current_values[metric_type] = actual_value
            device.last_metric_values = json.dumps(current_values)
            device.last_message_time = datetime.utcnow()
            device.wifi_connected = True

            session.commit()

            # Update cache
            device_dict = self._device_to_dict(device)
            self.devices[name] = device_dict
            return device_dict
        finally:
            session.close()

    def get_device_history(
        self,
        device_name: str,
        metric_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page_size: int = 100,
        last_id: Optional[int] = None,
    ) -> Tuple[List[Dict], bool]:
        """
        Fetch history from the normalized SQLite view `device_logs_norm`,
        which exposes: id, ts, device, stadium, metric, value.

        Returns list of dicts with keys: id, ts, metric, value.
        """
        session = self.session_factory()
        try:
            # Build WHERE clauses against the view using device name
            where = ["device = :device"]
            params = {"device": device_name, "limit": page_size}

            if metric_type:
                where.append("metric = :metric")
                params["metric"] = metric_type

            if start_time:
                iso = start_time.isoformat(sep=" ") if hasattr(start_time, "isoformat") else str(start_time)
                where.append("ts >= :start_time")
                params["start_time"] = iso

            if end_time:
                iso = end_time.isoformat(sep=" ") if hasattr(end_time, "isoformat") else str(end_time)
                where.append("ts <= :end_time")
                params["end_time"] = iso

            if last_id:
                where.append("id < :last_id")
                params["last_id"] = last_id

            sql = f"""
                SELECT id, ts, metric, value
                FROM device_logs_norm
                WHERE {' AND '.join(where)}
                ORDER BY id DESC
                LIMIT :limit
            """

            rows = session.execute(text(sql), params).mappings().all()
            has_more = len(rows) == page_size
            return [dict(r) for r in rows], has_more
        finally:
            session.close()

    def check_wifi_status(self):
        session = self.session_factory()
        changed: list[str] = []
        try:
            threshold = datetime.utcnow() - timedelta(seconds=61)
            devices = session.query(Device).all()
            for device in devices:
                was = device.wifi_connected
                is_now = bool(device.last_message_time and device.last_message_time > threshold)
                if was != is_now:
                    device.wifi_connected = is_now
                    if device.name in self.devices:
                        self.devices[device.name]["wifiConnected"] = is_now
                    changed.append(device.name)
            session.commit()
        finally:
            session.close()
        return changed
