import json
import pathlib as pl
import re
import socket
import xml.etree.ElementTree as ET
from typing import Any

import requests
from requests.auth import HTTPDigestAuth


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


CONFIG_DIR = pl.Path(__file__).parent / "config"


def get_mqtt_service_config() -> dict[str, str]:
    with open(CONFIG_DIR / "service.json") as jason:
        default_config = json.load(jason)

        my_IP = socket.gethostbyname(socket.gethostname())
        default_config["broker"] = f"tcp://{my_IP}:1883"

        mqtt_conf = assemble_mqtt_config(CONFIG_DIR / "events")
        default_config["config"] = json.dumps(mqtt_conf)
        return default_config


class API:
    __IP: str
    auth = HTTPDigestAuth("admin", "admin")

    def __init__(self, IP: str):
        self.__IP = IP

    def get(self, path: str, **kwargs):
        res = requests.get(
            url=f"http://{self.__IP}:3161{path}",
            auth=kwargs.pop("auth", self.auth),
            **kwargs,
        )
        if res.status_code != 200:
            raise ConnectionError
        return res

    def get_xml(self, path: str, **kwargs):
        res = self.get(path, **kwargs)
        return ET.fromstring(res.text)

    def put(self, path: str, data: Any, **kwargs):
        res = requests.put(
            url=f"http://{self.__IP}:3161{path}",
            data=data,
            auth=kwargs.pop("auth", self.auth),
            **kwargs,
        )
        if res.status_code != 200:
            raise ConnectionError
        print(res.text)
        return res

    def put_xml(self, path: str, data: ET.Element, **kwargs):
        kwargs["headers"] = kwargs.get("headers", {}).update(
            {"Content-Type": "application/xml"}
        )
        res = self.put(path, ET.tostring(data), **kwargs)
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


def restart_device(device_api: API):
    device_api.get("/system/runtime/reboot")


def __def_to_location(def_: str, mac: str = "") -> tuple[str, str]:
    """transform KEONN definition string to our system location id and antenna name
    def_ format: https://wiki.keonn.com/software/advannet/development/rest-api-development#:~:text=%3C/request%3E-,Explanation,-%3A
    """
    spl = def_.split(",")
    return f"{mac}/{spl[1]}/{spl[2]}/{spl[3]}", spl[5]


def get_locations(device_api: API):
    root = device_api.get_xml("/devices")
    device_id = root.find(".//device/id").text
    mac = root.find(".//device/mac").text
    loc_root = device_api.get_xml(f"/devices/{device_id}/antennas")

    return (
        __def_to_location(d.text, mac)
        for d in loc_root.iterfind(".//data/entries/entry/def")
    )


def configure_keonn(device_api: API):
    root = device_api.get_xml("/devices")
    device_id = root.find(".//device/id").text
    active_read_mode = root.find(".//device/activeReadMode").text
    if active_read_mode != "AUTONOMOUS":
        device_api.put(f"/devices/{device_id}/activeDeviceMode", data="Autonomous")
        device_api.put(f"/devices/{device_id}/activeReadMode", data="AUTONOMOUS")
        mode_conf = cfg_to_dict(CONFIG_DIR / "readmode.json")
        req = xml_request_from_dict(mode_conf)
        device_api.put_xml(f"/devices/{device_id}/readMode", req)

    mqtt_conf = get_mqtt_service_config()
    mqtt_conf["clientId"] = device_id
    req = xml_request_from_dict(mqtt_conf)
    device_api.put_xml("/system/services/byId/MQTTService", req)


if __name__ == "__main__":
    try:
        device_IP = "192.168.0.103"
        api = API(device_IP)
        root = api.get_xml("/devices")
        device_id = root.find(".//device/id").text
        active_read_mode = root.find(".//device/activeReadMode").text
        print("Device ID:", device_id)
        print("Active Read Mode:", active_read_mode)

        print("Locations:", *get_locations(api))

        # configure_keonn(api)
        # print("Configuration done")
    except ConnectionError:
        raise ConnectionError
