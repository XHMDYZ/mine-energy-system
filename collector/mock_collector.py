import time
import random
import requests

URL = "http://127.0.0.1:8080/api/energy/upload"

devices = [
    {"device_id": 1, "base_power": 80},
    {"device_id": 2, "base_power": 120},
    {"device_id": 3, "base_power": 60}
]

energy_total_map = {
    1: 1001.3,
    2: 2000.0,
    3: 500.0
}

while True:
    for d in devices:
        voltage = round(random.uniform(360, 400), 2)
        power = round(d["base_power"] + random.uniform(-10, 10), 2)
#        20% 概率制造异常高功率
        if random.random() < 0.2:
            power = round(power * 3, 2)
        current = round(power / voltage * 100, 2)

        # 模拟累计能耗增长
        energy_total_map[d["device_id"]] += round(power / 100, 2)

        payload = {
            "device_id": d["device_id"],
            "voltage": voltage,
            "current": current,
            "power": power,
            "energy_total": round(energy_total_map[d["device_id"]], 2)
        }

        try:
            response = requests.post(URL, json=payload, timeout=5)
            print("上传成功：", payload)
            print("服务器返回：", response.json())
        except Exception as e:
            print("上传失败：", e)

    print("等待 5 秒后继续...\n")
    time.sleep(5)