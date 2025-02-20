import asyncio
import random
import time

import aiomqtt

from server.core import KEONN_BROKER_CONF
from server.models import Device, Location, Tag


async def generate_mqtt_events():
    await asyncio.sleep(2)
    send_dev = await Device.first()
    async with aiomqtt.Client(
        **KEONN_BROKER_CONF, identifier=send_dev.meta.id
    ) as client:
        try:
            locations: list[str] = await Location.filter(device=send_dev).values_list(
                "loc", flat=True
            )
            s_locs = random.sample(locations, min(3, len(locations)))
            tags: list[int] = await Tag.filter(last_loc_seen_id__in=s_locs).values_list(
                "id", flat=True
            )
            s_tags = random.sample(tags, 10)
            epcs = await Tag.filter(id__in=s_tags).values_list("epc", flat=True)

            s_locs = [*(loc.split("/", 1)[1] for loc in s_locs), None]
            last_mutation_time = 0

            state = {epc: random.choice(s_locs) for epc in epcs}
            while True:
                if time.time() - last_mutation_time > 10:
                    last_mutation_time = time.time()
                    for epc in random.sample(epcs, 3):
                        state[epc] = random.choice(s_locs)

                message = ""
                for epc in epcs:
                    if not state[epc]:
                        continue
                    rssi = random.randint(-70, -30)
                    message += f"|{epc}:{rssi}@{state[epc]}"
                if message:
                    await client.publish("RFID/devices", send_dev.mac + message)
                await asyncio.sleep(3)
        except asyncio.CancelledError:
            raise asyncio.CancelledError
        except Exception as e:
            print(e)


if __name__ == "__main__":
    asyncio.run(generate_mqtt_events())
