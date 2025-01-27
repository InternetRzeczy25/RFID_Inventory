import asyncio
import logging
import os
import ssl
import sys

import aiomqtt

logr = logging.getLogger("RFID_gateway")

MQTT_CONF = {
    "hostname": "127.0.0.1",
    "port": 1883,
    "identifier": "clientId-aJxbSfffPU",
}

LIVE_OBJECTS_CONF = {
    "hostname": "mqtt.liveobjects.orange-business.com",
    "port": 8883,
    "password": os.environ.get("MQTT_PASSWORD"),
    "username": "json+device",
    "keepalive": 29,
    "identifier": "urn:lo:nsid:mqtt:rfid_system",
    "tls_context": ssl.create_default_context(),
}


async def main():
    running = True
    while running:
        try:
            async with (
                # aiomqtt.Client(**MQTT_CONF) as client,
                aiomqtt.Client(**LIVE_OBJECTS_CONF) as notifier,
            ):
                logr.info("Connected to MQTT broker")

                for i in range(100000):
                    await asyncio.sleep(0.5)
                    await notifier.publish("RFID/notifications", f"message {i}")
        except aiomqtt.exceptions.MqttError as e:
            logr.exception(e)
        except Exception as e:
            logr.exception(e)
        except KeyboardInterrupt:
            running = False
        await asyncio.sleep(0.2)


if sys.platform.lower() == "win32" or os.name.lower() == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
asyncio.run(main())
