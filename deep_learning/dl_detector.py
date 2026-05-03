import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
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


def load_recent_data(conn, device_id, features, seq_len):
    feature_sql = ", ".join(features)

    sql = f"""
        SELECT history_id, record_time, {feature_sql}
        FROM energy_history
        WHERE device_id = %s
        ORDER BY record_time DESC
        LIMIT %s
    """

    with conn.cursor() as cursor:
        cursor.execute(sql, (device_id, seq_len))
        rows = cursor.fetchall()

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df = df.sort_values("record_time").reset_index(drop=True)
    return df


def load_model(device_id):
    model_path = MODEL_DIR / f"lstm_autoencoder_device_{device_id}.pt"
    scaler_path = MODEL_DIR / f"scaler_device_{device_id}.pkl"
    threshold_path = MODEL_DIR / f"threshold_device_{device_id}.json"

    if not model_path.exists():
        raise FileNotFoundError(f"模型文件不存在: {model_path}")

    if not scaler_path.exists():
        raise FileNotFoundError(f"标准化器文件不存在: {scaler_path}")

    if not threshold_path.exists():
        raise FileNotFoundError(f"阈值文件不存在: {threshold_path}")

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


def save_result(
    conn, device_id, window_start_time, window_end_time, error, threshold, is_anomaly
):
    anomaly_desc = (
        "LSTM Autoencoder重构误差超过阈值，判定为异常"
        if is_anomaly
        else "深度学习检测正常"
    )

    sql = """
        INSERT INTO dl_anomaly_record
        (device_id, window_start_time, window_end_time,
         reconstruction_error, threshold_value, is_anomaly, anomaly_desc)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    with conn.cursor() as cursor:
        cursor.execute(
            sql,
            (
                device_id,
                window_start_time,
                window_end_time,
                float(error),
                float(threshold),
                1 if is_anomaly else 0,
                anomaly_desc,
            ),
        )


def detect_one_device(cfg, device_id):
    model, scaler, threshold_info, checkpoint = load_model(device_id)

    features = checkpoint["features"]
    seq_len = int(checkpoint["sequence_length"])
    threshold = float(threshold_info["threshold"])

    conn = get_mysql_conn(cfg)

    try:
        df = load_recent_data(conn, device_id, features, seq_len)

        if df.empty:
            print(f"[设备 {device_id}] 没有历史数据，跳过检测")
            return

        if len(df) < seq_len:
            print(
                f"[设备 {device_id}] 数据量不足，当前 {len(df)} 条，至少需要 {seq_len} 条"
            )
            return

        for col in features:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if df[features].isna().any(axis=1).any():
            print(f"[设备 {device_id}] 最近窗口存在非数值或空值，跳过检测")
            print(df[["history_id", "record_time"] + features])
            return

        values = df[features].astype(float).values
        scaled_values = scaler.transform(values)

        x = torch.tensor(scaled_values[np.newaxis, :, :], dtype=torch.float32)

        with torch.no_grad():
            reconstructed = model(x)
            error = torch.mean((reconstructed - x) ** 2).item()

        is_anomaly = error > threshold

        window_start_time = df["record_time"].iloc[0]
        window_end_time = df["record_time"].iloc[-1]

        save_result(
            conn,
            device_id,
            window_start_time,
            window_end_time,
            error,
            threshold,
            is_anomaly,
        )

        print(
            f"[设备 {device_id}] 检测完成 "
            f"窗口={window_start_time} ~ {window_end_time}, "
            f"error={error:.6f}, threshold={threshold:.6f}, "
            f"is_anomaly={1 if is_anomaly else 0}"
        )

    finally:
        conn.close()


def main():
    cfg = load_config()

    device_ids = [1, 2, 3]

    for device_id in device_ids:
        detect_one_device(cfg, device_id)


if __name__ == "__main__":
    main()
