import os

LOST_THRESHOLD = 5.0


KEONN_BROKER_CONF = {
    "hostname": os.environ.get("KEONN_MQTT_BROKER_DOMAIN", "127.0.0.1"),
    "port": 1883,
}
