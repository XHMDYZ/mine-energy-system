import json
import time
from datetime import datetime
from pathlib import Path

import pymysql
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


def get_mysql_conn(cfg):
    db_cfg = cfg["mysql"]
    return pymysql.connect(
        host=db_cfg["host"],
        port=db_cfg["port"],
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


def save_raw_data(conn, device_cfg, raw_payload):
    sql = """
    INSERT INTO energy_raw_data (
        device_id, source_type, source_name, node_id,
        voltage_raw, current_raw, power_raw, energy_total_raw,
        collect_time_raw, quality_status, raw_json
    ) VALUES (
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s
    )
    """
    collect_time = raw_payload["collect_time"]
    node_id = device_cfg["node_name"]

    raw_json = json.dumps(raw_payload, ensure_ascii=False)

    with conn.cursor() as cursor:
        cursor.execute(sql, (
            raw_payload["device_id"],
            "opcua",
            "Prosys OPC UA Simulation Server",
            node_id,
            raw_payload["voltage"],
            raw_payload["current"],
            raw_payload["power"],
            raw_payload["energy_total"],
            collect_time,
            "GOOD",
            raw_json
        ))
        return cursor.lastrowid


def save_clean_log(conn, raw_id, device_id, clean_log):
    if isinstance(clean_log, tuple):
        if len(clean_log) > 0 and isinstance(clean_log[0], dict):
            clean_log = clean_log[0]
        else:
            raise ValueError(f"clean_log 类型错误: {type(clean_log)} -> {clean_log}")

    if not isinstance(clean_log, dict):
        raise ValueError(f"clean_log 不是 dict: {type(clean_log)} -> {clean_log}")
    sql = """
    INSERT INTO data_clean_log (
        raw_id, device_id, is_valid, missing_flag, duplicate_flag, outlier_flag,
        unit_normalized, clean_voltage, clean_current, clean_power,
        clean_energy_total, clean_desc
    ) VALUES (
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s
    )
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (
            raw_id,
            device_id,
            clean_log.get("is_valid", 0),
            clean_log.get("missing_flag", 0),
            clean_log.get("duplicate_flag", 0),
            clean_log.get("outlier_flag", 0),
            clean_log.get("unit_normalized", 0),
            clean_log.get("clean_voltage"),
            clean_log.get("clean_current"),
            clean_log.get("clean_power"),
            clean_log.get("clean_energy_total"),
            clean_log.get("clean_desc", "")
        ))


def main():
    cfg = load_config()
    endpoint = cfg["endpoint"]
    backend_url = cfg["backend_url"]
    simulation_root = cfg["simulation_root"]
    devices = cfg["devices"]

    cleaner = DataCleaner()
    client = Client(endpoint)
    conn = None

    try:
        conn = get_mysql_conn(cfg)

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

                collect_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                raw_payload = {
                    "device_id": dev["device_id"],
                    "voltage": safe_float(nodes["voltage"].get_value()),
                    "current": safe_float(nodes["current"].get_value()),
                    "power": safe_float(nodes["power"].get_value()),
                    "energy_total": safe_float(nodes["energy_total"].get_value()),
                    "collect_time": collect_time,
                    "data_source": "opcua"
                }

                print(f"原始数据 [{dev['device_name']}] -> {raw_payload}")

                # 1. 先写原始数据表
                raw_id = save_raw_data(conn, dev, raw_payload)

                # 2. 再做清洗
                is_valid, cleaned_payload, clean_log = cleaner.clean(raw_payload)

                # 3. 写清洗日志表
                save_clean_log(conn, raw_id, dev["device_id"], clean_log)

                if not is_valid:
                    print(f"清洗失败 [{dev['device_name']}] -> {clean_log['clean_desc']}")
                    continue

                print(f"清洗成功 [{dev['device_name']}] -> {cleaned_payload}")

                # 4. 清洗通过后上传后端
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
            if client:
                client.disconnect()
        except Exception:
            pass

        try:
            if conn:
                conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()