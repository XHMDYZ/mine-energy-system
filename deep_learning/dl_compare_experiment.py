import json
import os
from pathlib import Path

import joblib
import numpy as np
import pymysql
import torch
import torch.nn as nn

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "model_config.json"
MODEL_DIR = BASE_DIR / "models"


class LSTMAutoencoder(nn.Module):
    def __init__(self, input_size, hidden_size=32, num_layers=1):
        super().__init__()
        self.encoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )
        self.decoder = nn.LSTM(
            input_size=hidden_size,
            hidden_size=input_size,
            num_layers=num_layers,
            batch_first=True,
        )

    def forward(self, x):
        _, (hidden, _) = self.encoder(x)
        repeated = hidden[-1].unsqueeze(1).repeat(1, x.size(1), 1)
        output, _ = self.decoder(repeated)
        return output


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_mysql_conn(cfg):
    db_cfg = cfg["database"]
    password = os.getenv("MYSQL_PASSWORD", db_cfg.get("password", ""))

    return pymysql.connect(
        host=db_cfg["host"],
        port=int(db_cfg["port"]),
        user=db_cfg["user"],
        password=password,
        database=db_cfg["database"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def load_model(device_id):
    model_path = MODEL_DIR / f"lstm_autoencoder_device_{device_id}.pt"
    scaler_path = MODEL_DIR / f"scaler_device_{device_id}.pkl"
    threshold_path = MODEL_DIR / f"threshold_device_{device_id}.json"

    checkpoint = torch.load(model_path, map_location="cpu")
    scaler = joblib.load(scaler_path)

    with open(threshold_path, "r", encoding="utf-8") as f:
        threshold_info = json.load(f)

    model = LSTMAutoencoder(
        input_size=checkpoint["input_size"],
        hidden_size=checkpoint["hidden_size"],
        num_layers=checkpoint["num_layers"],
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    return model, scaler, threshold_info, checkpoint


def get_device_info(conn, device_id):
    sql = """
        SELECT device_id, device_name, rated_power
        FROM device_info
        WHERE device_id = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (device_id,))
        row = cursor.fetchone()

    if not row:
        raise ValueError(f"未找到设备: device_id={device_id}")

    rated_power = float(row.get("rated_power") or 160)
    return row["device_name"], rated_power


def get_baseline_power(conn, device_id, rated_power):
    sql = """
        SELECT power
        FROM energy_history
        WHERE device_id = %s
          AND power IS NOT NULL
          AND power > 0
          AND power < %s
        ORDER BY record_time DESC
        LIMIT 200
    """

    with conn.cursor() as cursor:
        cursor.execute(sql, (device_id, rated_power * 1.2))
        rows = cursor.fetchall()

    powers = [float(row["power"]) for row in rows]

    if len(powers) == 0:
        return rated_power * 0.75

    return float(np.median(powers))


def build_feature_sequence(power_sequence, voltage=380.0):
    """
    根据功率序列构造模型输入特征：
    voltage, current, power
    其中 current 按 power / voltage * 100 近似计算，
    与前面 OPC UA 写入脚本的逻辑保持一致。
    """
    values = []

    for power in power_sequence:
        current = round(power / voltage * 100, 2)
        values.append([voltage, current, power])

    return np.array(values, dtype=np.float32)


def detect_by_lstm(model, scaler, feature_values):
    scaled_values = scaler.transform(feature_values)
    x = torch.tensor(scaled_values[np.newaxis, :, :], dtype=torch.float32)

    with torch.no_grad():
        reconstructed = model(x)
        error = torch.mean((reconstructed - x) ** 2).item()

    return float(error)


def detect_by_rule(power_sequence, rated_power, baseline_power):
    """
    这里实现一个简化版规则融合检测，用于对比实验：
    1. 功率超过额定功率 1.2 倍：记 40 分
    2. 相邻功率变化率超过 50%：记 30 分
    3. 窗口中位功率偏离历史基准 25% 以上：记 30 分

    为了和你系统里的“报警降噪”思想保持一致：
    score >= 40 认为规则融合检测会进入报警；
    score < 40 认为规则侧仅为低风险或未报警。
    """
    score = 0
    reasons = []

    max_power = max(power_sequence)

    if max_power > rated_power * 1.2:
        score += 40
        reasons.append("功率超限")

    max_change_rate = 0.0
    for i in range(1, len(power_sequence)):
        prev = power_sequence[i - 1]
        cur = power_sequence[i]

        if prev > 0:
            rate = abs(cur - prev) / prev
            max_change_rate = max(max_change_rate, rate)

    if max_change_rate > 0.5:
        score += 30
        reasons.append("短时变化率异常")

    median_power = float(np.median(power_sequence))
    if baseline_power > 0:
        deviation_rate = abs(median_power - baseline_power) / baseline_power
    else:
        deviation_rate = 0.0

    if deviation_rate > 0.25:
        score += 30
        reasons.append("历史偏差异常")

    rule_is_anomaly = 1 if score >= 40 else 0

    if rule_is_anomaly:
        result = f"规则报警，score={score}，原因：{'、'.join(reasons)}"
    elif score > 0:
        result = f"低风险异常未报警，score={score}，原因：{'、'.join(reasons)}"
    else:
        result = "规则检测正常"

    return rule_is_anomaly, result, score


def insert_result(
    conn,
    scenario_name,
    device_id,
    power_sequence,
    rule_is_anomaly,
    rule_result,
    dl_error,
    dl_threshold,
    dl_is_anomaly,
    dl_result,
    improvement_desc,
):
    sql = """
        INSERT INTO anomaly_compare_result
        (scenario_name, device_id, power_sequence,
         rule_is_anomaly, rule_result,
         dl_reconstruction_error, dl_threshold_value,
         dl_is_anomaly, dl_result, improvement_desc)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    with conn.cursor() as cursor:
        cursor.execute(
            sql,
            (
                scenario_name,
                device_id,
                ",".join([f"{p:.2f}" for p in power_sequence]),
                rule_is_anomaly,
                rule_result,
                float(dl_error),
                float(dl_threshold),
                dl_is_anomaly,
                dl_result,
                improvement_desc,
            ),
        )


def main():
    cfg = load_config()

    # 本次对比实验选择主通风机 device_id=2
    device_id = 2

    model, scaler, threshold_info, checkpoint = load_model(device_id)
    dl_threshold = float(threshold_info["threshold"])

    conn = get_mysql_conn(cfg)

    try:
        device_name, rated_power = get_device_info(conn, device_id)
        baseline_power = get_baseline_power(conn, device_id, rated_power)

        print(f"实验设备: {device_name}, device_id={device_id}")
        print(f"额定功率: {rated_power:.2f}")
        print(f"历史基准功率: {baseline_power:.2f}")
        print(f"LSTM Autoencoder 阈值: {dl_threshold:.6f}")

        # 清空旧的对比实验结果，避免重复
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM anomaly_compare_result")

        normal = [
            baseline_power * 0.98,
            baseline_power * 1.02,
            baseline_power * 1.00,
            baseline_power * 0.99,
            baseline_power * 1.01,
            baseline_power * 1.00,
            baseline_power * 0.97,
            baseline_power * 1.02,
            baseline_power * 1.01,
            baseline_power * 0.99,
        ]

        over_limit = [
            baseline_power,
            baseline_power * 1.02,
            220.0,
            220.0,
            220.0,
            baseline_power * 1.01,
            baseline_power,
            baseline_power * 0.98,
            baseline_power * 1.00,
            baseline_power * 1.01,
        ]

        # 持续偏高：整体偏离正常水平，但不一定达到严重报警条件
        sustained_high_value = min(rated_power * 1.16, baseline_power * 1.30)
        sustained_high = [
            sustained_high_value * 0.98,
            sustained_high_value * 1.00,
            sustained_high_value * 1.01,
            sustained_high_value * 0.99,
            sustained_high_value * 1.02,
            sustained_high_value * 1.00,
            sustained_high_value * 0.98,
            sustained_high_value * 1.01,
            sustained_high_value * 1.00,
            sustained_high_value * 0.99,
        ]

        # 周期波动：单点未必超限，但窗口模式明显不同于正常平稳波动
        low_value = baseline_power * 0.82
        high_value = min(rated_power * 1.10, baseline_power * 1.28)
        periodic_fluctuation = [
            low_value,
            high_value,
            low_value * 1.02,
            high_value * 0.99,
            low_value,
            high_value,
            low_value * 1.01,
            high_value * 1.00,
            low_value,
            high_value * 0.98,
        ]

        scenarios = [
            ("正常窗口", normal, "作为对照组，规则检测与深度学习检测均应为正常"),
            (
                "明显功率超限异常",
                over_limit,
                "明显异常，规则检测和深度学习检测均可识别",
            ),
            (
                "持续偏高但未明显超限",
                sustained_high,
                "该场景用于体现深度学习对整体窗口偏离的补充识别能力",
            ),
            (
                "周期波动模式异常",
                periodic_fluctuation,
                "该场景用于体现深度学习对窗口波动模式异常的补充识别能力",
            ),
        ]

        for scenario_name, power_sequence, improvement_desc in scenarios:
            feature_values = build_feature_sequence(power_sequence)
            dl_error = detect_by_lstm(model, scaler, feature_values)
            dl_is_anomaly = 1 if dl_error > dl_threshold else 0

            rule_is_anomaly, rule_result, rule_score = detect_by_rule(
                power_sequence,
                rated_power,
                baseline_power,
            )

            dl_result = "深度学习判定异常" if dl_is_anomaly else "深度学习判定正常"

            insert_result(
                conn,
                scenario_name,
                device_id,
                power_sequence,
                rule_is_anomaly,
                rule_result,
                dl_error,
                dl_threshold,
                dl_is_anomaly,
                dl_result,
                improvement_desc,
            )

            print("\n场景:", scenario_name)
            print("功率序列:", ",".join([f"{p:.2f}" for p in power_sequence]))
            print("规则结果:", rule_result)
            print(
                f"深度学习结果: error={dl_error:.6f}, "
                f"threshold={dl_threshold:.6f}, "
                f"is_anomaly={dl_is_anomaly}"
            )
            print("提升说明:", improvement_desc)

        print("\n对比实验完成，结果已写入 anomaly_compare_result 表。")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
