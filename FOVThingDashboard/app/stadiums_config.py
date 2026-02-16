# stadiums_config.py

# NOTE: Currently using Sydney (ap-southeast-2) certs only.
# To add Dublin (eu-west-1), you'd need separate IoT clients with Dublin certs.
STADIUMS = {
    # "aviva": {
    #     "name": "Aviva Stadium",
    #     "password": "temp123",
    #     "region": "eu-west-1",
    #     "iot_endpoint": "a3lkzcadhi1yzr-ats.iot.eu-west-1.amazonaws.com",
    # },
    "marvel": {
        "name": "Marvel Stadium",
        "password": "temp456",
        "region": "ap-southeast-2",
        "iot_endpoint": "a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com",
        "relay_id": "championdata",
    },
    "kia": {
        "name": "Kia Arena",
        "password": "temp789",
        "region": "ap-southeast-2",
        "iot_endpoint": "a3lkzcadhi1yzr-ats.iot.ap-southeast-2.amazonaws.com",
    },
}

ADMIN_PASSWORD = "admin123"
