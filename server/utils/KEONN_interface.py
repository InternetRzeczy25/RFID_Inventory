import asyncio
import ipaddress
import json
import pathlib as pl
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from httpx import DigestAuth

from server.core import KEONN_BROKER_CONF
from server.models import device_metadata


def cfg_to_dict(path: pl.Path) -> dict[str, str]:
    with open(path) as jason:
        return json.load(jason)


def xml_request_from_dict(data: dict[str, str]) -> ET.Element:
    req = ET.Element("request")
    for attr in data:
        el = ET.Element(attr)
        el.text = data[attr]
        req.append(el)
    return req


def assemble_mqtt_config(events_dir: pl.Path):
    # https://wiki.keonn.com/software/advannet/services/mqtt-service#h.vtmjyrh1zfu9
    config = []
    for file in events_dir.glob("*.js"):
        with open(file) as js:
            event, topic = file.stem.split("@")
            config.append(
                {
                    "event": event,
                    "topic": f"'RFID/{topic}'",
                    "body": re.sub(r"\s+", " ", js.read().replace('"', "'")),
                }
            )
    return config


CONFIG_DIR = pl.Path(__file__).parent / "device_conf"


def get_mqtt_service_config(broker_config: str | None = None) -> dict[str, str]:
    default_config = cfg_to_dict(CONFIG_DIR / "service.json")

    if broker_config is None:
        host = KEONN_BROKER_CONF["hostname"]
        port = KEONN_BROKER_CONF["port"]
        broker_config = f"tcp://{host}:{port}"

    default_config["broker"] = broker_config

    mqtt_conf = assemble_mqtt_config(CONFIG_DIR / "events")
    default_config["config"] = json.dumps(mqtt_conf)
    return default_config


class API:
    __IP: ipaddress.IPv4Address | ipaddress.IPv6Address
    auth = DigestAuth("admin", "admin")

    def __init__(self, IP: str):
        self.__IP = ipaddress.ip_address(IP)

    async def get(self, path: str, **kwargs):
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    url=f"http://{self.__IP}:3161{path}",
                    auth=kwargs.pop("auth", self.auth),
                    **kwargs,
                )
                res.raise_for_status()
                return res
        except httpx.RequestError as e:
            e.args = (f"{e.request.method} request to {e.request.url.host} failed!",)
            raise e

    async def get_xml(self, path: str, **kwargs):
        res = await self.get(path, **kwargs)
        return ET.fromstring(res.text)

    async def put(self, path: str, data: Any, **kwargs):
        try:
            async with httpx.AsyncClient() as client:
                res = await client.put(
                    url=f"http://{self.__IP}:3161{path}",
                    data=data,
                    auth=kwargs.pop("auth", self.auth),
                    **kwargs,
                )
                res.raise_for_status()
                return res
        except httpx.RequestError as e:
            e.args = (f"{e.request.method} request to {e.request.url.host} failed!",)
            raise e

    async def put_xml(self, path: str, data: ET.Element, **kwargs):
        kwargs["headers"] = kwargs.get("headers", {}).update(
            {"Content-Type": "application/xml"}
        )
        res = await self.put(path, ET.tostring(data), **kwargs)
        return ET.fromstring(res.text)


async def restart_device(device_api: API):
    await device_api.get("/system/runtime/reboot")


async def set_RF(device_api: API, state: bool):
    device_id = (await get_info(device_api)).device_id
    await device_api.get(f"/devices/{device_id}/{'start' if state else 'stop'}")


def __def_to_location(def_: str, mac: str = "") -> tuple[str, str]:
    """transform KEONN definition string to our system location id and antenna name
    def_ format: https://wiki.keonn.com/software/advannet/development/rest-api-development#:~:text=%3C/request%3E-,Explanation,-%3A
    """
    spl = def_.split(",")
    return f"{mac}/{spl[1]}/{spl[2]}/{spl[3]}", spl[5]


async def get_locations(device_api: API):
    root = await device_api.get_xml("/devices")
    device_id = root.find(".//device/id").text
    mac = root.find(".//device/mac").text
    loc_root = await device_api.get_xml(f"/devices/{device_id}/antennas")

    return (
        __def_to_location(d.text, mac)
        for d in loc_root.iterfind(".//data/entries/entry/def")
    )


async def configure_keonn(device_api: API):
    root = await device_api.get_xml("/devices")
    device_id = root.find(".//device/id").text
    active_read_mode = root.find(".//device/activeReadMode").text
    if active_read_mode != "AUTONOMOUS":
        await device_api.put(
            f"/devices/{device_id}/activeDeviceMode", data="Autonomous"
        )
        await device_api.put(f"/devices/{device_id}/activeReadMode", data="AUTONOMOUS")
        mode_conf = cfg_to_dict(CONFIG_DIR / "readmode.json")
        req = xml_request_from_dict(mode_conf)
        await device_api.put_xml(f"/devices/{device_id}/readMode", req)

    mqtt_conf = get_mqtt_service_config()
    mqtt_conf["clientId"] = device_id
    req = xml_request_from_dict(mqtt_conf)
    await asyncio.sleep(0.3)
    await device_api.put_xml("/system/services/byId/MQTTService", req)
    await device_api.get(f"/devices/{device_id}/confSave")
    await device_api.get("/conf/save")


async def get_metadata(device_api: API) -> device_metadata:
    root = await device_api.get_xml("/devices")
    return device_metadata(
        id=root.find(".//device/id").text,
        family=root.find(".//device/id").text,
        serial=root.find(".//device/serial").text,
        code=root.find(".//device/code").text,
        fw_version=root.find(".//device/firmware/version").text
        + "."
        + root.find(".//device/firmware/revision").text,
        rf_module=root.find(".//device/rf-module").text,
    )


@dataclass
class device_info:
    device_id: str
    active_read_mode: str
    status: str
    mac: str


async def get_info(device_api: API) -> device_info:
    root = await device_api.get_xml("/devices")
    return device_info(
        root.find(".//device/id").text,
        root.find(".//device/activeReadMode").text,
        root.find(".//device/status").text,
        root.find(".//device/mac").text,
    )


ms = int
Hz = Literal[1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000]


async def beep(
    device_api: API,
    device_id: str | None = None,
    frequency: Hz = 2000,
    time_on: ms = 100,
    time_off: ms = 50,
    duration: ms = 450,
):
    if device_id is None:
        device_id = (await get_info(device_api)).device_id
    await device_api.get(
        f"/devices/{device_id}/speak/{frequency}/5/{time_on}/{time_off}/{duration}"
    )


async def buzz(
    device_api: API,
    device_id: str | None = None,
    time_on: ms = 300,
    time_off: ms = 0,
    duration: ms = 300,
):
    if device_id is None:
        device_id = (await get_info(device_api)).device_id
    await device_api.get(f"/devices/{device_id}/buzzer/{time_on}/{time_off}/{duration}")


# some models have the speaker builtin and some a buzzer
# so we make sound with both to be sure
async def make_sound(
    device_api: API,
    device_id: str | None = None,
    frequency: Hz = 2000,
    time_on: ms = 100,
    time_off: ms = 50,
    duration: ms = 450,
):
    if device_id is None:
        device_id = (await get_info(device_api)).device_id
    await asyncio.gather(
        beep(device_api, device_id, frequency, time_on, time_off, duration),
        buzz(device_api, device_id, max(time_on, 200), time_off, max(duration, 200)),
    )


if __name__ == "__main__":

    async def main():
        try:
            device_IP = "192.168.0.103"
            api = API(device_IP)
            root = await api.get_xml("/devices")
            device_id = root.find(".//device/id").text
            active_read_mode = root.find(".//device/activeReadMode").text
            print("Device ID:", device_id)
            print("Active Read Mode:", active_read_mode)

            print("Locations:", *(await get_locations(api)))

            # await configure_keonn(api)
            # print("Configuration done")
        except httpx.HTTPStatusError:
            raise ConnectionError

    asyncio.run(main())
