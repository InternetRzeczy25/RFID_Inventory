import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from server.mock.mqtt_spam import generate_mqtt_events
from server import create_app
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks: list[asyncio.Task] = []
    tasks.append(asyncio.create_task(process_kmqtt()))
    tasks.append(asyncio.create_task(generate_mqtt_events()))

    yield
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = create_app(lifespan=lifespan)


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.DEBUG)
    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(app, host="0.0.0.0", port=5000)
