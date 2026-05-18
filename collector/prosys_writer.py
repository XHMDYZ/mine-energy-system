import json
import random
import time
from pathlib import Path

from opcua import Client, ua

# ============================================================
# 配置文件路径
# ============================================================
# prosys_opcua_config.json 中保存 OPC UA 服务器地址、仿真根节点名称、
# 设备节点名称、基础电压、基础功率和采集/写入周期等信息。
# 这样设备参数不需要写死在代码中，后续增加设备或调整参数时更方便。
CONFIG_PATH = Path(__file__).parent / "prosys_opcua_config.json"


def load_config():
    """
    读取 OPC UA 仿真写入配置文件。

    返回:
        cfg: dict
            配置文件内容，包括 endpoint、simulation_root、devices、
            poll_interval_seconds 等信息。

    作用:
        为后续连接 OPC UA 服务器、定位设备节点和生成模拟数据提供参数。
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def find_child_by_name(parent, name):
    """
    根据浏览名称在父节点下查找子节点。

    参数:
        parent:
            OPC UA 父节点。
        name:
            要查找的子节点名称，例如 Voltage、Current、Power、EnergyTotal。

    返回:
        child:
            匹配到的 OPC UA 节点对象。

    说明:
        Prosys OPC UA Simulation Server 中的设备和变量以树形结构组织。
        本函数用于在节点树中逐层查找指定设备或变量节点。
    """
    for child in parent.get_children():
        browse_name = child.get_browse_name().Name
        if browse_name == name:
            return child

    # 如果没有找到对应节点，说明配置文件中的节点名称可能与 Prosys 中不一致。
    raise ValueError(f"未找到子节点: {name}")


def get_device_nodes(client, simulation_root_name, device_node_name):
    """
    获取某一台设备下的电压、电流、功率和累计能耗节点。

    参数:
        client:
            已连接的 OPC UA 客户端。
        simulation_root_name:
            Prosys 仿真环境中的根节点名称。
        device_node_name:
            设备节点名称，例如 MainHoist、MainFan、DrainagePump。

    返回:
        dict:
            {
                "voltage": voltage_node,
                "current": current_node,
                "power": power_node,
                "energy_total": energy_node
            }

    对应论文内容:
        这里体现了 OPC UA 中“设备对象—变量节点”的组织方式。
        每台矿山设备都作为一个设备对象，其下挂载电压、电流、功率和累计能耗节点。
    """

    # OPC UA 标准 Objects 节点是业务对象的入口。
    objects = client.get_objects_node()

    # 找到仿真服务器中本文使用的根节点。
    simulation_node = find_child_by_name(objects, simulation_root_name)

    # 在仿真根节点下找到具体设备节点。
    device_node = find_child_by_name(simulation_node, device_node_name)

    # 在设备节点下找到具体变量节点。
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


def write_float(node, value):
    """
    向 OPC UA 变量节点写入浮点数。

    参数:
        node:
            OPC UA 变量节点。
        value:
            要写入的数值。

    说明:
        Prosys OPC UA 节点对数据类型有要求。
        这里使用 ua.Variant 并指定 VariantType.Float，
        可以保证写入值符合 OPC UA 变量节点的数据类型要求。
    """
    node.set_value(ua.Variant(float(value), ua.VariantType.Float))


def main():
    """
    OPC UA 仿真数据写入主流程。

    该脚本的作用:
        1. 连接 Prosys OPC UA Simulation Server；
        2. 找到主提升机、主通风机、排水泵等设备节点；
        3. 周期性生成电压、电流、功率和累计能耗等模拟数据；
        4. 写入 OPC UA 仿真服务器变量节点；
        5. 在指定轮次注入异常数据，用于论文实验验证。

    注入的异常场景:
        1. 主通风机功率超限异常：
            在第 3 到第 5 轮，将主通风机功率写为 220.00 kW，
            用于验证融合异常检测和 LSTM Autoencoder 是否能识别异常窗口。

        2. 排水泵累计能耗回跳异常：
            在第 8 轮，将排水泵累计能耗写成比上一时刻更小的值，
            用于验证 data_cleaner.py 中的累计能耗回跳拦截逻辑。
    """

    # 读取配置文件。
    cfg = load_config()

    # OPC UA 服务器地址。
    endpoint = cfg["endpoint"]

    # Prosys 仿真根节点名称。
    simulation_root = cfg["simulation_root"]

    # 设备列表，包括设备名称、节点名称、基础电压和基础功率等配置。
    devices = cfg["devices"]

    # 创建 OPC UA 客户端。
    client = Client(endpoint)

    try:
        # 连接 Prosys OPC UA 仿真服务器。
        print(f"正在连接 Prosys OPC UA Server: {endpoint}")
        client.connect()
        print("连接成功")

        # ============================================================
        # 初始化设备运行状态
        # ============================================================
        # device_runtime 用来保存每台设备的配置、节点对象和当前累计能耗值。
        # 因为累计能耗需要在每轮写入时持续递增，所以需要在程序中保存状态。
        device_runtime = {}

        for dev in devices:
            # 获取当前设备下的 Voltage、Current、Power、EnergyTotal 节点。
            nodes = get_device_nodes(client, simulation_root, dev["node_name"])

            # 读取节点中已有的累计能耗值，作为本次模拟的起始累计值。
            # 如果不读取初始值，每次重启脚本都从固定值开始，容易造成累计能耗回跳。
            current_total = float(nodes["energy_total"].get_value())
            start_total = round(current_total, 2)

            device_runtime[dev["node_name"]] = {
                "config": dev,
                "nodes": nodes,
                "energy_total": start_total,
            }

            print(f"初始化 [{dev['device_name']}] energy_total = {start_total}")

        # cycle_count 表示当前是第几轮写入。
        # 后面通过轮次控制异常注入时机。
        cycle_count = 0

        # ============================================================
        # 持续写入循环
        # ============================================================
        # 该循环模拟现场设备连续运行，不断产生新的电压、电流、功率和累计能耗。
        while True:
            cycle_count += 1

            # 遍历所有设备，逐台生成并写入数据。
            for _, item in device_runtime.items():
                dev = item["config"]
                nodes = item["nodes"]

                # ====================================================
                # 1. 生成正常运行数据
                # ====================================================
                # 电压围绕基础电压上下波动 10V。
                # 功率围绕基础功率上下波动 10kW。
                # 这种随机波动用于模拟设备正常运行过程中的轻微变化。
                voltage = round(
                    random.uniform(dev["base_voltage"] - 10, dev["base_voltage"] + 10),
                    2,
                )
                power = round(
                    random.uniform(dev["base_power"] - 10, dev["base_power"] + 10), 2
                )

                # ====================================================
                # 2. 注入主通风机功率超限异常
                # ====================================================
                # 在第 3 到第 5 轮，将主通风机功率强制写为 220.00。
                # 该值明显高于主通风机正常功率范围，用于验证：
                #   1. 规则融合异常检测是否能识别功率超限；
                #   2. LSTM Autoencoder 是否能通过重构误差识别异常窗口；
                #   3. 前端报警列表是否能展示异常结果。
                if dev["device_name"] == "主通风机" and 3 <= cycle_count <= 5:
                    voltage = 380.00
                    power = 220.00
                    print(f"*** 注入异常 [{dev['device_name']}]：功率超限测试 ***")

                # ====================================================
                # 3. 根据功率和电压估算电流
                # ====================================================
                # 这里采用简化计算方式：
                # current = power / voltage * 100
                # 目的不是进行严格电气计算，而是生成与功率变化相对应的电流数据，
                # 便于前端展示和深度学习模型使用。
                current = round(power / voltage * 100, 2)

                # ====================================================
                # 4. 正常情况下累计能耗递增
                # ====================================================
                # 累计能耗随功率不断增加。
                # 这里使用 power / 100 作为每轮的递增量，用于模拟设备运行产生的能耗。
                item["energy_total"] = round(item["energy_total"] + power / 100, 2)
                write_energy_total = item["energy_total"]

                # ====================================================
                # 5. 注入排水泵累计能耗回跳异常
                # ====================================================
                # 在第 8 轮，将排水泵累计能耗写成比当前累计值小 30 的值。
                # 正常情况下累计能耗不应该变小，因此该数据会被 data_cleaner.py 拦截。
                #
                # 该异常用于验证论文中的数据清洗拦截实验：
                #   1. 异常数据先进入 energy_raw_data 原始数据表；
                #   2. data_clean_log 表记录“累计能耗回跳”；
                #   3. energy_history 历史表中不会出现该异常值。
                if dev["device_name"] == "排水泵" and cycle_count == 8:
                    write_energy_total = round(item["energy_total"] - 30, 2)
                    print(
                        f"*** 注入异常 [{dev['device_name']}]：累计能耗回跳测试，写入值={write_energy_total} ***"
                    )

                # ====================================================
                # 6. 将数据写入 OPC UA 节点
                # ====================================================
                # 写入后，prosys_collector.py 会从这些节点读取数据，
                # 从而形成“写入模拟数据—采集端读取—平台处理”的完整链路。
                write_float(nodes["voltage"], voltage)
                write_float(nodes["current"], current)
                write_float(nodes["power"], power)
                write_float(nodes["energy_total"], write_energy_total)

                print(
                    f"写入成功 [{dev['device_name']}] -> "
                    f"voltage={voltage}, current={current}, power={power}, energy_total={write_energy_total}"
                )

            # 等待配置文件中设置的采样周期，然后进入下一轮写入。
            # 这里默认和采集端采集周期保持一致，便于观察数据变化。
            print("等待 5 秒后继续写入...\n")
            time.sleep(cfg["poll_interval_seconds"])

    except Exception as e:
        # 捕获主流程异常，方便调试。
        print("写入失败：", e)

    finally:
        # 程序结束时断开 OPC UA 连接。
        try:
            client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
"""prosys_writer.py 是仿真数据写入脚本，用来模拟矿山设备持续运行。
它会周期性向 Prosys OPC UA 仿真服务器中的设备节点写入电压、电流、功率和累计能耗数据。为了验证系统功能，脚本中还设置了两个典型异常：
一个是主通风机功率超限异常，用来验证异常检测和深度学习辅助检测；
另一个是排水泵累计能耗回跳异常，用来验证数据清洗模块能不能在历史入库前拦截错误数据。"""
