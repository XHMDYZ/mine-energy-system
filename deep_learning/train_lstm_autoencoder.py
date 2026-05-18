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

# ============================================================
# 基础路径配置
# ============================================================
# BASE_DIR 表示当前 deep_learning 目录。
BASE_DIR = Path(__file__).resolve().parent

# 模型配置文件路径。
# model_config.json 中保存数据库连接参数、模型参数、输入特征、窗口长度等信息。
CONFIG_PATH = BASE_DIR / "model_config.json"

# 模型保存目录。
# 训练完成后，每台设备对应的模型文件、标准化器和阈值文件都会保存在该目录下。
MODEL_DIR = BASE_DIR / "models"


class LSTMAutoencoder(nn.Module):
    """
    LSTM Autoencoder 模型。

    该模型用于无监督时间序列异常检测。
    训练阶段只学习历史正常或近似正常的能耗时间窗口；
    检测阶段通过比较输入窗口和模型重构窗口之间的误差，判断该窗口是否异常。

    在本文中，输入特征包括：
        voltage：电压
        current：电流
        power：功率

    输入数据形状:
        batch_size × sequence_length × input_size

    例如：
        batch_size = 32
        sequence_length = 10
        input_size = 3
    """

    def __init__(self, input_size, hidden_size=32, num_layers=1):
        """
        初始化 LSTM Autoencoder。

        参数:
            input_size:
                输入特征数量，例如电压、电流、功率共3个特征。
            hidden_size:
                LSTM隐藏层维度。值越大，模型表达能力越强，但训练成本也更高。
            num_layers:
                LSTM层数。本文作为本科原型系统，使用较轻量的结构即可。

        模型结构:
            encoder:
                将输入时间序列压缩成隐藏状态，学习窗口的整体运行模式。
            decoder:
                根据隐藏状态重构原始时间序列。
        """
        super().__init__()

        # 编码器：读取输入时间序列，并将其压缩为最后一个隐藏状态。
        self.encoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )

        # 解码器：根据编码器输出的隐藏状态，尝试重构原始输入序列。
        # 这里 decoder 的输入维度为 hidden_size，输出维度为 input_size，
        # 即重构后的每个时间步仍然包含 voltage、current、power 等特征。
        self.decoder = nn.LSTM(
            input_size=hidden_size,
            hidden_size=input_size,
            num_layers=num_layers,
            batch_first=True,
        )

    def forward(self, x):
        """
        前向传播过程。

        参数:
            x:
                输入时间窗口，形状为：
                batch_size × sequence_length × input_size

        返回:
            output:
                模型重构后的时间窗口，形状与输入 x 相同。

        说明:
            如果某个窗口符合设备历史正常运行模式，模型通常能较好地重构；
            如果某个窗口出现异常波动，模型重构效果会变差，重构误差增大。
        """

        # encoder 返回:
        #   output: 每个时间步的输出，这里不使用；
        #   hidden: 最后一个时间步的隐藏状态；
        #   cell: LSTM内部状态，这里不使用。
        _, (hidden, _) = self.encoder(x)

        # 取最后一层的隐藏状态，并复制 sequence_length 次，
        # 作为 decoder 每个时间步的输入。
        repeated = hidden[-1].unsqueeze(1).repeat(1, x.size(1), 1)

        # decoder 根据压缩后的隐藏表示重构原始时间序列。
        output, _ = self.decoder(repeated)

        return output


def load_config():
    """
    读取深度学习模块配置文件。

    返回:
        cfg: dict
            包含数据库配置和模型参数配置。

    配置文件通常包括：
        database:
            host、port、user、password、database
        model:
            features、sequence_length、hidden_size、epochs、batch_size等
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_mysql_conn(cfg):
    """
    创建 MySQL 数据库连接。

    参数:
        cfg:
            从 model_config.json 中读取的配置。

    返回:
        pymysql 数据库连接对象。

    说明:
        密码优先从环境变量 MYSQL_PASSWORD 中读取。
        这样可以避免把真实数据库密码直接写入代码。
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
    )


def load_device_data(conn, device_id, features):
    """
    从 energy_history 表读取指定设备的历史能耗数据。

    参数:
        conn:
            MySQL数据库连接。
        device_id:
            设备编号。
        features:
            模型输入特征列表，例如 ["voltage", "current", "power"]。

    返回:
        df: pandas.DataFrame
            按 record_time 升序排列的历史数据。

    对应论文内容:
        energy_history 表保存清洗通过后的正式历史数据。
        LSTM Autoencoder 不直接使用原始数据表，而是使用清洗后的历史数据训练，
        这样可以减少错误采集数据对模型训练的影响。
    """

    # 将特征字段拼成 SQL 查询字段。
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
    """
    使用滑动窗口构造时间序列样本。

    参数:
        values:
            标准化后的二维数组，形状为：
            记录数 × 特征数
        seq_len:
            时间窗口长度，例如10。

    返回:
        sequences:
            三维数组，形状为：
            样本数 × sequence_length × 特征数

    举例:
        如果原始数据有100条，窗口长度为10，
        则可以构造 100 - 10 + 1 = 91 个窗口样本。

    对应论文内容:
        本文利用长度为10的滑动窗口构造设备运行片段，
        让模型学习一段时间内电压、电流和功率的整体变化模式。
    """
    sequences = []

    for i in range(len(values) - seq_len + 1):
        sequences.append(values[i : i + seq_len])

    return np.array(sequences, dtype=np.float32)


def train_one_device(cfg, device_id):
    """
    针对单台设备训练 LSTM Autoencoder 模型。

    参数:
        cfg:
            模型配置文件。
        device_id:
            设备编号，例如：
                1 主提升机
                2 主通风机
                3 排水泵

    训练流程:
        1. 读取模型参数；
        2. 从数据库读取该设备历史数据；
        3. 清理非数值和空值数据；
        4. 对电压、电流、功率进行标准化；
        5. 构造滑动窗口样本；
        6. 训练 LSTM Autoencoder；
        7. 计算训练集重构误差；
        8. 根据重构误差分位数确定异常阈值；
        9. 保存模型、标准化器和阈值文件。
    """

    # ============================================================
    # 1. 读取模型参数
    # ============================================================
    model_cfg = cfg["model"]

    # 输入特征，例如 ["voltage", "current", "power"]。
    features = model_cfg["features"]

    # 滑动窗口长度。
    seq_len = int(model_cfg["sequence_length"])

    # LSTM隐藏层维度。
    hidden_size = int(model_cfg["hidden_size"])

    # LSTM层数。
    num_layers = int(model_cfg["num_layers"])

    # 训练轮数。
    epochs = int(model_cfg["epochs"])

    # 批大小。
    batch_size = int(model_cfg["batch_size"])

    # 学习率。
    learning_rate = float(model_cfg["learning_rate"])

    # 异常阈值分位数。
    # 例如95表示使用训练集重构误差的95%分位数作为阈值。
    threshold_percentile = float(model_cfg["threshold_percentile"])

    # ============================================================
    # 2. 从数据库读取该设备历史数据
    # ============================================================
    conn = get_mysql_conn(cfg)
    try:
        df = load_device_data(conn, device_id, features)
    finally:
        conn.close()

    # 如果没有历史数据，则无法训练。
    if df.empty:
        print(f"[设备 {device_id}] 没有历史数据，跳过训练")
        return

    # 如果数据量太少，无法构造足够的滑动窗口，则跳过训练。
    if len(df) < seq_len + 5:
        print(
            f"[设备 {device_id}] 数据量不足，当前 {len(df)} 条，至少需要 {seq_len + 5} 条"
        )
        return

    # ============================================================
    # 3. 训练数据基础清理
    # ============================================================
    # 删除输入特征中存在空值的记录。
    df = df.dropna(subset=features).copy()

    # 将特征字段强制转换为数值。
    # 如果数据库中混入了表头字符串、非法字符等内容，会被转成 NaN。
    for col in features:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 找出无法转换为数值或仍然为空的异常训练记录。
    invalid_df = df[df[features].isna().any(axis=1)]
    if not invalid_df.empty:
        print(
            f"[设备 {device_id}] 发现 {len(invalid_df)} 条非数值或空值数据，已自动跳过"
        )
        print(invalid_df[["history_id", "record_time"] + features].head(10))

    # 再次删除非法数据，保证进入模型训练的数据都是有效数值。
    df = df.dropna(subset=features).copy()

    if len(df) < seq_len + 5:
        print(
            f"[设备 {device_id}] 清洗后数据量不足，当前 {len(df)} 条，至少需要 {seq_len + 5} 条"
        )
        return

    # 取出特征值，形成二维数组。
    values = df[features].astype(float).values

    # ============================================================
    # 4. 数据标准化
    # ============================================================
    # 电压、电流、功率的量纲和取值范围不同。
    # 如果直接训练，数值较大的特征可能会主导损失函数。
    # 因此这里使用 StandardScaler 对每个特征进行标准化。
    scaler = StandardScaler()
    scaled_values = scaler.fit_transform(values)

    # ============================================================
    # 5. 构造滑动窗口样本
    # ============================================================
    # LSTM需要输入连续时间序列。
    # 这里按照 seq_len 构造多个窗口，每个窗口代表一段设备运行状态。
    sequences = create_sequences(scaled_values, seq_len)

    if len(sequences) == 0:
        print(f"[设备 {device_id}] 序列数量为 0，跳过训练")
        return

    # 转成 PyTorch Tensor。
    x = torch.tensor(sequences, dtype=torch.float32)

    # TensorDataset 和 DataLoader 用于批量训练。
    dataset = TensorDataset(x)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # 自动选择 GPU 或 CPU。
    # 如果本机安装了 CUDA 版本的 PyTorch，就使用 cuda。
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 初始化模型。
    model = LSTMAutoencoder(
        input_size=len(features),
        hidden_size=hidden_size,
        num_layers=num_layers,
    ).to(device)

    # Adam优化器。
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    # 均方误差损失函数。
    # Autoencoder 的目标是让重构结果尽可能接近输入序列。
    criterion = nn.MSELoss()

    print(f"\n[设备 {device_id}] 开始训练，样本数={len(sequences)}，使用设备={device}")

    # ============================================================
    # 6. 模型训练
    # ============================================================
    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0

        for (batch_x,) in loader:
            batch_x = batch_x.to(device)

            # 清空上一轮梯度。
            optimizer.zero_grad()

            # 前向传播，得到重构序列。
            output = model(batch_x)

            # 计算重构误差。
            loss = criterion(output, batch_x)

            # 反向传播。
            loss.backward()

            # 更新模型参数。
            optimizer.step()

            # 累加当前批次损失。
            epoch_loss += loss.item() * batch_x.size(0)

        # 计算本轮平均损失。
        avg_loss = epoch_loss / len(dataset)

        # 每10轮打印一次训练损失，便于观察训练是否正常下降。
        if epoch == 1 or epoch % 10 == 0 or epoch == epochs:
            print(f"[设备 {device_id}] Epoch {epoch:03d}/{epochs}, Loss={avg_loss:.6f}")

    # ============================================================
    # 7. 计算训练集重构误差并确定异常阈值
    # ============================================================
    model.eval()
    with torch.no_grad():
        x_device = x.to(device)

        # 使用训练好的模型对训练窗口进行重构。
        reconstructed = model(x_device)

        # 对每个窗口计算平均重构误差。
        # dim=(1, 2) 表示同时在时间维度和特征维度上求均值。
        errors = torch.mean((reconstructed - x_device) ** 2, dim=(1, 2)).cpu().numpy()

    # 使用训练集重构误差的指定分位数作为异常阈值。
    # 例如95%分位数表示：训练集中约95%的窗口误差低于该阈值。
    # 检测阶段如果某个窗口误差超过该阈值，就认为其偏离正常模式。
    threshold = float(np.percentile(errors, threshold_percentile))

    # 确保模型目录存在。
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # 8. 保存模型、标准化器和阈值文件
    # ============================================================
    model_path = MODEL_DIR / f"lstm_autoencoder_device_{device_id}.pt"
    scaler_path = MODEL_DIR / f"scaler_device_{device_id}.pkl"
    threshold_path = MODEL_DIR / f"threshold_device_{device_id}.json"

    # 保存 PyTorch 模型参数和必要的结构信息。
    # 检测脚本需要根据这些信息重新构造模型结构。
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

    # 保存标准化器。
    # 检测阶段必须使用训练阶段相同的均值和标准差进行标准化，
    # 否则重构误差没有可比性。
    joblib.dump(scaler, scaler_path)

    # 保存异常阈值和训练数据统计信息。
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
    """
    训练入口函数。

    当前系统中已有三台设备：
        1 主提升机
        2 主通风机
        3 排水泵

    这里分别为每台设备训练一个独立的 LSTM Autoencoder 模型。
    这样做的原因是不同设备的功率水平、运行波动和历史模式并不完全相同，
    每台设备使用独立模型更符合设备级异常检测思路。
    """
    cfg = load_config()

    # 当前系统中已有三台设备：1 主提升机，2 主通风机，3 排水泵。
    device_ids = [1, 2, 3]

    for device_id in device_ids:
        train_one_device(cfg, device_id)


if __name__ == "__main__":
    main()
"""train_lstm_autoencoder.py 是深度学习模型训练脚本。它从 energy_history 表读取清洗后的历史数据，
以电压、电流和功率作为输入特征，按照长度为10的滑动窗口构造时间序列样本。
然后分别为主提升机、主通风机和排水泵训练 LSTM Autoencoder 模型。训练完成后，程序会计算训练集重构误差，并使用95%分位数作为异常阈值，
最后保存模型文件、标准化器和阈值文件，供后续检测脚本使用。"""
