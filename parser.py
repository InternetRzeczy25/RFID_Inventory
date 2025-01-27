import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from aiomqtt.client import Client

# sample message content "60:e8:5b:0a:78:5f|e28011700000020f7cbd7358:-39@1/0/0|e28011700000020f7cbd73a7:-39@1/0/0|00000000deadbeef:-31@1/0/0|e28011700000020f7cbd7348:-41@1/0/0|e28011700000020f7cbd73c7:-46@1/0/0"


@dataclass
class ReadEvent:
    tag_id: str
    RSSI: int
    location: str  # 60:e8:5b:0a:78:5f/1/0/0


async def parsed_messages_stream(
    mesidz_stream: Client.MessagesIterator,
) -> AsyncGenerator[ReadEvent, None, None]:
    async for message in mesidz_stream:
        message = message.payload.decode()
        mac, *tags = message.split("|")
        for tag in tags:
            tag_id, RSSI, location = re.split(":|@", tag)
            yield ReadEvent(tag_id, int(RSSI), f"{mac}/{location}")
