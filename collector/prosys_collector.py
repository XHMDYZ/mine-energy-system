import json
import time
from pathlib import Path

import requests
from opcua import Client

from data_cleaner import DataCleaner

CONFIG_PATH = Path(__file__).parent / "prosys_opcua_config.json"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def find_child_by_name(parent, name):
    for child in parent.get_children():
        browse_name = child.get_browse_name().Name
        if browse_name == name:
            return child
    raise ValueError(f"未找到子节点: {name}")


def get_device_nodes(client, simulation_root_name, device_node_name):
    objects = client.get_objects_node()
    simulation_node = find_child_by_name(objects, simulation_root_name)
    device_node = find_child_by_name(simulation_node, device_node_name)

    voltage_node = find_child_by_name(device_node, "Voltage")
    current_node = find_child_by_name(device_node, "Current")
    power_node = find_child_by_name(device_node, "Power")
    energy_node = find_child_by_name(device_node, "EnergyTotal")

    return {
        "voltage": voltage_node,
        "current": current_node,
        "power": power_node,
        "energy_total": energy_node
    }


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def main():
    cfg = load_config()
    endpoint = cfg["endpoint"]
    backend_url = cfg["backend_url"]
    simulation_root = cfg["simulation_root"]
    devices = cfg["devices"]

    cleaner = DataCleaner()
    client = Client(endpoint)

    try:
        print(f"正在连接 Prosys OPC UA Server: {endpoint}")
        client.connect()
        print("连接成功")

        device_nodes = {}
        for dev in devices:
            device_nodes[dev["node_name"]] = {
                "config": dev,
                "nodes": get_device_nodes(client, simulation_root, dev["node_name"])
            }

        while True:
            for _, item in device_nodes.items():
                dev = item["config"]
                nodes = item["nodes"]

                raw_payload = {
                    "device_id": dev["device_id"],
                    "voltage": safe_float(nodes["voltage"].get_value()),
                    "current": safe_float(nodes["current"].get_value()),
                    "power": safe_float(nodes["power"].get_value()),
                    "energy_total": safe_float(nodes["energy_total"].get_value())
                }

                print(f"原始数据 [{dev['device_name']}] -> {raw_payload}")

                is_valid, cleaned_payload, reason = cleaner.clean(raw_payload)

                if not is_valid:
                    print(f"清洗失败 [{dev['device_name']}] -> {reason}")
                    continue

                print(f"清洗成功 [{dev['device_name']}] -> {cleaned_payload}")

                try:
                    response = requests.post(backend_url, json=cleaned_payload, timeout=5)
                    print(f"上传结果 [{dev['device_name']}] -> {response.json()}")
                except Exception as e:
                    print(f"上传失败 [{dev['device_name']}] -> {e}")

            print(f"等待 {cfg['poll_interval_seconds']} 秒后继续采集...\n")
            time.sleep(cfg["poll_interval_seconds"])

    except Exception as e:
        print("采集失败：", e)
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()