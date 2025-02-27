import asyncio
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from server import create_app
from server.core.mqtt import event_sink, monitor_lost, process_kmqtt, process_status


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks: list[asyncio.Task] = []
    tasks.append(asyncio.create_task(process_status()))
    tasks.append(asyncio.create_task(event_sink()))
    tasks.append(asyncio.create_task(process_kmqtt()))
    tasks.append(asyncio.create_task(monitor_lost()))

    yield
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = create_app(lifespan=lifespan)


if __name__ == "__main__":
    import uvicorn

    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(app, host="0.0.0.0", port=5000)
