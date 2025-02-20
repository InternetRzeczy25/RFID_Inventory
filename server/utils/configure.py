import json
import pathlib as pl
import re
import socket
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from httpx import DigestAuth

from server.models import device_metadata


def assemble_mqtt_config(events_dir: pl.Path):
    config = []
    for file in events_dir.glob("*.js"):
        with open(file) as js:
            config.append(
                {
                    "event": file.stem,
                    "topic": "'RFID/devices'",
                    "body": re.sub(r"\s+", " ", js.read().replace('"', "'")),
                }
            )
    return config


CONFIG_DIR = pl.Path(__file__).parent / "device_conf"


def get_mqtt_service_config(broker_ip: str | None = None) -> dict[str, str]:
    with open(CONFIG_DIR / "service.json") as jason:
        default_config = json.load(jason)

        my_ip = socket.gethostbyname(socket.gethostname())
        broker_addr = broker_ip or my_ip

        default_config["broker"] = f"tcp://{broker_addr}:1883"

        mqtt_conf = assemble_mqtt_config(CONFIG_DIR / "events")
        default_config["config"] = json.dumps(mqtt_conf)
        return default_config


class API:
    __IP: str
    auth = DigestAuth("admin", "admin")

    def __init__(self, IP: str):
        self.__IP = IP

    async def get(self, path: str, **kwargs):
        async with httpx.AsyncClient() as client:
            res = await client.get(
                url=f"http://{self.__IP}:3161{path}",
                auth=kwargs.pop("auth", self.auth),
                **kwargs,
            )
            res.raise_for_status()
            return res

    async def get_xml(self, path: str, **kwargs):
        res = await self.get(path, **kwargs)
        return ET.fromstring(res.text)

    async def put(self, path: str, data: Any, **kwargs):
        async with httpx.AsyncClient() as client:
            res = await client.put(
                url=f"http://{self.__IP}:3161{path}",
                data=data,
                auth=kwargs.pop("auth", self.auth),
                **kwargs,
            )
            res.raise_for_status()
            print(res.text)
            return res

    async def put_xml(self, path: str, data: ET.Element, **kwargs):
        kwargs["headers"] = kwargs.get("headers", {}).update(
            {"Content-Type": "application/xml"}
        )
        res = await self.put(path, ET.tostring(data), **kwargs)
        return ET.fromstring(res.text)


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


async def restart_device(device_api: API):
    await device_api.get("/system/runtime/reboot")


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
    await device_api.put_xml("/system/services/byId/MQTTService", req)


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


if __name__ == "__main__":
    import asyncio

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
