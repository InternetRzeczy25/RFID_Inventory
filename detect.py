import asyncio
import os
import re
import sys
import time
from copy import deepcopy

from zeroconf import IPVersion
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf


class KeonnFinder:
    TYPE_ = "_workstation._tcp.local."
    __devices = {}

    def __init__(self) -> None:
        self.aiobrowser: AsyncServiceBrowser | None = None
        self.aiozc: AsyncZeroconf | None = None

    async def run_detection(self) -> None:
        self.aiozc = AsyncZeroconf(unicast=True, ip_version=IPVersion.V4Only)
        await self.aiozc.zeroconf.async_wait_for_start()

        def on_service_state_change(*args, **kwargs) -> None:
            """Dummy handler."""

        self.aiobrowser = AsyncServiceBrowser(
            self.aiozc.zeroconf,
            self.TYPE_,
            handlers=[on_service_state_change],
            delay=200,
        )
        await asyncio.sleep(0.5)
        infos: list[AsyncServiceInfo] = []
        for name in self.aiozc.zeroconf.cache.names():
            if not name.endswith(f".{self.TYPE_}"):
                continue
            infos.append(AsyncServiceInfo(self.TYPE_, name))
        tasks = [info.async_request(self.aiozc.zeroconf, 1000) for info in infos]
        await asyncio.gather(*tasks)

        new_devices = {}
        for info in filter(None, infos):
            parsed = re.compile("(?P<name>.*) \\[(?P<mac>.*)\\].*").match(info.name)
            new_devices[parsed["mac"]] = {
                "name": parsed["name"],
                "ip": info.parsed_addresses()[0],
            }
        self.__devices = new_devices
        await self.async_close()

    async def async_close(self) -> None:
        assert self.aiozc is not None
        assert self.aiobrowser is not None
        await self.aiobrowser.async_cancel()
        await self.aiozc.async_close()

    def get_devices(self) -> dict[str, dict[str, str]]:
        return deepcopy(self.__devices)


async def main(kf: KeonnFinder) -> None:
    while True:
        await kf.run_detection()
        print(f"{time.ctime()} | Devices: {kf.get_devices()}")
        await asyncio.sleep(5)


if __name__ == "__main__":
    if sys.platform.lower() == "win32" or os.name.lower() == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    kf = KeonnFinder()
    try:
        loop.run_until_complete(main(kf))
    except KeyboardInterrupt:
        loop.run_until_complete(kf.async_close())
