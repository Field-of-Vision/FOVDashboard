import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class FOVDashboardConfig:
    def __init__(self):
        # ---------- AWS IoT endpoint + certs ----------
        # Reads from .env with sensible defaults for ap-southeast-2 (Sydney).
        # Per-stadium topic subscriptions are built dynamically in main.py
        # from stadiums_config.py, so no topic fields are needed here.
        self.endpoint: str = os.getenv(
            "IOT_ENDPOINT",
            "a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com",
        )
        self.cert_path: str = os.getenv(
            "IOT_CERT_PATH",
            "./certs/sydney/certificate.pem.crt",
        )
        self.private_key_path: str = os.getenv(
            "IOT_PRIVATE_KEY_PATH",
            "./certs/sydney/private.pem.key",
        )
        self.root_ca_path: str = os.getenv(
            "IOT_ROOT_CA_PATH",
            "./certs/sydney/AmazonRootCA1.pem",
        )

        # ---------- Relay ----------
        self.relay_topic: str = "fov/relay/+/heartbeat"
