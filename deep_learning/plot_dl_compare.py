import json
import os
from pathlib import Path

import pandas as pd
import pymysql
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
CONFIG_PATH = BASE_DIR / "model_config.json"
OUTPUT_DIR = PROJECT_DIR / "figures"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_mysql_conn(cfg):
    db_cfg = cfg["database"]

    # 优先使用环境变量里的密码；没有环境变量时，使用配置文件里的密码
    password = os.getenv("MYSQL_PASSWORD", db_cfg.get("password", ""))

    return pymysql.connect(
        host=db_cfg["host"],
        port=int(db_cfg["port"]),
        user=db_cfg["user"],
        password=password,
        database=db_cfg["database"],
        charset="utf8mb4",
    )


def query_compare_result(conn):
    sql = """
        SELECT
            compare_id,
            scenario_name,
            rule_is_anomaly,
            dl_reconstruction_error,
            dl_threshold_value,
            dl_is_anomaly
        FROM anomaly_compare_result
        ORDER BY compare_id;
    """
    return pd.read_sql(sql, conn)


def plot_reconstruction_error(df):
    # 设置中文字体，避免图片里中文乱码
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    x = range(len(df))
    scenario_names = df["scenario_name"].tolist()

    plt.figure(figsize=(11, 6))

    # LSTM Autoencoder 重构误差
    plt.plot(
        x,
        df["dl_reconstruction_error"],
        marker="o",
        linewidth=2,
        label="LSTM Autoencoder重构误差",
    )

    # 异常阈值
    plt.plot(
        x,
        df["dl_threshold_value"],
        marker="s",
        linestyle="--",
        linewidth=2,
        label="异常阈值",
    )

    # 给每个点标注数值
    for i, row in df.iterrows():
        error = row["dl_reconstruction_error"]
        threshold = row["dl_threshold_value"]

        plt.text(
            i,
            error,
            f"{error:.3f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

        # 对深度学习判定异常的点加文字提示
        if int(row["dl_is_anomaly"]) == 1:
            plt.text(
                i,
                error,
                "异常",
                ha="center",
                va="top",
                fontsize=9,
            )

    plt.xticks(x, scenario_names, rotation=15)
    plt.xlabel("测试场景")
    plt.ylabel("重构误差")
    plt.title("规则融合检测与LSTM Autoencoder检测结果对比")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()

    output_path = OUTPUT_DIR / "dl_compare_reconstruction_error.png"
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"图片已生成：{output_path}")


def main():
    cfg = load_config()
    conn = get_mysql_conn(cfg)

    try:
        df = query_compare_result(conn)

        if df.empty:
            print(
                "anomaly_compare_result 表中没有数据，请先运行 dl_compare_experiment.py"
            )
            return

        print("读取到的对比实验数据：")
        print(df)

        plot_reconstruction_error(df)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
