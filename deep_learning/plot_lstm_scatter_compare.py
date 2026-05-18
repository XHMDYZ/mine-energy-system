import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pymysql
import torch
import torch.nn as nn
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
CONFIG_PATH = BASE_DIR / "model_config.json"
MODEL_DIR = BASE_DIR / "models"
OUTPUT_DIR = PROJECT_DIR / "figures"
OUTPUT_DIR.mkdir(exist_ok=True)


# 选择主通风机，和前面深度学习实验保持一致
DEVICE_ID = 2

# 滑动窗口长度，需要和训练时保持一致
SEQUENCE_LENGTH = 10

# 读取最近多少条历史数据
LIMIT_ROWS = 900

# 这里是“基础规则候选异常”的宽松阈值
# 目的：把规则方法筛出来的低风险候选点也画出来
# 如果基础点太少，可以适当调小这几个值
RULE_POWER_FACTOR = 1.10  # 功率超过额定功率 1.03 倍，作为候选点
RULE_RATE_THRESHOLD = 0.15  # 窗口内相邻功率变化率超过 8%，作为候选点
RULE_DEVIATION_THRESHOLD = 0.12  # 窗口中位功率偏离历史基准 5%，作为候选点


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
    )


def load_lstm_model(device_id):
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

    threshold = float(threshold_info["threshold"])

    return model, scaler, threshold


def query_device_info(conn, device_id):
    sql = """
        SELECT device_id, device_name, rated_power
        FROM device_info
        WHERE device_id = %s
    """
    with conn.cursor() as cursor:
        cursor.execute(sql, (device_id,))
        row = cursor.fetchone()

    if row is None:
        raise ValueError(f"device_info 中找不到 device_id={device_id}")

    device_name = row["device_name"]
    rated_power = float(row["rated_power"])

    return device_name, rated_power


def query_history_data(conn, device_id):
    sql = """
        SELECT history_id, record_time, voltage, current, power
        FROM energy_history
        WHERE device_id = %s
          AND voltage IS NOT NULL
          AND current IS NOT NULL
          AND power IS NOT NULL
        ORDER BY record_time DESC
        LIMIT %s
    """

    with conn.cursor() as cursor:
        cursor.execute(sql, (device_id, LIMIT_ROWS))
        rows = cursor.fetchall()

    df = pd.DataFrame(rows)

    if df.empty:
        raise ValueError("energy_history 中没有可用数据")

    # 转成时间升序，便于做滑动窗口
    df = df.sort_values("record_time").reset_index(drop=True)

    for col in ["voltage", "current", "power"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["voltage", "current", "power"]).reset_index(drop=True)

    if len(df) < SEQUENCE_LENGTH:
        raise ValueError(f"数据不足，当前 {len(df)} 条，至少需要 {SEQUENCE_LENGTH} 条")

    return df


def calc_reconstruction_error(model, scaler, window_values):
    scaled = scaler.transform(window_values)
    x = torch.tensor(scaled[np.newaxis, :, :], dtype=torch.float32)

    with torch.no_grad():
        reconstructed = model(x)
        error = torch.mean((reconstructed - x) ** 2).item()

    return float(error)


def is_rule_candidate(power_window, rated_power, baseline_power):
    """
    基础规则候选异常：
    这里故意设置得比最终报警规则宽松一点，
    用来表示“基础方法筛出的疑似异常点”。
    """
    power_window = np.array(power_window, dtype=float)

    max_power = np.max(power_window)
    median_power = np.median(power_window)

    # 1. 功率接近或超过额定功率
    power_flag = max_power > rated_power * RULE_POWER_FACTOR

    # 2. 窗口内存在一定变化率
    rate_flag = False
    for i in range(1, len(power_window)):
        prev = power_window[i - 1]
        cur = power_window[i]
        if prev > 0:
            rate = abs(cur - prev) / prev
            if rate > RULE_RATE_THRESHOLD:
                rate_flag = True
                break

    # 3. 窗口整体偏离历史基准
    if baseline_power > 0:
        deviation_rate = abs(median_power - baseline_power) / baseline_power
    else:
        deviation_rate = 0

    deviation_flag = deviation_rate > RULE_DEVIATION_THRESHOLD

    return power_flag or rate_flag or deviation_flag


def build_scatter_data(df, model, scaler, threshold, rated_power):
    baseline_power = float(df["power"].median())

    records = []

    features = ["voltage", "current", "power"]

    for start in range(0, len(df) - SEQUENCE_LENGTH + 1):
        end = start + SEQUENCE_LENGTH

        window = df.iloc[start:end]
        window_values = window[features].astype(float).values
        power_window = window["power"].astype(float).values

        reconstruction_error = calc_reconstruction_error(model, scaler, window_values)

        rule_candidate = is_rule_candidate(
            power_window=power_window,
            rated_power=rated_power,
            baseline_power=baseline_power,
        )

        lstm_confirmed = rule_candidate and (reconstruction_error > threshold)

        records.append(
            {
                "window_id": start + 1,
                "window_end_time": window.iloc[-1]["record_time"],
                "avg_power": float(np.mean(power_window)),
                "max_power": float(np.max(power_window)),
                "reconstruction_error": reconstruction_error,
                "threshold": threshold,
                "rule_candidate": int(rule_candidate),
                "lstm_confirmed": int(lstm_confirmed),
            }
        )

    return pd.DataFrame(records)


def plot_scatter(compare_df, device_name):
    # 设置中文字体
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    # 只画基础规则筛出的候选窗口
    candidate_df = compare_df[compare_df["rule_candidate"] == 1].copy()
    confirmed_df = compare_df[compare_df["lstm_confirmed"] == 1].copy()

    if candidate_df.empty:
        print("没有基础规则候选异常点，请适当调低规则阈值")
        return

    # 用“重构误差 / 阈值”作为纵轴，比直接画误差更直观
    candidate_df["error_ratio"] = (
        candidate_df["reconstruction_error"] / candidate_df["threshold"]
    )

    confirmed_df["error_ratio"] = (
        confirmed_df["reconstruction_error"] / confirmed_df["threshold"]
    )

    before_count = len(candidate_df)
    after_count = len(confirmed_df)

    plt.figure(figsize=(11, 5.8))

    # 基础规则候选点
    plt.scatter(
        candidate_df["window_id"],
        candidate_df["error_ratio"],
        s=26,
        alpha=0.35,
        label=f"基础规则候选异常窗口（{before_count}个）",
    )

    # LSTM辅助确认点
    plt.scatter(
        confirmed_df["window_id"],
        confirmed_df["error_ratio"],
        s=95,
        marker="x",
        linewidths=2.4,
        label=f"LSTM辅助确认异常窗口（{after_count}个）",
    )

    # y=1 表示超过阈值
    plt.axhline(
        y=1,
        linestyle="--",
        linewidth=1.8,
        label="LSTM异常判定边界（重构误差/阈值=1）",
    )

    # 只标注最有代表性的点：误差比最大的前5个 + 最接近阈值的前3个
    top_high = confirmed_df.sort_values("error_ratio", ascending=False).head(5)
    top_near = confirmed_df[confirmed_df["error_ratio"] >= 1].copy()
    top_near["distance_to_threshold"] = top_near["error_ratio"] - 1
    top_near = top_near.sort_values("distance_to_threshold", ascending=True).head(3)

    label_df = pd.concat([top_high, top_near]).drop_duplicates(subset=["window_id"])

    for _, row in label_df.iterrows():
        plt.text(
            row["window_id"],
            row["error_ratio"] + 0.08,
            f"{row['error_ratio']:.2f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    plt.xlabel("滑动窗口序号")
    plt.ylabel("重构误差 / 异常阈值")
    plt.title(f"{device_name}规则候选窗口与LSTM辅助确认结果对比")
    plt.grid(True, linestyle="--", alpha=0.35)
    plt.legend()
    plt.tight_layout()

    output_path = OUTPUT_DIR / "rule_lstm_error_ratio_scatter.png"
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"散点图已生成：{output_path}")


def main():
    cfg = load_config()
    conn = get_mysql_conn(cfg)

    try:
        device_name, rated_power = query_device_info(conn, DEVICE_ID)
        df = query_history_data(conn, DEVICE_ID)
        model, scaler, threshold = load_lstm_model(DEVICE_ID)

        compare_df = build_scatter_data(
            df=df,
            model=model,
            scaler=scaler,
            threshold=threshold,
            rated_power=rated_power,
        )

        output_csv = OUTPUT_DIR / "rule_lstm_scatter_compare_data.csv"
        compare_df.to_csv(output_csv, index=False, encoding="utf-8-sig")

        before_count = int(compare_df["rule_candidate"].sum())
        after_count = int(compare_df["lstm_confirmed"].sum())

        print(f"设备：{device_name}")
        print(f"历史数据条数：{len(df)}")
        print(f"滑动窗口数量：{len(compare_df)}")
        print(f"基础规则候选异常点数量：{before_count}")
        print(f"LSTM辅助确认异常点数量：{after_count}")
        print(f"重构误差阈值：{threshold:.6f}")
        print(f"绘图数据已保存：{output_csv}")

        plot_scatter(compare_df, device_name)

        print("\n提示：")
        print(
            "如果基础规则候选异常点太少，可以适当调小 RULE_POWER_FACTOR、RULE_RATE_THRESHOLD 或 RULE_DEVIATION_THRESHOLD。"
        )
        print(
            "如果 LSTM 辅助确认点太少或为 0，说明当前历史数据中超过重构误差阈值的异常窗口较少，可以结合前面的异常注入实验一起说明。"
        )

    finally:
        conn.close()


if __name__ == "__main__":
    main()
