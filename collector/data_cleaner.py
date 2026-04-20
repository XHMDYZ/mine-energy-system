from datetime import datetime


class DataCleaner:
    def __init__(self):
        self.last_energy_total = {}
        self.last_signature = set()

    def clean(self, payload):
        """
        输入原始 payload
        输出: (is_valid, cleaned_payload, reason)
        """

        # 1. 关键字段检查
        required_fields = ["device_id", "voltage", "current", "power", "energy_total"]
        for field in required_fields:
            if field not in payload or payload[field] is None:
                return False, None, f"缺少关键字段: {field}"

        # 2. 类型转换
        try:
            cleaned = {
                "device_id": int(payload["device_id"]),
                "voltage": round(float(payload["voltage"]), 2),
                "current": round(float(payload["current"]), 2),
                "power": round(float(payload["power"]), 2),
                "energy_total": round(float(payload["energy_total"]), 2),
                "collect_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            return False, None, f"类型转换失败: {e}"

        # 3. 范围校验
        if cleaned["voltage"] <= 0 or cleaned["voltage"] > 10000:
            return False, None, "电压超出合理范围"
        if cleaned["current"] < 0 or cleaned["current"] > 10000:
            return False, None, "电流超出合理范围"
        if cleaned["power"] < 0 or cleaned["power"] > 100000:
            return False, None, "功率超出合理范围"
        if cleaned["energy_total"] < 0:
            return False, None, "累计能耗不能为负数"

        # 4. 累计能耗回跳检查
        device_id = cleaned["device_id"]
        current_energy = cleaned["energy_total"]
        last_energy = self.last_energy_total.get(device_id)

        if last_energy is not None and current_energy < last_energy:
            return False, None, "累计能耗回跳，判定为异常数据"

        self.last_energy_total[device_id] = current_energy

        # 5. 重复数据过滤
        signature = (
            cleaned["device_id"],
            cleaned["voltage"],
            cleaned["current"],
            cleaned["power"],
            cleaned["energy_total"]
        )

        if signature in self.last_signature:
            return False, None, "检测到重复数据"

        if len(self.last_signature) > 1000:
            self.last_signature.clear()

        self.last_signature.add(signature)

        return True, cleaned, "清洗通过"