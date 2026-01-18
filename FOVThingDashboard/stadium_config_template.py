# stadiums_config_template.py

STADIUMS = {
    "aviva": {
        "name": "aviva",
        "password": "temp123",  # Plain text for now, hash later
        "region": "eu-west-1",
        "topics": {
            "battery": "eu-west-1/aviva/+/battery",
            "temperature": "eu-west-1/aviva/+/temperature",
            "version": "eu-west-1/aviva/+/version",
            "ota": "eu-west-1/aviva/+/ota"
        },
        "iot_endpoint": "a3lkzcadhi1yzr-ats.iot.eu-west-1.amazonaws.com",
        "cert_path": "./aws-iot-certs/fov-dashboard-dublin-client/certificate.pem.crt",
        "private_key_path": "./aws-iot-certs/fov-dashboard-dublin-client/private.pem.key",
        "root_ca_path": "./aws-iot-certs/fov-dashboard-dublin-client/AmazonRootCA1.pem",
        "latency_ping_topic": "dalymount_IRL/pub"
    },
    "marvel": {
        "name": "Marvel Stadium",
        "password": "temp456",
        "region": "ap-southeast-2",
        "topics": {
            "battery": "ap-southeast-2/marvel/+/battery",
            "temperature": "ap-southeast-2/marvel/+/temperature",
            "version": "ap-southeast-2/marvel/+/version",
            "ota": "ap-southeast-2/marvel/+/ota"
        },
        "iot_endpoint": "a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com",
        "cert_path": "./aws-iot-certs/fov-dashboard-sydney-client/fov-dashboard-client-sydney-1-",
        "private_key_path": "./aws-iot-certs/fov-dashboard-sydney-client/fov-dashboard-client-sydney-1-private.pem.key",
        "root_ca_path": "./aws-iot-certs/fov-dashboard-sydney-client/AmazonRootCA1.pem",
        "latency_ping_topic": "marvel_AUS/ai_pub"
    },
    "kia": {
        "name": "Kia Arena",
        "password": "temp789",
        "region": "ap-southeast-2",
        "topics": {
            "battery": "ap-southeast-2/kia/+/battery",
            "temperature": "ap-southeast-2/kia/+/temperature",
            "version": "ap-southeast-2/kia/+/version",
            "ota": "ap-southeast-2/kia/+/ota"
        },
        "iot_endpoint": "a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com",
        "cert_path": "certificate.pem.crt",
        "private_key_path": "./certs/sydney/private.pem.key",
        "root_ca_path": "./certs/sydney/AmazonRootCA1.pem",
        "latency_ping_topic": "kia_AUS/pub"
    }
}

# Admin account
ADMIN_USERS = {
    "admin": {
        "password": "admin123",  # CHANGE THIS!
        "is_admin": True
    }
}