import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pymysql
import torch
import torch.nn as nn

# ============================================================
# 基础路径配置
# ============================================================
# BASE_DIR 表示当前 deep_learning 目录。
BASE_DIR = Path(__file__).resolve().parent

# 深度学习模块配置文件。
# model_config.json 中保存数据库连接信息以及部分模型配置。
CONFIG_PATH = BASE_DIR / "model_config.json"

# 模型文件保存目录。
# 训练脚本 train_lstm_autoencoder.py 会把模型、标准化器和阈值文件保存到这里。
MODEL_DIR = BASE_DIR / "models"


class LSTMAutoencoder(nn.Module):
    """
    LSTM Autoencoder 模型结构。

    注意：
        这里的模型结构必须和 train_lstm_autoencoder.py 中训练时的结构保持一致。
        检测阶段会先读取模型文件中的 input_size、hidden_size、num_layers 等参数，
        再重新构建同样结构的模型，并加载训练好的参数。

    作用：
        对输入的时间序列窗口进行重构。
        如果当前窗口符合历史正常运行模式，重构误差通常较小；
        如果当前窗口偏离正常模式，重构误差通常较大。
    """

    def __init__(self, input_size, hidden_size=32, num_layers=1):
        """
        初始化 LSTM Autoencoder。

        参数:
            input_size:
                输入特征数量，例如 voltage、current、power 共3个特征。
            hidden_size:
                LSTM隐藏层维度。
            num_layers:
                LSTM层数。
        """
        super().__init__()

        # 编码器：把输入时间窗口压缩成隐藏状态。
        self.encoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )

        # 解码器：根据隐藏状态重构原始时间窗口。
        self.decoder = nn.LSTM(
            input_size=hidden_size,
            hidden_size=input_size,
            num_layers=num_layers,
            batch_first=True,
        )

    def forward(self, x):
        """
        前向传播。

        参数:
            x:
                输入窗口，形状为：
                batch_size × sequence_length × input_size

        返回:
            output:
                重构后的窗口，形状与输入 x 保持一致。
        """

        # encoder 读取输入序列，得到最后时刻隐藏状态。
        _, (hidden, _) = self.encoder(x)

        # 将最后一层隐藏状态复制 sequence_length 次，
        # 作为 decoder 在每个时间步上的输入。
        repeated = hidden[-1].unsqueeze(1).repeat(1, x.size(1), 1)

        # decoder 输出重构序列。
        output, _ = self.decoder(repeated)

        return output


def load_config():
    """
    读取深度学习模块配置文件。

    返回:
        cfg: dict
            包含数据库连接参数等信息。
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_mysql_conn(cfg):
    """
    创建 MySQL 数据库连接。

    参数:
        cfg:
            model_config.json 中读取到的配置字典。

    返回:
        pymysql 数据库连接对象。

    说明:
        数据库密码优先从环境变量 MYSQL_PASSWORD 中读取，
        避免把真实密码直接写入代码。
    """
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
        # 检测结果写入 dl_anomaly_record 表时自动提交。
        autocommit=True,
    )


def load_recent_data(conn, device_id, features, seq_len):
    """
    从 energy_history 表中读取指定设备最近 seq_len 条历史数据。

    参数:
        conn:
            MySQL 数据库连接。
        device_id:
            设备编号。
        features:
            模型输入特征列表，例如 ["voltage", "current", "power"]。
        seq_len:
            模型需要的时间窗口长度，例如10。

    返回:
        df: pandas.DataFrame
            最近一个时间窗口的数据，按 record_time 升序排列。

    说明:
        SQL 查询时先按时间倒序取最近 seq_len 条，
        取出后再按时间升序排列。
        这样既能保证拿到最新窗口，又能保证 LSTM 输入顺序是从早到晚。
    """

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

    # 将最近窗口重新按时间升序排列，保证时间序列顺序正确。
    df = df.sort_values("record_time").reset_index(drop=True)
    return df


def load_model(device_id):
    """
    加载指定设备训练好的模型、标准化器和阈值文件。

    参数:
        device_id:
            设备编号。

    返回:
        model:
            已加载参数并设置为 eval 模式的 LSTM Autoencoder。
        scaler:
            训练阶段保存的 StandardScaler，用于检测阶段数据标准化。
        threshold_info:
            阈值文件中的信息，包括 threshold、训练样本数量等。
        checkpoint:
            模型文件中的结构参数和输入特征信息。

    说明:
        每台设备的运行模式不同，因此本文为每台设备分别训练一个模型。
        文件命名中包含 device_id，用于区分不同设备模型。
    """

    model_path = MODEL_DIR / f"lstm_autoencoder_device_{device_id}.pt"
    scaler_path = MODEL_DIR / f"scaler_device_{device_id}.pkl"
    threshold_path = MODEL_DIR / f"threshold_device_{device_id}.json"

    # 检查模型、标准化器和阈值文件是否存在。
    # 如果缺失，说明该设备还没有完成训练。
    if not model_path.exists():
        raise FileNotFoundError(f"模型文件不存在: {model_path}")

    if not scaler_path.exists():
        raise FileNotFoundError(f"标准化器文件不存在: {scaler_path}")

    if not threshold_path.exists():
        raise FileNotFoundError(f"阈值文件不存在: {threshold_path}")

    # 加载 PyTorch 模型检查点。
    checkpoint = torch.load(model_path, map_location="cpu")

    # 加载训练阶段保存的标准化器。
    scaler = joblib.load(scaler_path)

    # 加载异常阈值。
    with open(threshold_path, "r", encoding="utf-8") as f:
        threshold_info = json.load(f)

    # 根据训练时保存的结构参数重新构造模型。
    model = LSTMAutoencoder(
        input_size=checkpoint["input_size"],
        hidden_size=checkpoint["hidden_size"],
        num_layers=checkpoint["num_layers"],
    )

    # 加载训练好的模型参数。
    model.load_state_dict(checkpoint["model_state_dict"])

    # 设置为评估模式，关闭训练状态。
    model.eval()

    return model, scaler, threshold_info, checkpoint


def save_result(
    conn, device_id, window_start_time, window_end_time, error, threshold, is_anomaly
):
    """
    将深度学习检测结果写入 dl_anomaly_record 表。

    参数:
        conn:
            MySQL 数据库连接。
        device_id:
            设备编号。
        window_start_time:
            当前检测窗口开始时间。
        window_end_time:
            当前检测窗口结束时间。
        error:
            LSTM Autoencoder 计算得到的重构误差。
        threshold:
            该设备对应的异常阈值。
        is_anomaly:
            是否判定为异常。

    对应论文内容:
        dl_anomaly_record 表用于保存深度学习辅助检测结果，
        包括窗口时间、重构误差、阈值、是否异常和异常说明。
    """

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
    """
    对单台设备执行一次深度学习辅助异常检测。

    参数:
        cfg:
            配置文件内容。
        device_id:
            设备编号。

    检测流程:
        1. 加载该设备训练好的模型、标准化器和阈值；
        2. 从 energy_history 表读取最近一个时间窗口；
        3. 检查窗口数据是否完整且可转成数值；
        4. 使用训练阶段保存的标准化器对窗口数据进行标准化；
        5. 输入 LSTM Autoencoder 进行重构；
        6. 计算输入窗口与重构窗口之间的均方误差；
        7. 将重构误差与阈值比较；
        8. 将检测结果写入 dl_anomaly_record 表。
    """

    # 加载模型、标准化器、阈值和模型配置。
    model, scaler, threshold_info, checkpoint = load_model(device_id)

    # 获取训练阶段使用的输入特征和窗口长度。
    features = checkpoint["features"]
    seq_len = int(checkpoint["sequence_length"])

    # 读取该设备异常阈值。
    threshold = float(threshold_info["threshold"])

    # 连接数据库。
    conn = get_mysql_conn(cfg)

    try:
        # 读取最近 seq_len 条历史数据，作为当前检测窗口。
        df = load_recent_data(conn, device_id, features, seq_len)

        if df.empty:
            print(f"[设备 {device_id}] 没有历史数据，跳过检测")
            return

        if len(df) < seq_len:
            print(
                f"[设备 {device_id}] 数据量不足，当前 {len(df)} 条，至少需要 {seq_len} 条"
            )
            return

        # ============================================================
        # 数据数值化检查
        # ============================================================
        # 将特征列转换为数值。
        # 如果存在无法转换的数据，则说明最近窗口数据质量不足，跳过检测。
        for col in features:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if df[features].isna().any(axis=1).any():
            print(f"[设备 {device_id}] 最近窗口存在非数值或空值，跳过检测")
            print(df[["history_id", "record_time"] + features])
            return

        # 取出特征数据。
        values = df[features].astype(float).values

        # 使用训练阶段保存的 scaler 进行标准化。
        # 注意：检测阶段不能重新 fit scaler，只能 transform。
        scaled_values = scaler.transform(values)

        # LSTM Autoencoder 输入需要三维张量：
        # batch_size × sequence_length × feature_size
        # 这里只检测一个窗口，所以 batch_size = 1。
        x = torch.tensor(scaled_values[np.newaxis, :, :], dtype=torch.float32)

        # ============================================================
        # 计算重构误差
        # ============================================================
        with torch.no_grad():
            reconstructed = model(x)

            # 对时间维度和特征维度求平均均方误差。
            error = torch.mean((reconstructed - x) ** 2).item()

        # 如果重构误差超过阈值，则判定为异常。
        is_anomaly = error > threshold

        # 当前窗口开始和结束时间，用于写入结果表。
        window_start_time = df["record_time"].iloc[0]
        window_end_time = df["record_time"].iloc[-1]

        # 将检测结果写入 dl_anomaly_record 表。
        save_result(
            conn,
            device_id,
            window_start_time,
            window_end_time,
            error,
            threshold,
            is_anomaly,
        )

        # 打印检测结果，便于实验截图和调试。
        print(
            f"[设备 {device_id}] 检测完成 "
            f"窗口={window_start_time} ~ {window_end_time}, "
            f"error={error:.6f}, threshold={threshold:.6f}, "
            f"is_anomaly={1 if is_anomaly else 0}"
        )

    finally:
        # 关闭数据库连接。
        conn.close()


def main():
    """
    检测入口函数。

    当前系统中已有三台设备：
        1 主提升机
        2 主通风机
        3 排水泵

    这里分别对每台设备最近一个时间窗口执行深度学习辅助检测。
    """
    cfg = load_config()

    device_ids = [1, 2, 3]

    for device_id in device_ids:
        detect_one_device(cfg, device_id)


if __name__ == "__main__":
    main()
"""dl_detector.py 是深度学习检测脚本。它会加载训练阶段保存的模型、标准化器和异常阈值，
然后从 energy_history 表读取每台设备最近10条历史数据，构造成一个时间窗口。模型会对这个窗口进行重构，并计算重构误差。
如果重构误差超过阈值，就把该窗口判定为异常，并把结果写入 dl_anomaly_record 表。
比如主通风机异常窗口的重构误差为 12.626498，高于阈值 1.300105，所以被判定为异常。"""
