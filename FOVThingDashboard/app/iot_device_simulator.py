"""
Simulate an FOV Tablet sending messages to AWS IoT Core using the new topic scheme:
  {region}/{stadium}/{device}/{metric}

Examples:
  python iot_device_simulator.py --stadium aviva --region eu-west-1 --device fov-aviva-tablet-test-2
  python iot_device_simulator.py --stadium marvel --region ap-southeast-2 --device fov-marvel-tablet-test-2 --interval 5
"""
import argparse
import json
import random
import time

from aws_iot.IOTClient import IOTClient
from aws_iot.IOTContext import IOTContext, IOTCredentials
from config import FOVDashboardConfig

config = FOVDashboardConfig()

# sensible defaults per stadium
DEFAULT_REGION_BY_STADIUM = {
    "aviva": "eu-west-1",
    "marvel": "ap-southeast-2",
}

def initialize_iot_client(client_id: str = "FOVTablet-Simulator-123") -> IOTClient:
    iot_context = IOTContext()
    iot_credentials = IOTCredentials(
        cert_path=config.cert_path,
        client_id=client_id,
        endpoint=config.endpoint,
        priv_key_path=config.private_key_path,
        ca_path=config.root_ca_path,
    )
    return IOTClient(iot_context, iot_credentials)

def topic(region: str, stadium: str, device: str, metric: str) -> str:
    return f"{region}/{stadium}/{device}/{metric}"

#ex: python iot_device_simulator.py --stadium aviva --region eu-west-1 --device fov-aviva-tablet-test-2
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stadium", choices=["aviva", "marvel"], default="marvel")
    parser.add_argument("--region", help="AWS region for this stadium (defaults based on stadium)")
    parser.add_argument("--device", default=None, help="Device name to simulate")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between telemetry publishes")
    args = parser.parse_args()

    stadium = args.stadium
    region = args.region or DEFAULT_REGION_BY_STADIUM.get(stadium, "eu-west-1")
    # default device name based on stadium if not provided
    device = args.device or (f"fov-{stadium}-tablet-test-2")

    iot_client = initialize_iot_client(client_id=f"FOVTabletSim-{stadium}-{device}-123")


    print(f"Connecting… endpoint={config.endpoint} stadium={stadium} region={region} device={device}")
    iot_client.connect()
    print("Connected.")

    # publish a version once on startup
    iot_client.publish(
        topic=topic(region, stadium, device, "version"),
        payload=json.dumps({"Version": "1.1.0"}),
    )

    while True:
        temperature = round(random.uniform(50, 100), 2)
        battery = random.randint(0, 100)

        iot_client.publish(
            topic=topic(region, stadium, device, "temperature"),
            payload=json.dumps({"Temperature": temperature}),
        )
        iot_client.publish(
            topic=topic(region, stadium, device, "battery"),
            payload=json.dumps({"Battery Percentage": battery}),
        )

        time.sleep(args.interval)

if __name__ == "__main__":
    main()
