import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pymysql
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

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
    )


def load_device_data(conn, device_id, features):
    feature_sql = ", ".join(features)

    sql = f"""
    SELECT history_id, record_time, {feature_sql}
    FROM energy_history
    WHERE device_id = %s
    ORDER BY record_time ASC
    """

    df = pd.read_sql(sql, conn, params=[device_id])
    return df


def create_sequences(values, seq_len):
    sequences = []

    for i in range(len(values) - seq_len + 1):
        sequences.append(values[i : i + seq_len])

    return np.array(sequences, dtype=np.float32)


def train_one_device(cfg, device_id):
    model_cfg = cfg["model"]
    features = model_cfg["features"]
    seq_len = int(model_cfg["sequence_length"])
    hidden_size = int(model_cfg["hidden_size"])
    num_layers = int(model_cfg["num_layers"])
    epochs = int(model_cfg["epochs"])
    batch_size = int(model_cfg["batch_size"])
    learning_rate = float(model_cfg["learning_rate"])
    threshold_percentile = float(model_cfg["threshold_percentile"])

    conn = get_mysql_conn(cfg)
    try:
        df = load_device_data(conn, device_id, features)
    finally:
        conn.close()

    if df.empty:
        print(f"[设备 {device_id}] 没有历史数据，跳过训练")
        return

    if len(df) < seq_len + 5:
        print(
            f"[设备 {device_id}] 数据量不足，当前 {len(df)} 条，至少需要 {seq_len + 5} 条"
        )
        return

    df = df.dropna(subset=features).copy()

    # 将特征字段强制转换为数值，无法转换的内容会变成 NaN
    for col in features:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 过滤非数值、空值等异常训练数据
    invalid_df = df[df[features].isna().any(axis=1)]
    if not invalid_df.empty:
        print(
            f"[设备 {device_id}] 发现 {len(invalid_df)} 条非数值或空值数据，已自动跳过"
        )
        print(invalid_df[["history_id", "record_time"] + features].head(10))

    df = df.dropna(subset=features).copy()

    if len(df) < seq_len + 5:
        print(
            f"[设备 {device_id}] 清洗后数据量不足，当前 {len(df)} 条，至少需要 {seq_len + 5} 条"
        )
        return

    values = df[features].astype(float).values

    scaler = StandardScaler()
    scaled_values = scaler.fit_transform(values)

    sequences = create_sequences(scaled_values, seq_len)

    if len(sequences) == 0:
        print(f"[设备 {device_id}] 序列数量为 0，跳过训练")
        return

    x = torch.tensor(sequences, dtype=torch.float32)
    dataset = TensorDataset(x)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = LSTMAutoencoder(
        input_size=len(features),
        hidden_size=hidden_size,
        num_layers=num_layers,
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.MSELoss()

    print(f"\n[设备 {device_id}] 开始训练，样本数={len(sequences)}，使用设备={device}")

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0

        for (batch_x,) in loader:
            batch_x = batch_x.to(device)

            optimizer.zero_grad()
            output = model(batch_x)
            loss = criterion(output, batch_x)
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item() * batch_x.size(0)

        avg_loss = epoch_loss / len(dataset)

        if epoch == 1 or epoch % 10 == 0 or epoch == epochs:
            print(f"[设备 {device_id}] Epoch {epoch:03d}/{epochs}, Loss={avg_loss:.6f}")

    model.eval()
    with torch.no_grad():
        x_device = x.to(device)
        reconstructed = model(x_device)
        errors = torch.mean((reconstructed - x_device) ** 2, dim=(1, 2)).cpu().numpy()

    threshold = float(np.percentile(errors, threshold_percentile))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    model_path = MODEL_DIR / f"lstm_autoencoder_device_{device_id}.pt"
    scaler_path = MODEL_DIR / f"scaler_device_{device_id}.pkl"
    threshold_path = MODEL_DIR / f"threshold_device_{device_id}.json"

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "input_size": len(features),
            "hidden_size": hidden_size,
            "num_layers": num_layers,
            "features": features,
            "sequence_length": seq_len,
        },
        model_path,
    )

    joblib.dump(scaler, scaler_path)

    with open(threshold_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "device_id": device_id,
                "threshold": threshold,
                "threshold_percentile": threshold_percentile,
                "train_sequence_count": int(len(sequences)),
                "train_record_count": int(len(df)),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"[设备 {device_id}] 训练完成")
    print(f"[设备 {device_id}] 阈值={threshold:.6f}")
    print(f"[设备 {device_id}] 模型保存：{model_path}")
    print(f"[设备 {device_id}] 标准化器保存：{scaler_path}")
    print(f"[设备 {device_id}] 阈值文件保存：{threshold_path}")


def main():
    cfg = load_config()

    # 当前系统中已有三台设备：1 主提升机，2 主通风机，3 排水泵
    device_ids = [1, 2, 3]

    for device_id in device_ids:
        train_one_device(cfg, device_id)


if __name__ == "__main__":
    main()
