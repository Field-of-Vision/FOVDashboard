# aws_iot/IOTClient.py   ← overwrite the file
from __future__ import annotations

import threading
import time
from typing import Callable, Dict

from awscrt import mqtt, exceptions as awscrt_exceptions
from awsiot import mqtt_connection_builder

from aws_iot.IOTContext import IOTContext, IOTCredentials


Handler = Callable[[str, bytes, mqtt.QoS, bool, bool], None]


class IOTClient:
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        context: IOTContext,
        credentials: IOTCredentials,
        ca_bytes: bytes | None = None,
    ) -> None:
        self.context = context
        self.credentials = credentials

        self.connected = False
        self._subs: Dict[str, Handler] = {}           # topic -> handler
        self._reconnect_lock = threading.Lock()

        self._mqtt = mqtt_connection_builder.mtls_from_path(
            endpoint=credentials.endpoint,
            port=credentials.port,
            cert_filepath=credentials.cert_path,
            pri_key_filepath=credentials.priv_key_path,
            ca_filepath=credentials.ca_path,
            ca_bytes=ca_bytes,
            client_bootstrap=context.client_bootstrap,
            on_connection_interrupted=self._on_interrupted,
            on_connection_resumed=self._on_resumed,
            client_id=credentials.client_id,
            clean_session=False,
            keep_alive_secs=30,
        )

    # ------------------------------------------------------------------ #
    def connect(self) -> None:
        print("MQTT connect …")
        self._mqtt.connect().result()
        self.connected = True
        print("… connected")

    def disconnect(self) -> None:
        print("MQTT disconnect …")
        self._mqtt.disconnect().result()
        self.connected = False
        print("… disconnected")

    # ---- publish ------------------------------------------------------ #
    def publish(self, topic: str, payload: str | bytes) -> None:
        if not self.connected:
            print("WARNING: publish skipped - not connected")
            return
        publish_future, packet_id = self._mqtt.publish(topic=topic, payload=payload, qos=mqtt.QoS.AT_MOST_ONCE)
        print(f"Published message: {payload} to topic: {topic} with packet id: {packet_id}")

    # ---- subscribe (fixed) ------------------------------------------- #
    def subscribe(self, topic: str, handler: Handler) -> None:
        """Subscribe and remember the pair for later re‑subscribe."""
        fut, _packet_id = self._mqtt.subscribe(                #  ← unpack
            topic=topic, qos=mqtt.QoS.AT_MOST_ONCE, callback=handler
        )
        fut.result()
        self._subs[topic] = handler
        print(f"Subscribed to: {topic}")

    # ------------------------------------------------------------------ #
    # internal callbacks
    # ------------------------------------------------------------------ #
    def _on_interrupted(self, *args, **kwargs):
        print("MQTT interrupted")
        self.connected = False
        # No manual reconnect – the CRT event-loop handles it automatically.

    def _on_resumed(self, *args, **kwargs):
        # args might be (connection, return_code, session_present)
        # or (return_code, session_present), or come as keywords
        if len(args) >= 3:
            session_present = args[2]
        else:
            session_present = kwargs.get("session_present", False)
        print("MQTT resumed; session_present =", session_present)
        self.connected = True
        if not session_present:
            self._resubscribe_all()

    # ------------------------------------------------------------------ #
    def _resubscribe_all(self) -> None:
        for topic, handler in self._subs.items():
            try:
                fut, _ = self._mqtt.subscribe(                  #  ← unpack
                    topic=topic, qos=mqtt.QoS.AT_MOST_ONCE, callback=handler
                )
                fut.result()
                print(f"Re-subscribed to: {topic}")
            except Exception as exc:
                print(f"Failed to re-subscribe {topic}: {exc}")
