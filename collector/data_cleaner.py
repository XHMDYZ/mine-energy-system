from datetime import datetime


class DataCleaner:
    """
    数据清洗类。

    采集端从 OPC UA 节点读取到原始数据后，不直接写入正式历史数据表，
    而是先调用本类进行字段检查、类型转换、范围校验、累计能耗回跳检查和重复提交过滤。

    clean() 方法会返回三个结果：
    1. is_valid：该条数据是否有效；
    2. cleaned_payload：清洗后的标准化数据；
    3. clean_log：清洗日志，用于写入 data_clean_log 表。
    """

    def __init__(self):
        """
        初始化清洗器。

        last_energy_total:
            用于记录每台设备上一次的累计能耗值。
            正常情况下，累计能耗应该随时间递增或保持不变。
            如果当前累计能耗小于上一时刻的累计能耗，就说明存在“累计能耗回跳”，
            这类数据会被判定为异常采集数据。

        last_signature:
            用于记录每台设备上一条数据的特征签名。
            如果同一设备连续提交了完全相同的采样时间和采样数值，
            则认为该条数据可能是重复上传数据。
        """
        self.last_energy_total = {}
        self.last_signature = {}

    def clean(self, payload):
        """
        对采集端上传的一条原始能耗数据进行清洗。

        参数:
            payload: dict
                采集端上传的原始数据，一般包含：
                device_id       设备编号
                voltage         电压
                current         电流
                power           功率
                energy_total    累计能耗
                collect_time    采集时间
                data_source     数据来源，例如 opcua

        返回:
            (
                is_valid: bool,
                    True 表示数据清洗通过，可以进入后续历史数据表；
                    False 表示数据无效，只记录清洗日志，不进入历史数据表。

                cleaned_payload: dict | None,
                    清洗后的标准化数据。
                    如果数据无效，则返回 None。

                clean_log: dict,
                    清洗日志，记录该条数据是否有效、是否缺失、是否重复、
                    是否异常，以及清洗说明。
            )
        """

        # 默认认为数据有效。
        # 后续如果发现缺失、重复、异常等问题，再修改对应标志位。
        clean_log = {
            "is_valid": 1,  # 是否有效：1表示有效，0表示无效
            "missing_flag": 0,  # 缺失标志：1表示存在关键字段缺失
            "duplicate_flag": 0,  # 重复标志：1表示检测到重复提交
            "outlier_flag": 0,  # 异常标志：1表示存在数值异常或时序异常
            "unit_normalized": 1,  # 单位标准化标志：本文采集端已统一单位，因此默认为1
            "clean_desc": "清洗通过",  # 清洗说明，默认写“清洗通过”
        }

        # ============================================================
        # 1. 关键字段检查
        # ============================================================
        # 能耗数据后续要用于历史趋势、能耗统计、异常检测和深度学习模型输入，
        # 因此必须包含设备编号、电压、电流、功率和累计能耗这几个核心字段。
        # 如果缺少其中任意一个字段，则该条数据不具备后续分析条件。
        required_fields = ["device_id", "voltage", "current", "power", "energy_total"]
        for field in required_fields:
            if field not in payload or payload[field] is None:
                clean_log["is_valid"] = 0
                clean_log["missing_flag"] = 1
                clean_log["clean_desc"] = f"缺少关键字段: {field}"

                # 返回 False，表示该条数据不会进入 energy_history 表，
                # 只会在 data_clean_log 表中留下清洗失败原因。
                return False, None, clean_log

        # ============================================================
        # 2. 类型转换与字段标准化
        # ============================================================
        # OPC UA 或其他采集端上传的数据可能是字符串、整数或浮点数。
        # 为了保证后续数据库写入和计算逻辑稳定，这里统一转换为指定类型。
        # 数值字段保留两位小数，便于展示和后续统计。
        try:
            cleaned = {
                "device_id": int(payload["device_id"]),
                "voltage": round(float(payload["voltage"]), 2),
                "current": round(float(payload["current"]), 2),
                "power": round(float(payload["power"]), 2),
                "energy_total": round(float(payload["energy_total"]), 2),
                # 如果采集端没有传 collect_time，则使用当前系统时间。
                # 这样可以保证每条数据都有时间戳，便于构造时间序列。
                "collect_time": payload.get("collect_time")
                or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                # 如果没有指定数据来源，则默认为 opcua。
                # 后续如果接入其他来源，如智能电表或工业网关，也可以在这里扩展。
                "data_source": payload.get("data_source", "opcua"),
            }
        except Exception as e:
            # 如果类型转换失败，比如功率字段传入了无法转成数字的字符串，
            # 则认为该条数据无效。
            clean_log["is_valid"] = 0
            clean_log["clean_desc"] = f"类型转换失败: {e}"
            return False, None, clean_log

        # ============================================================
        # 3. 数值范围校验
        # ============================================================
        # 这里进行基础的合理性检查，用于拦截明显不符合设备运行规律的异常数据。
        # 这些阈值不是最终报警规则，而是数据质量层面的粗筛。
        # 例如：电压不能为负，功率不能为负，累计能耗不能为负。
        # 如果这类数据进入历史数据表，会影响趋势图、统计分析和异常检测结果。

        # 电压范围校验。
        # 低于等于0或过大的电压值通常说明采集异常或数据解析错误。
        if cleaned["voltage"] <= 0 or cleaned["voltage"] > 10000:
            clean_log["is_valid"] = 0
            clean_log["outlier_flag"] = 1
            clean_log["clean_desc"] = "电压超出合理范围"
            return False, None, clean_log

        # 电流范围校验。
        # 电流允许为0，但不允许为负数，也不允许超过极大值。
        if cleaned["current"] < 0 or cleaned["current"] > 10000:
            clean_log["is_valid"] = 0
            clean_log["outlier_flag"] = 1
            clean_log["clean_desc"] = "电流超出合理范围"
            return False, None, clean_log

        # 功率范围校验。
        # 功率不能为负，过大的功率值通常属于采集异常或仿真数据错误。
        if cleaned["power"] < 0 or cleaned["power"] > 100000:
            clean_log["is_valid"] = 0
            clean_log["outlier_flag"] = 1
            clean_log["clean_desc"] = "功率超出合理范围"
            return False, None, clean_log

        # 累计能耗不能为负。
        # 累计能耗一般表示设备从某一初始时刻到当前时刻的累计用能。
        if cleaned["energy_total"] < 0:
            clean_log["is_valid"] = 0
            clean_log["outlier_flag"] = 1
            clean_log["clean_desc"] = "累计能耗不能为负数"
            return False, None, clean_log

        # ============================================================
        # 4. 累计能耗回跳检查
        # ============================================================
        # 正常情况下，同一设备的累计能耗应该随时间递增或保持不变。
        # 如果当前采集值小于上一条累计能耗值，就说明出现了“累计能耗回跳”。
        # 这通常不是设备运行异常，而是采集质量异常，例如：
        # 1. 传感器或仿真节点值被错误写入；
        # 2. 数据传输发生错乱；
        # 3. 设备计量值被重置但系统未识别。
        #
        # 本文第4章和第6章中的“累计能耗回跳拦截实验”就是通过这里实现的。
        device_id = cleaned["device_id"]
        current_energy = cleaned["energy_total"]
        last_energy = self.last_energy_total.get(device_id)

        if last_energy is not None and current_energy < last_energy:
            clean_log["is_valid"] = 0
            clean_log["outlier_flag"] = 1
            clean_log["clean_desc"] = "累计能耗回跳，判定为异常数据"

            # 该数据会被记录在原始数据表和清洗日志表中，
            # 但不会进入 energy_history 表。
            return False, None, clean_log

        # 如果当前累计能耗正常，则更新该设备的上一时刻累计能耗值。
        self.last_energy_total[device_id] = current_energy

        # ============================================================
        # 5. 重复提交过滤
        # ============================================================
        # 重复提交指同一设备在同一采样时刻上传了完全相同的数据。
        # 这种情况可能来自采集端重试、网络重复请求或程序循环异常。
        # 如果重复数据进入历史表，会影响数据量统计和后续趋势分析。
        #
        # 这里用电压、电流、功率、累计能耗和采集时间组成一个签名。
        # 如果当前签名与该设备上一条签名完全一致，则认为是重复提交。
        signature = (
            cleaned["voltage"],
            cleaned["current"],
            cleaned["power"],
            cleaned["energy_total"],
            cleaned["collect_time"],
        )

        last_sig = self.last_signature.get(device_id)
        if last_sig == signature:
            clean_log["is_valid"] = 0
            clean_log["duplicate_flag"] = 1
            clean_log["clean_desc"] = "检测到同一采样时刻的重复提交"
            return False, None, clean_log

        # 如果不是重复数据，则保存当前签名，供下一次判断使用。
        self.last_signature[device_id] = signature

        # ============================================================
        # 6. 清洗结果写入清洗日志
        # ============================================================
        # 对于清洗通过的数据，把标准化后的电压、电流、功率和累计能耗
        # 回填到 clean_log 中。
        # 这样 data_clean_log 表不仅能记录“是否通过”，
        # 也能保留清洗后的关键数值，方便后续排查和论文实验截图展示。
        clean_log["clean_voltage"] = cleaned["voltage"]
        clean_log["clean_current"] = cleaned["current"]
        clean_log["clean_power"] = cleaned["power"]
        clean_log["clean_energy_total"] = cleaned["energy_total"]

        # 返回清洗成功结果。
        # cleaned 会进入后续正式历史数据表，
        # clean_log 会写入数据清洗日志表。
        return True, cleaned, clean_log
"""data_cleaner.py 是采集端的数据质量控制模块。它不会让原始数据直接进入历史表，
而是先进行关键字段检查、类型转换、范围校验、累计能耗回跳检查和重复数据过滤。清洗通过的数据进入 energy_history 表，
清洗失败的数据只记录在 data_clean_log 表中，这样就实现了论文中的三层数据处理链路。"""
