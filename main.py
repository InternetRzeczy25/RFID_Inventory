import asyncio

import aiomqtt
import sys
import os
from parser import parsed_messages_stream, ReadEvent
from core import processEvent

KEON_MQTT_CONF = {
    "hostname": "172.26.226.211",
    "port": 1883,
    "identifier": "server",
}

NOTIFIER_MQTT_CONF = {
    "hostname": "172.26.226.211",
    "port": 1883,
    "identifier": "notifier",
}


async def main():
    async with (
        aiomqtt.Client(**KEON_MQTT_CONF) as client,
        aiomqtt.Client(**NOTIFIER_MQTT_CONF) as notifier,
    ):
        await client.subscribe("RFID/devices")

        async def onLocCh(evt: ReadEvent):
            await notifier.publish("RFID/events", f"{evt}")

        async def onPresenceCh(evt: ReadEvent, present: bool):
            await notifier.publish("RFID/events/presence", f"{evt}:{present}")

        async for evt in parsed_messages_stream(client.messages):
            asyncio.ensure_future(processEvent(evt, [onLocCh, onPresenceCh]))


if __name__ == "__main__":
    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
