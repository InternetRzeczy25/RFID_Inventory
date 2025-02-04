import asyncio
import json
import os
import sys

# import uuid
import aiomqtt
from dotenv import load_dotenv

load_dotenv()

# MQTT Connection Details
MQTT_BROKER = "liveobjects.orange-business.com"
MQTT_PORT = 1883
MQTT_USERNAME = "json+device"
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD")
MQTT_TOPIC = "dev/data"

# Payload to send
payload = {
    "streamId": "urn:lo:nsid:rfid:1",
    "location": {"lat": 52.20899, "lon": 20.94641},
    "model": "testMQTTS",
    "value": {
        "testerino": "Po zmianie nazwy, to samo UUID!",
        "status": "online",
        "temperature rise frequency": 10,
        "temp": 17.25,
    },
    "tags": ["City.Warsaw", "Model.testMQTTS"],
}


async def publish():
    async with aiomqtt.Client(
        hostname=MQTT_BROKER,
        port=MQTT_PORT,
        username=MQTT_USERNAME,
        password=MQTT_PASSWORD,
        keepalive=30,
        identifier="6bf9a9b3-75ff-4ddc-b10e-f29eb5f60590",  # str(uuid.uuid4())
    ) as client:
        print("Connected")
        await client.publish(MQTT_TOPIC, json.dumps(payload), qos=1)
        print(f"Published message to {MQTT_TOPIC}")


if __name__ == "__main__":
    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(publish())
