class FOVDashboardConfig:
    def __init__(self):
        # ---------- AWS IoT endpoint + certs ----------
        # Keep the block that matches your provisioned registry/certs.
        self.endpoint: str = "a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com"
        self.cert_path: str = "./certs/sydney/certificate.pem.crt"
        self.private_key_path: str = "./certs/sydney/private.pem.key"
        self.root_ca_path: str = "./certs/sydney/AmazonRootCA1.pem"

        # If you actually use Dublin, swap to these instead: # currently single region only 
        # self.endpoint: str = "a3lkzcadhi1yzr-ats.iot.eu-west-1.amazonaws.com"
        # self.cert_path: str = "./aws-iot-certs/fov-dashboard-dublin-client/certificate.pem.crt"
        # self.private_key_path: str = "./aws-iot-certs/fov-dashboard-dublin-client/private.pem.key"
        # self.root_ca_path: str = "./aws-iot-certs/fov-dashboard-dublin-client/AmazonRootCA1.pem"

        # ---------- Topic filters (match simulator) ----------
        # Simulator publishes: eu-west-1/<stadium>/<device>/{version|temperature|battery|ota}
        self.region_prefix = "eu-west-1"
        self.version_topic: str     = f"{self.region_prefix}/+/+/version"
        self.battery_topic: str     = f"{self.region_prefix}/+/+/battery"
        self.temperature_topic: str = f"{self.region_prefix}/+/+/temperature"
        self.ota_topic: str         = f"{self.region_prefix}/+/+/ota"

        # ---------- Latency ----------
        # Keep your ping publisher as-is (tablets subscribe to this).
        self.latency_ping_topic: str = "marvel_AUS/ai_pub"
        # Echo back following the same region/stadium/device shape:
        self.latency_echo_topic: str = f"{self.region_prefix}/+/+/latency/echo"

        # ---------- Relay ----------
        self.relay_topic: str = "fov/relay/+/heartbeat"
