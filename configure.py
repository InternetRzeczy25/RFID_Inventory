import requests
from requests.auth import HTTPDigestAuth
import xml.etree.ElementTree as ET
import json
import pathlib as pl
import socket


def assemble_mqtt_config(events_dir: pl.Path):
    config = []
    for file in events_dir.glob("*.js"):
        with open(file) as js:
            config.append(
                {
                    "event": file.stem,
                    "topic": "RFID/devices",
                    "config": js.read().replace("\n", ""),
                }
            )
    return config


def read_config():
    with open(pl.Path(__file__).parent / "KEONN_config.json") as jason:
        default_config = json.load(jason)

        my_IP = socket.gethostbyname(socket.gethostname())
        default_config["broker"] = f"tcp://{my_IP}:1883"

        mqtt_conf = assemble_mqtt_config(pl.Path(__file__).parent / "events")
        default_config["config"] = json.dumps(mqtt_conf)
        return default_config


class XML_API:
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
        return ET.fromstring(res.text)

    def put(self, path: str, data: ET.ElementTree, **kwargs):
        res = requests.put(
            url=f"http://{self.__IP}:3161{path}",
            data=ET.tostring(data),
            auth=kwargs.pop("auth", self.auth),
            headers={"Content-Type": "application/xml"},
            **kwargs,
        )
        if res.status_code != 200:
            raise ConnectionError
        return ET.fromstring(res.text)


def configure_keonn(config: dict, device_api: XML_API):
    # to add: set mode to autonomous
    root = device_api.get("/system/services/byId/MQTTService")
    req = ET.Element("request")
    for child in root.find("data"):
        if child.tag in config:
            child.text = config[child.tag]
        req.append(child)
    device_api.put("/system/services/byId/MQTTService", req)


if __name__ == "__main__":
    try:
        device_IP = "192.168.0.103"
        api = XML_API(device_IP)
        root = api.get("/devices")
        device_id = root.find(".//device/id").text
        active_read_mode = root.find(".//device/activeReadMode").text
        print("Device ID:", device_id)
        print("Active Read Mode:", active_read_mode)

        configure_keonn(read_config(), api)
        print("Configuration done")
    except ConnectionError:
        raise ConnectionError
