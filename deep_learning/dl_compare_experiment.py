import json
import os
from pathlib import Path

import joblib
import numpy as np
import pymysql
import torch
import torch.nn as nn

# ============================================================
# 基础路径配置
# ============================================================
# BASE_DIR 表示当前 deep_learning 目录。
BASE_DIR = Path(__file__).resolve().parent

# 深度学习模块配置文件路径。
# 该文件中保存数据库连接参数、模型参数等信息。
CONFIG_PATH = BASE_DIR / "model_config.json"

# 模型文件目录。
# train_lstm_autoencoder.py 训练完成后，会把模型、标准化器和阈值文件保存到这里。
MODEL_DIR = BASE_DIR / "models"


class LSTMAutoencoder(nn.Module):
    """
    LSTM Autoencoder 模型结构。

    该结构需要和训练脚本 train_lstm_autoencoder.py 中保持一致。
    本脚本不是重新训练模型，而是加载已经训练好的模型，
    用于计算不同测试场景下的重构误差。

    模型基本思想:
        1. Encoder 读取一段时间序列窗口，并压缩成隐藏状态；
        2. Decoder 根据隐藏状态重构原始窗口；
        3. 如果窗口符合历史正常运行模式，重构误差通常较小；
        4. 如果窗口存在异常模式，重构误差通常较大。
    """

    def __init__(self, input_size, hidden_size=32, num_layers=1):
        """
        初始化 LSTM Autoencoder。

        参数:
            input_size:
                输入特征数量。本文一般为3，对应 voltage、current、power。
            hidden_size:
                LSTM隐藏层维度。
            num_layers:
                LSTM层数。
        """
        super().__init__()

        # 编码器：将输入时间窗口压缩成隐藏表示。
        self.encoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )

        # 解码器：根据隐藏表示重构原始时间窗口。
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
                输入时间窗口，形状为：
                batch_size × sequence_length × input_size

        返回:
            output:
                重构后的时间窗口，形状与输入保持一致。
        """

        # encoder 输出最后一层隐藏状态。
        _, (hidden, _) = self.encoder(x)

        # 将隐藏状态复制 sequence_length 次，作为 decoder 的输入。
        repeated = hidden[-1].unsqueeze(1).repeat(1, x.size(1), 1)

        # decoder 根据隐藏状态重构时间窗口。
        output, _ = self.decoder(repeated)

        return output


def load_config():
    """
    读取深度学习模块配置文件。

    返回:
        cfg: dict
            包含数据库连接信息等配置。
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
        避免把本地数据库密码直接写死在代码中。
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
        autocommit=True,
    )


def load_model(device_id):
    """
    加载指定设备训练好的 LSTM Autoencoder 模型、标准化器和阈值。

    参数:
        device_id:
            设备编号。

    返回:
        model:
            已加载训练参数的 LSTM Autoencoder 模型。
        scaler:
            训练阶段保存的 StandardScaler。
        threshold_info:
            阈值文件中的信息。
        checkpoint:
            模型文件中保存的结构参数和输入特征信息。

    说明:
        本文为不同设备分别训练模型。
        这里选择主通风机 device_id=2 进行对比实验。
    """

    model_path = MODEL_DIR / f"lstm_autoencoder_device_{device_id}.pt"
    scaler_path = MODEL_DIR / f"scaler_device_{device_id}.pkl"
    threshold_path = MODEL_DIR / f"threshold_device_{device_id}.json"

    # 加载 PyTorch 模型文件。
    checkpoint = torch.load(model_path, map_location="cpu")

    # 加载训练阶段保存的标准化器。
    scaler = joblib.load(scaler_path)

    # 加载异常阈值。
    with open(threshold_path, "r", encoding="utf-8") as f:
        threshold_info = json.load(f)

    # 根据训练时保存的参数重新构建模型结构。
    model = LSTMAutoencoder(
        input_size=checkpoint["input_size"],
        hidden_size=checkpoint["hidden_size"],
        num_layers=checkpoint["num_layers"],
    )

    # 加载训练好的权重。
    model.load_state_dict(checkpoint["model_state_dict"])

    # 设置为评估模式。
    model.eval()

    return model, scaler, threshold_info, checkpoint


def get_device_info(conn, device_id):
    """
    查询设备基础信息。

    参数:
        conn:
            MySQL 数据库连接。
        device_id:
            设备编号。

    返回:
        device_name:
            设备名称。
        rated_power:
            设备额定功率。

    作用:
        对比实验中的规则检测需要用到设备额定功率。
    """
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

    # 如果数据库中没有额定功率，则给一个默认值，避免程序中断。
    rated_power = float(row.get("rated_power") or 160)
    return row["device_name"], rated_power


def get_baseline_power(conn, device_id, rated_power):
    """
    根据历史数据计算设备功率基准值。

    参数:
        conn:
            MySQL 数据库连接。
        device_id:
            设备编号。
        rated_power:
            设备额定功率。

    返回:
        baseline_power:
            历史基准功率，一般使用最近正常数据的中位数。

    说明:
        这里使用最近200条历史功率记录，并排除明显过大的功率值。
        使用中位数而不是平均数，是为了降低少量异常值对基准值的影响。
    """
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

    # 如果没有可用历史数据，则用额定功率的75%作为默认基准。
    if len(powers) == 0:
        return rated_power * 0.75

    return float(np.median(powers))


def build_feature_sequence(power_sequence, voltage=380.0):
    """
    根据功率序列构造 LSTM Autoencoder 所需的输入特征。

    参数:
        power_sequence:
            测试场景中的功率序列。
        voltage:
            默认电压值，本文使用380V作为仿真电压。

    返回:
        values:
            三维特征中的二维窗口数据：
            sequence_length × feature_size

    特征构造:
        voltage, current, power

    说明:
        本文 LSTM Autoencoder 训练时使用的输入特征是电压、电流和功率。
        对比实验中主要人为构造功率序列，因此需要根据功率估算电流。
        current = power / voltage * 100
        该计算方式与 OPC UA 写入脚本中的简化逻辑保持一致。
    """
    values = []

    for power in power_sequence:
        current = round(power / voltage * 100, 2)
        values.append([voltage, current, power])

    return np.array(values, dtype=np.float32)


def detect_by_lstm(model, scaler, feature_values):
    """
    使用 LSTM Autoencoder 计算某个测试窗口的重构误差。

    参数:
        model:
            训练好的 LSTM Autoencoder 模型。
        scaler:
            训练阶段保存的标准化器。
        feature_values:
            构造好的窗口特征，形状为：
            sequence_length × feature_size

    返回:
        error:
            当前窗口的重构误差。

    说明:
        检测阶段必须使用训练阶段保存的 scaler 进行 transform，
        不能重新 fit，否则重构误差与训练阈值不再具有可比性。
    """

    # 使用训练阶段的标准化器对测试窗口进行标准化。
    scaled_values = scaler.transform(feature_values)

    # 转换成 LSTM 需要的三维输入：
    # batch_size × sequence_length × feature_size。
    x = torch.tensor(scaled_values[np.newaxis, :, :], dtype=torch.float32)

    # 计算模型重构误差。
    with torch.no_grad():
        reconstructed = model(x)
        error = torch.mean((reconstructed - x) ** 2).item()

    return float(error)


def detect_by_rule(power_sequence, rated_power, baseline_power):
    """
    简化版规则融合检测，用于和 LSTM Autoencoder 进行对比实验。

    参数:
        power_sequence:
            当前测试场景的功率序列。
        rated_power:
            设备额定功率。
        baseline_power:
            历史基准功率。

    检测规则:
        1. 功率超过额定功率 1.2 倍：记40分；
        2. 相邻功率变化率超过50%：记30分；
        3. 窗口中位功率偏离历史基准25%以上：记30分。

    判断逻辑:
        score >= 40：
            认为规则融合检测会进入报警；
        score < 40：
            认为规则侧只是低风险异常或未报警。

    说明:
        这里不是完整后端报警逻辑，而是为了实验对比构造的简化规则版本。
        它用于说明固定规则对不同异常类型的识别能力，以及 LSTM 的补充作用。
    """
    score = 0
    reasons = []

    # ============================================================
    # 1. 功率超限判断
    # ============================================================
    max_power = max(power_sequence)

    if max_power > rated_power * 1.2:
        score += 40
        reasons.append("功率超限")

    # ============================================================
    # 2. 短时变化率判断
    # ============================================================
    # 计算窗口内相邻功率点之间的最大变化率。
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

    # ============================================================
    # 3. 历史偏差判断
    # ============================================================
    # 使用窗口中位功率与历史基准功率比较。
    # 如果整体偏离较大，则认为存在历史偏差异常。
    median_power = float(np.median(power_sequence))
    if baseline_power > 0:
        deviation_rate = abs(median_power - baseline_power) / baseline_power
    else:
        deviation_rate = 0.0

    if deviation_rate > 0.25:
        score += 30
        reasons.append("历史偏差异常")

    # 规则侧是否报警。
    rule_is_anomaly = 1 if score >= 40 else 0

    # 生成规则检测结果说明。
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
    """
    将对比实验结果写入 anomaly_compare_result 表。

    参数:
        scenario_name:
            测试场景名称。
        device_id:
            测试设备编号。
        power_sequence:
            当前测试窗口的功率序列。
        rule_is_anomaly:
            规则方法是否报警。
        rule_result:
            规则方法结果说明。
        dl_error:
            LSTM Autoencoder 重构误差。
        dl_threshold:
            LSTM Autoencoder 异常阈值。
        dl_is_anomaly:
            深度学习方法是否判定异常。
        dl_result:
            深度学习检测结果说明。
        improvement_desc:
            该场景用于说明的提升点。

    对应论文内容:
        anomaly_compare_result 表用于保存规则融合检测与深度学习检测的对比结果。
        第6章中的对比截图和分析文字可以直接基于该表生成。
    """
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
    """
    规则融合检测与 LSTM Autoencoder 对比实验主流程。

    实验目的:
        验证 LSTM Autoencoder 是否能对规则检测方法形成补充。

    实验设备:
        主通风机，device_id=2。

    实验场景:
        1. 正常窗口：
            作为对照组，两种方法都应判断正常。

        2. 明显功率超限异常：
            功率明显超过正常范围，规则方法和 LSTM 都应能识别。

        3. 持续偏高但未明显超限：
            用于观察模型是否会对轻微偏高数据过度报警。

        4. 周期波动模式异常：
            单点不一定严重超限，但窗口整体波动模式异常。
            该场景用于体现 LSTM 对时间窗口整体模式的补充识别能力。
    """

    # 读取配置文件。
    cfg = load_config()

    # 本次对比实验选择主通风机 device_id=2。
    device_id = 2

    # 加载主通风机对应的 LSTM Autoencoder 模型、标准化器和阈值。
    model, scaler, threshold_info, checkpoint = load_model(device_id)
    dl_threshold = float(threshold_info["threshold"])

    # 连接数据库。
    conn = get_mysql_conn(cfg)

    try:
        # 查询设备名称和额定功率。
        device_name, rated_power = get_device_info(conn, device_id)

        # 根据历史数据计算主通风机基准功率。
        baseline_power = get_baseline_power(conn, device_id, rated_power)

        print(f"实验设备: {device_name}, device_id={device_id}")
        print(f"额定功率: {rated_power:.2f}")
        print(f"历史基准功率: {baseline_power:.2f}")
        print(f"LSTM Autoencoder 阈值: {dl_threshold:.6f}")

        # 清空旧的对比实验结果，避免多次运行后表中出现重复数据。
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM anomaly_compare_result")

        # ============================================================
        # 构造测试场景1：正常窗口
        # ============================================================
        # 功率围绕历史基准功率小幅波动。
        # 该场景用于验证规则检测和 LSTM 检测是否会误报正常数据。
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

        # ============================================================
        # 构造测试场景2：明显功率超限异常
        # ============================================================
        # 在窗口中连续插入 220.0 kW 的高功率值。
        # 该场景属于明显异常，规则检测和 LSTM 都应能识别。
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

        # ============================================================
        # 构造测试场景3：持续偏高但未明显超限
        # ============================================================
        # 该场景整体功率比正常水平偏高，但控制在不严重超限的范围内。
        # 用于观察 LSTM 是否会对轻微偏高情况过度敏感。
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

        # ============================================================
        # 构造测试场景4：周期波动模式异常
        # ============================================================
        # 该场景的特点是窗口内功率高低交替波动。
        # 单个点不一定严重超过额定阈值，但整体模式与正常平稳波动明显不同。
        # 这是 LSTM Autoencoder 更容易发挥补充作用的场景。
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

        # 将所有场景组织成列表，便于统一循环检测。
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
                "该场景用于体现模型对轻微偏高数据是否过度敏感",
            ),
            (
                "周期波动模式异常",
                periodic_fluctuation,
                "该场景用于体现深度学习对窗口波动模式异常的补充识别能力",
            ),
        ]

        # ============================================================
        # 逐个场景执行规则检测和 LSTM 检测
        # ============================================================
        for scenario_name, power_sequence, improvement_desc in scenarios:
            # 根据功率序列构造 voltage、current、power 三个输入特征。
            feature_values = build_feature_sequence(power_sequence)

            # 使用 LSTM Autoencoder 计算重构误差。
            dl_error = detect_by_lstm(model, scaler, feature_values)

            # 与阈值比较，判断深度学习是否认为该窗口异常。
            dl_is_anomaly = 1 if dl_error > dl_threshold else 0

            # 使用简化规则融合方法进行检测。
            rule_is_anomaly, rule_result, rule_score = detect_by_rule(
                power_sequence,
                rated_power,
                baseline_power,
            )

            # 生成深度学习检测结果说明。
            dl_result = "深度学习判定异常" if dl_is_anomaly else "深度学习判定正常"

            # 将本场景对比结果写入 anomaly_compare_result 表。
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

            # 打印本场景结果，便于终端截图或调试。
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
        # 关闭数据库连接。
        conn.close()


if __name__ == "__main__":
    main()
"""dl_compare_experiment.py 是规则检测和深度学习检测的对比实验脚本。
它选择主通风机作为测试对象，构造正常窗口、明显功率超限异常、持续偏高但未明显超限、周期波动模式异常四类场景。
每个场景都会分别经过规则检测和 LSTM Autoencoder 检测，并把规则结果、重构误差、阈值、深度学习判定结果写入 anomaly_compare_result 表。
这个实验主要用来说明：明显异常下两种方法都能识别，而周期波动模式异常下，规则方法可能不报警，
但 LSTM 可以通过重构误差识别出来，所以它对规则检测有补充作用。"""
