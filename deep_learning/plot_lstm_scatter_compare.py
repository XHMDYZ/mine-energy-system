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

# ============================================================
# 基础路径配置
# ============================================================
# BASE_DIR 表示当前 deep_learning 目录。
BASE_DIR = Path(__file__).resolve().parent

# PROJECT_DIR 表示项目根目录。
# 因为 deep_learning 在项目根目录下，所以 parent 就是项目根目录。
PROJECT_DIR = BASE_DIR.parent

# 深度学习模块配置文件路径。
CONFIG_PATH = BASE_DIR / "model_config.json"

# 模型文件目录。
# train_lstm_autoencoder.py 训练完成后，会在该目录保存模型、标准化器和阈值文件。
MODEL_DIR = BASE_DIR / "models"

# 图片和CSV结果输出目录。
# 生成的散点图和绘图数据会保存到 figures 目录，便于插入论文。
OUTPUT_DIR = PROJECT_DIR / "figures"
OUTPUT_DIR.mkdir(exist_ok=True)


# ============================================================
# 实验参数配置
# ============================================================

# 本次散点对比实验选择主通风机。
# 这样和前面的深度学习检测实验、规则对比实验保持一致。
DEVICE_ID = 2

# 滑动窗口长度。
# 需要和 train_lstm_autoencoder.py 训练时的 sequence_length 保持一致。
# 本文设置为10，即每10条历史记录构造一个检测窗口。
SEQUENCE_LENGTH = 10

# 从 energy_history 表中读取最近多少条历史数据。
# 数据越多，构造出的滑动窗口越多，散点图中点也越多。
LIMIT_ROWS = 900

# ============================================================
# 基础规则候选异常阈值
# ============================================================
# 这里的规则不是最终报警规则，而是“候选异常窗口”的筛选条件。
# 也就是说，先用相对宽松的规则从全部滑动窗口中筛出一批疑似异常窗口，
# 然后再使用 LSTM Autoencoder 进行辅助确认。
#
# 注意：
#   这里一定要在论文中说明为“候选异常窗口”，不要直接叫“最终异常报警”。
#   因为该阶段的作用是初筛，不是最终报警。
#
# 当前参数对应你论文里的实验结果：
#   基础规则候选异常窗口：78个
#   LSTM辅助确认异常窗口：34个
RULE_POWER_FACTOR = 1.10  # 功率超过额定功率的1.10倍，作为候选异常条件之一
RULE_RATE_THRESHOLD = 0.15  # 窗口内相邻功率变化率超过15%，作为候选异常条件之一
RULE_DEVIATION_THRESHOLD = 0.12  # 窗口中位功率偏离历史基准12%，作为候选异常条件之一


class LSTMAutoencoder(nn.Module):
    """
    LSTM Autoencoder 模型结构。

    该模型结构需要和训练脚本 train_lstm_autoencoder.py 中保持一致。
    本脚本不负责训练模型，而是加载已经训练好的模型，
    用于计算每个滑动窗口的重构误差。

    在散点图实验中：
        基础规则负责筛出候选异常窗口；
        LSTM Autoencoder 根据重构误差进一步确认候选窗口是否异常。
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

        # 编码器：读取输入时间窗口，将窗口压缩为隐藏状态。
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
                输入时间窗口，形状为：
                batch_size × sequence_length × input_size

        返回:
            output:
                重构后的时间窗口，形状与输入一致。

        说明:
            如果输入窗口符合模型学到的正常模式，重构误差较小；
            如果输入窗口偏离正常运行模式，重构误差较大。
        """

        # encoder 输出最后时刻的隐藏状态 hidden。
        _, (hidden, _) = self.encoder(x)

        # 将最后一层隐藏状态复制 sequence_length 次，
        # 作为 decoder 的每个时间步输入。
        repeated = hidden[-1].unsqueeze(1).repeat(1, x.size(1), 1)

        # decoder 输出重构序列。
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
            从 model_config.json 中读取到的配置字典。

    返回:
        pymysql 数据库连接对象。

    说明:
        数据库密码优先从环境变量 MYSQL_PASSWORD 中读取，
        避免将数据库密码直接写死在代码中。
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
    )


def load_lstm_model(device_id):
    """
    加载指定设备训练好的 LSTM Autoencoder 模型、标准化器和异常阈值。

    参数:
        device_id:
            设备编号。

    返回:
        model:
            加载好参数的 LSTM Autoencoder 模型。
        scaler:
            训练阶段保存的 StandardScaler。
        threshold:
            该设备对应的异常阈值。

    说明:
        检测阶段必须使用训练阶段保存的 scaler。
        如果重新 fit 标准化器，重构误差和训练阈值就不再可比。
    """

    model_path = MODEL_DIR / f"lstm_autoencoder_device_{device_id}.pt"
    scaler_path = MODEL_DIR / f"scaler_device_{device_id}.pkl"
    threshold_path = MODEL_DIR / f"threshold_device_{device_id}.json"

    # 加载模型结构参数和权重。
    checkpoint = torch.load(model_path, map_location="cpu")

    # 加载训练阶段保存的标准化器。
    scaler = joblib.load(scaler_path)

    # 加载异常阈值文件。
    with open(threshold_path, "r", encoding="utf-8") as f:
        threshold_info = json.load(f)

    # 根据训练时保存的参数重新构建模型。
    model = LSTMAutoencoder(
        input_size=checkpoint["input_size"],
        hidden_size=checkpoint["hidden_size"],
        num_layers=checkpoint["num_layers"],
    )

    # 加载训练好的模型参数。
    model.load_state_dict(checkpoint["model_state_dict"])

    # 设置为评估模式。
    model.eval()

    threshold = float(threshold_info["threshold"])

    return model, scaler, threshold


def query_device_info(conn, device_id):
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
        基础规则候选筛选需要使用设备额定功率。
    """
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
    """
    从 energy_history 表中读取指定设备的历史数据。

    参数:
        conn:
            MySQL 数据库连接。
        device_id:
            设备编号。

    返回:
        df:
            清洗后的历史数据，按 record_time 升序排列。

    对应论文内容:
        energy_history 表保存经过数据清洗后的正式历史数据。
        本脚本使用这些历史数据构造滑动窗口，用于候选异常筛选和 LSTM辅助确认。
    """
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

    # SQL中按时间倒序读取最近数据，这里重新按时间升序排列，
    # 便于后续构造时间滑动窗口。
    df = df.sort_values("record_time").reset_index(drop=True)

    # 将电压、电流、功率转换为数值类型。
    # 如果存在非法字符串，会转成NaN并在下一步删除。
    for col in ["voltage", "current", "power"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 删除非数值或空值记录，保证模型输入数据有效。
    df = df.dropna(subset=["voltage", "current", "power"]).reset_index(drop=True)

    if len(df) < SEQUENCE_LENGTH:
        raise ValueError(f"数据不足，当前 {len(df)} 条，至少需要 {SEQUENCE_LENGTH} 条")

    return df


def calc_reconstruction_error(model, scaler, window_values):
    """
    计算一个时间窗口的 LSTM Autoencoder 重构误差。

    参数:
        model:
            训练好的 LSTM Autoencoder 模型。
        scaler:
            训练阶段保存的标准化器。
        window_values:
            当前窗口的原始特征值，形状为：
            sequence_length × feature_size

    返回:
        error:
            当前窗口的平均重构误差。

    说明:
        重构误差越大，说明当前窗口越偏离模型学习到的正常运行模式。
    """

    # 使用训练阶段的 scaler 进行标准化。
    scaled = scaler.transform(window_values)

    # 转换成 LSTM 所需的三维张量：
    # batch_size × sequence_length × feature_size。
    # 这里只有一个窗口，因此 batch_size=1。
    x = torch.tensor(scaled[np.newaxis, :, :], dtype=torch.float32)

    with torch.no_grad():
        reconstructed = model(x)

        # 对时间维度和特征维度求平均均方误差。
        error = torch.mean((reconstructed - x) ** 2).item()

    return float(error)


def is_rule_candidate(power_window, rated_power, baseline_power):
    """
    判断某个窗口是否属于“基础规则候选异常窗口”。

    参数:
        power_window:
            当前窗口中的功率序列。
        rated_power:
            设备额定功率。
        baseline_power:
            历史基准功率，一般取历史功率中位数。

    返回:
        bool:
            True 表示该窗口被基础规则筛选为候选异常窗口；
            False 表示该窗口不属于候选异常窗口。

    候选规则:
        1. 窗口最大功率超过额定功率一定倍数；
        2. 窗口内相邻功率变化率超过阈值；
        3. 窗口中位功率偏离历史基准超过阈值。

    注意:
        这里的阈值设置相对宽松，目的是形成候选异常窗口，
        再交给 LSTM Autoencoder 进行二次确认。
    """
    power_window = np.array(power_window, dtype=float)

    max_power = np.max(power_window)
    median_power = np.median(power_window)

    # 1. 功率接近或超过额定功率。
    power_flag = max_power > rated_power * RULE_POWER_FACTOR

    # 2. 窗口内存在较大变化率。
    rate_flag = False
    for i in range(1, len(power_window)):
        prev = power_window[i - 1]
        cur = power_window[i]
        if prev > 0:
            rate = abs(cur - prev) / prev
            if rate > RULE_RATE_THRESHOLD:
                rate_flag = True
                break

    # 3. 窗口整体功率偏离历史基准。
    if baseline_power > 0:
        deviation_rate = abs(median_power - baseline_power) / baseline_power
    else:
        deviation_rate = 0

    deviation_flag = deviation_rate > RULE_DEVIATION_THRESHOLD

    return power_flag or rate_flag or deviation_flag


def build_scatter_data(df, model, scaler, threshold, rated_power):
    """
    构造散点图所需的数据。

    参数:
        df:
            主通风机历史数据。
        model:
            LSTM Autoencoder 模型。
        scaler:
            标准化器。
        threshold:
            异常阈值。
        rated_power:
            主通风机额定功率。

    返回:
        compare_df:
            每个滑动窗口的检测结果，包括：
            window_id、平均功率、最大功率、重构误差、阈值、
            是否为规则候选窗口、是否被LSTM确认异常等字段。

    整体流程:
        1. 使用历史功率中位数作为基准功率；
        2. 按长度为10构造滑动窗口；
        3. 对每个窗口计算 LSTM 重构误差；
        4. 用基础规则判断是否为候选异常窗口；
        5. 如果候选窗口的重构误差超过阈值，则认为被 LSTM 辅助确认为异常。
    """

    # 使用历史功率中位数作为基准功率。
    # 中位数对少量异常值不敏感，适合作为简单历史基准。
    baseline_power = float(df["power"].median())

    records = []

    # LSTM模型使用的输入特征。
    features = ["voltage", "current", "power"]

    # 遍历所有滑动窗口。
    for start in range(0, len(df) - SEQUENCE_LENGTH + 1):
        end = start + SEQUENCE_LENGTH

        # 当前窗口数据。
        window = df.iloc[start:end]

        # 当前窗口的模型输入特征。
        window_values = window[features].astype(float).values

        # 当前窗口的功率序列，用于基础规则候选筛选。
        power_window = window["power"].astype(float).values

        # 计算当前窗口的 LSTM 重构误差。
        reconstruction_error = calc_reconstruction_error(model, scaler, window_values)

        # 判断当前窗口是否属于基础规则候选异常窗口。
        rule_candidate = is_rule_candidate(
            power_window=power_window,
            rated_power=rated_power,
            baseline_power=baseline_power,
        )

        # LSTM辅助确认逻辑：
        # 只有先被基础规则筛为候选窗口，并且重构误差超过阈值，
        # 才认为是 LSTM 辅助确认异常窗口。
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
    """
    绘制规则候选异常窗口与 LSTM 辅助确认结果的散点图。

    参数:
        compare_df:
            build_scatter_data() 生成的对比数据。
        device_name:
            设备名称。

    图中含义:
        蓝色点：
            基础规则筛选出的候选异常窗口。

        橙色叉号：
            在基础规则候选窗口中，重构误差超过阈值、
            被 LSTM Autoencoder 进一步确认为异常的窗口。

        横向虚线 y=1：
            LSTM异常判定边界。
            当“重构误差 / 异常阈值 > 1”时，说明该窗口超过阈值。
    """

    # 设置中文字体，避免图中中文乱码。
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    # 只画基础规则筛出的候选窗口。
    candidate_df = compare_df[compare_df["rule_candidate"] == 1].copy()

    # 在候选窗口中，再筛出 LSTM 辅助确认异常的窗口。
    confirmed_df = compare_df[compare_df["lstm_confirmed"] == 1].copy()

    if candidate_df.empty:
        print("没有基础规则候选异常点，请适当调低规则阈值")
        return

    # 使用“重构误差 / 阈值”作为纵轴。
    # 这样比直接画重构误差更直观：
    #   大于1表示超过阈值；
    #   小于1表示未超过阈值。
    candidate_df["error_ratio"] = (
        candidate_df["reconstruction_error"] / candidate_df["threshold"]
    )

    confirmed_df["error_ratio"] = (
        confirmed_df["reconstruction_error"] / confirmed_df["threshold"]
    )

    before_count = len(candidate_df)
    after_count = len(confirmed_df)

    plt.figure(figsize=(11, 5.8))

    # 绘制基础规则候选异常窗口。
    plt.scatter(
        candidate_df["window_id"],
        candidate_df["error_ratio"],
        s=26,
        alpha=0.35,
        label=f"基础规则候选异常窗口（{before_count}个）",
    )

    # 绘制 LSTM 辅助确认异常窗口。
    # marker="x" 用于和基础候选点区分。
    plt.scatter(
        confirmed_df["window_id"],
        confirmed_df["error_ratio"],
        s=95,
        marker="x",
        linewidths=2.4,
        label=f"LSTM辅助确认异常窗口（{after_count}个）",
    )

    # y=1 表示重构误差等于异常阈值。
    # 位于该线以上的点表示超过阈值。
    plt.axhline(
        y=1,
        linestyle="--",
        linewidth=1.8,
        label="LSTM异常判定边界（重构误差/阈值=1）",
    )

    # ============================================================
    # 给部分代表性点添加标注
    # ============================================================
    # 如果所有点都标注，会导致图像过于拥挤。
    # 因此只标注：
    #   1. 误差比最大的前5个点；
    #   2. 最接近阈值的前3个点。
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

    # 设置坐标轴、标题、网格和图例。
    plt.xlabel("滑动窗口序号")
    plt.ylabel("重构误差 / 异常阈值")
    plt.title(f"{device_name}规则候选窗口与LSTM辅助确认结果对比")
    plt.grid(True, linestyle="--", alpha=0.35)
    plt.legend()
    plt.tight_layout()

    # 保存图片，dpi=300适合插入论文。
    output_path = OUTPUT_DIR / "rule_lstm_error_ratio_scatter.png"
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"散点图已生成：{output_path}")


def main():
    """
    散点图对比实验主流程。

    作用:
        生成论文中“规则候选异常窗口与 LSTM 辅助确认结果散点图”。

    流程:
        1. 读取配置文件；
        2. 连接 MySQL 数据库；
        3. 查询主通风机设备信息；
        4. 查询主通风机历史数据；
        5. 加载主通风机 LSTM Autoencoder 模型；
        6. 构造滑动窗口并计算每个窗口的检测结果；
        7. 保存绘图数据 CSV；
        8. 输出统计数量；
        9. 绘制并保存散点图。
    """
    cfg = load_config()
    conn = get_mysql_conn(cfg)

    try:
        # 查询设备名称和额定功率。
        device_name, rated_power = query_device_info(conn, DEVICE_ID)

        # 查询历史能耗数据。
        df = query_history_data(conn, DEVICE_ID)

        # 加载训练好的 LSTM Autoencoder 模型、标准化器和阈值。
        model, scaler, threshold = load_lstm_model(DEVICE_ID)

        # 构造滑动窗口检测结果。
        compare_df = build_scatter_data(
            df=df,
            model=model,
            scaler=scaler,
            threshold=threshold,
            rated_power=rated_power,
        )

        # 保存绘图数据，方便后续检查和论文数据说明。
        output_csv = OUTPUT_DIR / "rule_lstm_scatter_compare_data.csv"
        compare_df.to_csv(output_csv, index=False, encoding="utf-8-sig")

        # 统计基础规则候选异常窗口数量和 LSTM 辅助确认异常窗口数量。
        before_count = int(compare_df["rule_candidate"].sum())
        after_count = int(compare_df["lstm_confirmed"].sum())

        print(f"设备：{device_name}")
        print(f"历史数据条数：{len(df)}")
        print(f"滑动窗口数量：{len(compare_df)}")
        print(f"基础规则候选异常点数量：{before_count}")
        print(f"LSTM辅助确认异常点数量：{after_count}")
        print(f"重构误差阈值：{threshold:.6f}")
        print(f"绘图数据已保存：{output_csv}")

        # 绘制散点图。
        plot_scatter(compare_df, device_name)

        # 输出调参提示。
        print("\n提示：")
        print(
            "如果基础规则候选异常点太少，可以适当调小 RULE_POWER_FACTOR、RULE_RATE_THRESHOLD 或 RULE_DEVIATION_THRESHOLD。"
        )
        print(
            "如果 LSTM 辅助确认点太少或为 0，说明当前历史数据中超过重构误差阈值的异常窗口较少，可以结合前面的异常注入实验一起说明。"
        )

    finally:
        # 关闭数据库连接。
        conn.close()


if __name__ == "__main__":
    main()
"""plot_lstm_scatter_compare.py 是深度学习实验结果可视化脚本。
它从 energy_history 表读取主通风机历史数据，按照长度为10构造776个滑动窗口。
然后先用较宽松的基础规则筛选候选异常窗口，共筛出78个；再用 LSTM Autoencoder 计算每个候选窗口的重构误差，
如果重构误差超过阈值，就辅助确认为异常，最终确认34个窗口。这个脚本生成的散点图用来说明深度学习模块不是简单增加报警，
而是对规则候选窗口做进一步筛选，使异常结果更加集中。"""
