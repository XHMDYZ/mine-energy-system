import json
import time
import os
from datetime import datetime
from pathlib import Path

import pymysql
import requests
from opcua import Client

from data_cleaner import DataCleaner

# ============================================================
# 配置文件路径
# ============================================================
# prosys_opcua_config.json 中保存 OPC UA 服务器地址、后端接口地址、
# 仿真根节点名称、设备节点名称、数据库连接信息和采集周期等配置。
# 这样可以避免把设备节点、数据库地址等信息写死在代码里，
# 后续如果更换服务器地址或增加设备，只需要修改配置文件。
CONFIG_PATH = Path(__file__).parent / "prosys_opcua_config.json"


def load_config():
    """
    读取 OPC UA 采集配置文件。

    返回:
        cfg: dict
            包含 endpoint、backend_url、simulation_root、devices、mysql、
            poll_interval_seconds 等配置内容。

    对应作用:
        为 OPC UA 连接、设备节点定位、MySQL 数据库连接和后端上传提供参数。
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def find_child_by_name(parent, name):
    """
    在 OPC UA 父节点下，根据浏览名称查找子节点。

    参数:
        parent:
            OPC UA 父节点对象。
        name:
            需要查找的子节点浏览名称，例如 Voltage、Current、Power。

    返回:
        child:
            匹配到的 OPC UA 子节点对象。

    说明:
        Prosys OPC UA Simulation Server 中的设备和变量通常以树形节点方式组织。
        采集端需要先找到设备对象，再在设备对象下找到电压、电流、功率、
        累计能耗等变量节点。

    如果没有找到指定节点:
        抛出 ValueError，方便定位配置文件或 Prosys 节点名称是否写错。
    """
    for child in parent.get_children():
        browse_name = child.get_browse_name().Name
        if browse_name == name:
            return child
    raise ValueError(f"未找到子节点: {name}")


def get_device_nodes(client, simulation_root_name, device_node_name):
    """
    获取某一台设备下的电压、电流、功率和累计能耗节点。

    参数:
        client:
            已连接的 OPC UA 客户端。
        simulation_root_name:
            Prosys 仿真服务器中的根节点名称。
        device_node_name:
            设备节点名称，例如 MainHoist、MainFan、DrainagePump 等。

    返回:
        dict:
            {
                "voltage": voltage_node,
                "current": current_node,
                "power": power_node,
                "energy_total": energy_node
            }

    对应论文内容:
        该函数体现了“设备对象—变量节点”的 OPC UA 数据组织方式。
        每台矿山设备被抽象为一个设备对象，设备对象下包含多个变量节点。
    """

    # 获取 OPC UA 标准 Objects 节点。
    objects = client.get_objects_node()

    # 在 Objects 下找到本文仿真环境的根节点。
    simulation_node = find_child_by_name(objects, simulation_root_name)

    # 在仿真根节点下找到具体设备节点。
    device_node = find_child_by_name(simulation_node, device_node_name)

    # 在设备节点下继续查找电压、电流、功率和累计能耗变量。
    voltage_node = find_child_by_name(device_node, "Voltage")
    current_node = find_child_by_name(device_node, "Current")
    power_node = find_child_by_name(device_node, "Power")
    energy_node = find_child_by_name(device_node, "EnergyTotal")

    return {
        "voltage": voltage_node,
        "current": current_node,
        "power": power_node,
        "energy_total": energy_node,
    }


def safe_float(value, default=0.0):
    """
    安全地将 OPC UA 读取值转换为 float。

    参数:
        value:
            OPC UA 节点读取到的原始值。
        default:
            转换失败时使用的默认值。

    返回:
        float:
            转换后的浮点数。

    说明:
        OPC UA 节点可能返回 int、float 或其他类型。
        这里统一转换为 float，避免后续清洗和上传时类型不一致。
        如果转换失败，则返回默认值，后续清洗模块会继续判断其合理性。
    """
    try:
        return float(value)
    except Exception:
        return default


def get_mysql_conn(cfg):
    """
    建立 MySQL 数据库连接。

    参数:
        cfg:
            配置文件中读取到的完整配置字典。

    返回:
        conn:
            pymysql 数据库连接对象。

    说明:
        数据库用户名和密码优先从环境变量 MYSQL_USER、MYSQL_PASSWORD 中读取。
        这样可以避免把本机数据库密码直接写死在代码里，提高安全性。
    """
    db_cfg = cfg["mysql"]
    return pymysql.connect(
        host=db_cfg["host"],
        port=db_cfg["port"],
        user=os.getenv("MYSQL_USER", db_cfg["user"]),
        password=os.getenv("MYSQL_PASSWORD", db_cfg.get("password", "")),
        database=db_cfg["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        # autocommit=True 表示每次执行 INSERT 后自动提交，
        # 适合采集端这种持续写入场景。
        autocommit=True,
    )


def save_raw_data(conn, device_cfg, raw_payload):
    """
    将 OPC UA 采集到的原始数据写入 energy_raw_data 表。

    参数:
        conn:
            MySQL 数据库连接。
        device_cfg:
            当前设备的配置，例如 device_id、device_name、node_name。
        raw_payload:
            采集端刚从 OPC UA 节点读取到的原始数据。

    返回:
        raw_id:
            当前原始数据在 energy_raw_data 表中的主键ID。

    对应论文内容:
        该函数对应“原始数据表”。
        无论后续清洗是否通过，采集到的原始数据都先保存下来，
        用于实现原始数据留痕和后续问题追溯。
    """

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

    # 原始采集时间。
    collect_time = raw_payload["collect_time"]

    # 当前设备对应的 OPC UA 节点名称，用于追溯数据来源。
    node_id = device_cfg["node_name"]

    # 将完整原始数据转成 JSON 字符串保存。
    # 这样即使某些字段后续没有单独建列，也可以从 raw_json 中追溯。
    raw_json = json.dumps(raw_payload, ensure_ascii=False)

    with conn.cursor() as cursor:
        cursor.execute(
            sql,
            (
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
                raw_json,
            ),
        )

        # 返回当前插入原始数据的ID。
        # 后续清洗日志表 data_clean_log 会通过 raw_id 与原始数据关联。
        return cursor.lastrowid


def save_clean_log(conn, raw_id, device_id, clean_log):
    """
    将数据清洗结果写入 data_clean_log 表。

    参数:
        conn:
            MySQL 数据库连接。
        raw_id:
            对应 energy_raw_data 表中的原始数据ID。
        device_id:
            当前设备编号。
        clean_log:
            DataCleaner.clean() 返回的清洗日志字典。

    对应论文内容:
        该函数对应“清洗日志表”。
        它记录每条原始数据是否有效，以及是否存在缺失、重复、异常等问题。
        如果数据被拦截，clean_desc 中会记录具体原因，例如“累计能耗回跳”。
    """

    # 兼容处理：
    # 如果外部错误地传入了 tuple，这里尝试取其中的 dict。
    # 正常情况下 clean_log 应该是一个 dict。
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
        cursor.execute(
            sql,
            (
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
                clean_log.get("clean_desc", ""),
            ),
        )


def main():
    """
    OPC UA 采集端主流程。

    整体流程:
        1. 读取配置文件；
        2. 连接 MySQL 数据库；
        3. 连接 Prosys OPC UA 仿真服务器；
        4. 根据配置找到各设备的变量节点；
        5. 周期性读取设备电压、电流、功率和累计能耗；
        6. 先写入 energy_raw_data 原始数据表；
        7. 调用 DataCleaner 进行数据清洗；
        8. 将清洗结果写入 data_clean_log 清洗日志表；
        9. 清洗通过后，将标准化数据上传到 Go 后端接口；
        10. 后端再写入正式历史数据表，并进行异常检测等处理。

    对应论文主线:
        OPC UA仿真接入 → 原始数据入库 → 数据清洗 → 清洗日志记录
        → 清洗通过数据上传 → 历史数据入库 → 异常检测与前端展示
    """

    # 读取配置文件。
    cfg = load_config()

    # OPC UA服务器地址。
    endpoint = cfg["endpoint"]

    # Go后端接收清洗后数据的接口地址。
    backend_url = cfg["backend_url"]

    # Prosys仿真服务器中的根节点名称。
    simulation_root = cfg["simulation_root"]

    # 设备配置列表，包括设备ID、设备名称、OPC UA节点名称等。
    devices = cfg["devices"]

    # 初始化数据清洗器。
    # 用于关键字段检查、类型转换、范围校验、重复过滤和累计能耗回跳检查。
    cleaner = DataCleaner()

    # 创建 OPC UA 客户端。
    client = Client(endpoint)

    # 数据库连接对象，先置为空，便于 finally 中安全关闭。
    conn = None

    try:
        # 连接 MySQL 数据库。
        conn = get_mysql_conn(cfg)

        # 连接 Prosys OPC UA Simulation Server。
        print(f"正在连接 Prosys OPC UA Server: {endpoint}")
        client.connect()
        print("连接成功")

        # ============================================================
        # 根据配置文件定位每台设备的 OPC UA 变量节点
        # ============================================================
        # device_nodes 保存每台设备的配置和对应的 OPC UA 节点对象。
        # 后续采集时直接从这里读取，不需要每轮循环重新查找节点。
        device_nodes = {}
        for dev in devices:
            device_nodes[dev["node_name"]] = {
                "config": dev,
                "nodes": get_device_nodes(client, simulation_root, dev["node_name"]),
            }

        # ============================================================
        # 持续采集循环
        # ============================================================
        # 采集端会按照 poll_interval_seconds 设置的周期不断读取设备数据。
        # 成果展示时可以说明：该循环模拟了现场采集终端的持续采集过程。
        while True:
            # 遍历每一台配置好的矿山设备。
            for _, item in device_nodes.items():
                dev = item["config"]
                nodes = item["nodes"]

                # 当前采集时间。
                collect_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # ====================================================
                # 1. 从 OPC UA 节点读取原始数据
                # ====================================================
                # 这里分别读取电压、电流、功率和累计能耗。
                # safe_float 用于保证读取结果可以转为浮点数。
                raw_payload = {
                    "device_id": dev["device_id"],
                    "voltage": safe_float(nodes["voltage"].get_value()),
                    "current": safe_float(nodes["current"].get_value()),
                    "power": safe_float(nodes["power"].get_value()),
                    "energy_total": safe_float(nodes["energy_total"].get_value()),
                    "collect_time": collect_time,
                    "data_source": "opcua",
                }

                print(f"原始数据 [{dev['device_name']}] -> {raw_payload}")

                # ====================================================
                # 2. 先写入原始数据表 energy_raw_data
                # ====================================================
                # 注意：这里是不管后续清洗是否通过，都先保存原始数据。
                # 这样可以保证原始采集证据不丢失。
                raw_id = save_raw_data(conn, dev, raw_payload)

                # ====================================================
                # 3. 调用清洗模块进行数据清洗
                # ====================================================
                # clean() 返回：
                #   is_valid：是否清洗通过；
                #   cleaned_payload：清洗后的标准化数据；
                #   clean_log：清洗日志。
                is_valid, cleaned_payload, clean_log = cleaner.clean(raw_payload)

                # ====================================================
                # 4. 写入清洗日志表 data_clean_log
                # ====================================================
                # 无论数据是否有效，都记录清洗日志。
                # 如果数据无效，可以通过 clean_desc 看到具体拦截原因。
                save_clean_log(conn, raw_id, dev["device_id"], clean_log)

                # 如果清洗失败，则不上传后端，也不会进入正式历史数据表。
                if not is_valid:
                    print(
                        f"清洗失败 [{dev['device_name']}] -> {clean_log['clean_desc']}"
                    )
                    continue

                print(f"清洗成功 [{dev['device_name']}] -> {cleaned_payload}")

                # ====================================================
                # 5. 清洗通过后上传 Go 后端接口
                # ====================================================
                # 后端接口负责把有效数据写入 energy_history 表，
                # 并触发后续统计或异常检测逻辑。
                try:
                    response = requests.post(
                        backend_url, json=cleaned_payload, timeout=5
                    )
                    print(f"上传结果 [{dev['device_name']}] -> {response.json()}")
                except Exception as e:
                    # 上传失败时只打印错误，不影响采集端继续运行。
                    # 这样可以避免单次网络或后端异常导致采集程序退出。
                    print(f"上传失败 [{dev['device_name']}] -> {e}")

            # 按配置的采集周期等待，然后进入下一轮采集。
            print(f"等待 {cfg['poll_interval_seconds']} 秒后继续采集...\n")
            time.sleep(cfg["poll_interval_seconds"])

    except Exception as e:
        # 捕获采集端主流程中的异常，方便调试。
        print("采集失败：", e)

    finally:
        # 程序结束前断开 OPC UA 连接。
        try:
            if client:
                client.disconnect()
        except Exception:
            pass

        # 程序结束前关闭数据库连接。
        try:
            if conn:
                conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
"""prosys_collector.py 是采集端主程序。它先连接 Prosys OPC UA 仿真服务器，找到每台设备的 Voltage、Current、Power 和 EnergyTotal 节点，
然后周期性读取数据。采集到的数据不会直接进入历史表，而是先写入 energy_raw_data 原始数据表，再调用 data_cleaner.py 进行清洗，
并把清洗结果写入 data_clean_log 表。只有清洗通过的数据才会上传到 Go 后端，后端再写入正式历史数据表。"""
