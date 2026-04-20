import json
import random
import time
from pathlib import Path

from opcua import Client, ua

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


def write_float(node, value):
    node.set_value(ua.Variant(float(value), ua.VariantType.Float))


def main():
    cfg = load_config()
    endpoint = cfg["endpoint"]
    simulation_root = cfg["simulation_root"]
    devices = cfg["devices"]

    client = Client(endpoint)

    try:
        print(f"正在连接 Prosys OPC UA Server: {endpoint}")
        client.connect()
        print("连接成功")

        device_runtime = {}

        for dev in devices:
            nodes = get_device_nodes(client, simulation_root, dev["node_name"])
            device_runtime[dev["node_name"]] = {
                "config": dev,
                "nodes": nodes,
                "energy_total": dev["base_energy_total"]
            }

        while True:
            for _, item in device_runtime.items():
                dev = item["config"]
                nodes = item["nodes"]

                voltage = round(random.uniform(dev["base_voltage"] - 10, dev["base_voltage"] + 10), 2)
                power = round(random.uniform(dev["base_power"] - 10, dev["base_power"] + 10), 2)

                # 偶尔制造异常峰值，便于后续报警实验
                if random.random() < 0.1:
                    power = round(power * random.uniform(2.0, 3.0), 2)

                current = round(power / voltage * 100, 2)
                item["energy_total"] = round(item["energy_total"] + power / 100, 2)

                write_float(nodes["voltage"], voltage)
                write_float(nodes["current"], current)
                write_float(nodes["power"], power)
                write_float(nodes["energy_total"], item["energy_total"])

                print(
                    f"写入成功 [{dev['device_name']}] -> "
                    f"voltage={voltage}, current={current}, power={power}, energy_total={item['energy_total']}"
                )

            print("等待 5 秒后继续写入...\n")
            time.sleep(cfg["poll_interval_seconds"])

    except Exception as e:
        print("写入失败：", e)
    finally:
        try:
            client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()