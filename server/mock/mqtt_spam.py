import asyncio
import random
import time

import aiomqtt

from server.core import KEONN_BROKER_CONF
from server.models import Device, Location, Tag
from server.logging import get_configured_logger

logger = get_configured_logger(__name__, level="DEBUG")


async def generate_mqtt_events():
    while True:
        try:
            await asyncio.sleep(2)
            send_dev = await Device.first()
            async with aiomqtt.Client(
                **KEONN_BROKER_CONF, identifier=send_dev.meta.id
            ) as client:
                logger.info(
                    f"Connected to broker at {KEONN_BROKER_CONF['hostname']} as {send_dev.meta.id}"
                )
                locations: list[str] = await Location.filter(
                    device=send_dev
                ).values_list("loc", flat=True)
                s_locs = random.sample(locations, min(3, len(locations)))
                logger.debug(f"Selected locations: {s_locs}")
                tags: list[int] = await Tag.filter(
                    last_loc_seen_id__in=s_locs
                ).values_list("id", flat=True)
                s_tags = random.sample(tags, 10)
                epcs = await Tag.filter(id__in=s_tags).values_list("epc", flat=True)
                logger.debug(f"Selected tags: {epcs}")

                s_locs = [*(loc.split("/", 1)[1] for loc in s_locs), None]
                last_mutation_time = 0

                state = {epc: random.choice(s_locs) for epc in epcs}
                while True:
                    if time.time() - last_mutation_time > 10:
                        last_mutation_time = time.time()
                        logger.info("\x1b[1;92mMutating tags!\x1b[0m")
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
                        logger.debug(f"Published: {send_dev.mac + message}")
                    await asyncio.sleep(3)
        except asyncio.CancelledError:
            break
        except aiomqtt.MqttError as e:
            logger.error(f"MQTT error: {e}")
        except Exception as e:
            logger.exception(str(e))


if __name__ == "__main__":
    asyncio.run(generate_mqtt_events())
