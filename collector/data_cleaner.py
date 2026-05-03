from datetime import datetime


class DataCleaner:
    def __init__(self):
        self.last_energy_total = {}
        self.last_signature = {}

    def clean(self, payload):
        """
        返回:
        (
            is_valid: bool,
            cleaned_payload: dict | None,
            clean_log: dict
        )
        """

        clean_log = {
            "is_valid": 1,
            "missing_flag": 0,
            "duplicate_flag": 0,
            "outlier_flag": 0,
            "unit_normalized": 1,
            "clean_desc": "清洗通过"
        }

        # 1. 关键字段检查
        required_fields = ["device_id", "voltage", "current", "power", "energy_total"]
        for field in required_fields:
            if field not in payload or payload[field] is None:
                clean_log["is_valid"] = 0
                clean_log["missing_flag"] = 1
                clean_log["clean_desc"] = f"缺少关键字段: {field}"
                return False, None, clean_log

        # 2. 类型转换
        try:
            cleaned = {
                "device_id": int(payload["device_id"]),
                "voltage": round(float(payload["voltage"]), 2),
                "current": round(float(payload["current"]), 2),
                "power": round(float(payload["power"]), 2),
                "energy_total": round(float(payload["energy_total"]), 2),
                "collect_time": payload.get("collect_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_source": payload.get("data_source", "opcua")
            }
        except Exception as e:
            clean_log["is_valid"] = 0
            clean_log["clean_desc"] = f"类型转换失败: {e}"
            return False, None, clean_log

        # 3. 范围校验
        if cleaned["voltage"] <= 0 or cleaned["voltage"] > 10000:
            clean_log["is_valid"] = 0
            clean_log["outlier_flag"] = 1
            clean_log["clean_desc"] = "电压超出合理范围"
            return False, None, clean_log

        if cleaned["current"] < 0 or cleaned["current"] > 10000:
            clean_log["is_valid"] = 0
            clean_log["outlier_flag"] = 1
            clean_log["clean_desc"] = "电流超出合理范围"
            return False, None, clean_log

        if cleaned["power"] < 0 or cleaned["power"] > 100000:
            clean_log["is_valid"] = 0
            clean_log["outlier_flag"] = 1
            clean_log["clean_desc"] = "功率超出合理范围"
            return False, None, clean_log

        if cleaned["energy_total"] < 0:
            clean_log["is_valid"] = 0
            clean_log["outlier_flag"] = 1
            clean_log["clean_desc"] = "累计能耗不能为负数"
            return False, None, clean_log

        # 4. 累计能耗回跳检查
        device_id = cleaned["device_id"]
        current_energy = cleaned["energy_total"]
        last_energy = self.last_energy_total.get(device_id)

        if last_energy is not None and current_energy < last_energy:
            clean_log["is_valid"] = 0
            clean_log["outlier_flag"] = 1
            clean_log["clean_desc"] = "累计能耗回跳，判定为异常数据"
            return False, None, clean_log

        self.last_energy_total[device_id] = current_energy

        # 5. 重复提交过滤（同一设备、同一时刻、同一数值）
        signature = (
            cleaned["voltage"],
            cleaned["current"],
            cleaned["power"],
            cleaned["energy_total"],
            cleaned["collect_time"]
        )

        last_sig = self.last_signature.get(device_id)
        if last_sig == signature:
            clean_log["is_valid"] = 0
            clean_log["duplicate_flag"] = 1
            clean_log["clean_desc"] = "检测到同一采样时刻的重复提交"
            return False, None, clean_log

        self.last_signature[device_id] = signature

        # 6. 清洗结果回填到日志
        clean_log["clean_voltage"] = cleaned["voltage"]
        clean_log["clean_current"] = cleaned["current"]
        clean_log["clean_power"] = cleaned["power"]
        clean_log["clean_energy_total"] = cleaned["energy_total"]

        return True, cleaned, clean_log