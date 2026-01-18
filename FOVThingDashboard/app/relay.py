"""
Ultra-light in-memory relay tracker.
No DB – we only need current state for the dashboard.
"""

import os
from datetime import datetime, timedelta


class RelayManager:
    def __init__(self, timeout_s: int | None = None):
        # allow override via env var RELAY_OFFLINE_GRACE_S, default 90s
        self._timeout = timeout_s or int(os.getenv("RELAY_OFFLINE_GRACE_S", "90"))
        self.relays: dict[str, dict] = {}     # relay-id → state dict

    # ---------- update from each heartbeat --------------------------------
    def upsert(self, rid: str, pkt: dict):
        st = self.relays.get(rid, {})
        st.update(pkt)
        st["last_seen"] = datetime.utcnow()
        st["alive"] = True
        self.relays[rid] = st

    # ---------- called periodically to flip 'alive' -----------------------
    def refresh(self):
        cut = datetime.utcnow() - timedelta(seconds=self._timeout)
        for rid, st in self.relays.items():
            last_seen = st.get("last_seen")
            if isinstance(last_seen, str):
                try:
                    last_seen = datetime.fromisoformat(last_seen.replace("Z", ""))
                except Exception:
                    last_seen = None
            st["alive"] = bool(last_seen) and (last_seen > cut)
