<template>
  <!--
    首页概览页面。
    该页面是系统进入后的首页，用于快速展示平台整体运行情况。
    主要包含两部分：
    1. 上方三张统计卡片：设备总数、报警总数、历史数据总数；
    2. 下方两个信息面板：系统运行流程、核心功能模块。
  -->
  <div class="overview-page">
    <!--
      第一行：统计卡片区域。
      el-row 和 el-col 是 Element Plus 的栅格布局组件。
      :gutter="20" 表示三张卡片之间有 20px 的间距。
    -->
    <el-row :gutter="20">
      <!-- 设备总数卡片 -->
      <el-col :span="8">
        <!--
          el-card 是 Element Plus 的卡片组件。
          shadow="hover" 表示鼠标移上去时显示阴影效果。
          blue 是自定义样式类，用于设置浅蓝色渐变背景。
        -->
        <el-card class="stat-card blue" shadow="hover">
          <div class="stat-content">
            <div>
              <div class="stat-label">设备总数</div>

              <!--
                overview.device_count 来自后端 /api/overview 接口。
                表示当前平台中已接入或已维护的设备数量。
              -->
              <div class="stat-value">{{ overview.device_count }}</div>

              <div class="stat-desc">当前接入平台的矿山设备数量</div>
            </div>

            <!--
              Monitor 是 Element Plus 图标。
              这里用作设备总数卡片的装饰图标。
            -->
            <el-icon class="stat-icon"><Monitor /></el-icon>
          </div>
        </el-card>
      </el-col>

      <!-- 报警总数卡片 -->
      <el-col :span="8">
        <el-card class="stat-card orange" shadow="hover">
          <div class="stat-content">
            <div>
              <div class="stat-label">报警总数</div>

              <!--
                overview.alarm_count 表示当前系统已经生成的报警记录数量。
                该数据来自后端报警表 alarm_record 的统计结果。
              -->
              <div class="stat-value">{{ overview.alarm_count }}</div>

              <div class="stat-desc">系统已生成的异常报警记录</div>
            </div>

            <!-- 报警类图标，用于突出异常报警信息 -->
            <el-icon class="stat-icon"><Warning /></el-icon>
          </div>
        </el-card>
      </el-col>

      <!-- 历史数据总数卡片 -->
      <el-col :span="8">
        <el-card class="stat-card green" shadow="hover">
          <div class="stat-content">
            <div>
              <div class="stat-label">历史数据总数</div>

              <!--
                overview.history_count 表示 energy_history 表中的历史数据数量。
                该表保存的是经过数据清洗后正式进入平台分析的数据。
              -->
              <div class="stat-value">{{ overview.history_count }}</div>

              <div class="stat-desc">清洗通过后的能耗历史数据</div>
            </div>

            <!-- 数据趋势类图标，用于表示历史数据积累情况 -->
            <el-icon class="stat-icon"><DataLine /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!--
      第二行：系统说明区域。
      左侧展示系统运行流程；
      右侧展示平台核心功能模块。
    -->
    <el-row :gutter="20" class="content-row">
      <!-- 左侧：系统运行流程说明 -->
      <el-col :span="15">
        <el-card class="panel-card" shadow="never">
          <!--
            el-card 的 header 插槽。
            用于自定义卡片顶部标题区域。
          -->
          <template #header>
            <div class="panel-header">
              <span>系统运行流程</span>

              <!--
                Running 标签用于提示系统处于运行状态。
                这里是展示性标签，不涉及后端状态判断。
              -->
              <el-tag type="success">Running</el-tag>
            </div>
          </template>

          <!-- 流程列表 -->
          <div class="flow-list">
            <!-- 流程 1：OPC UA 数据接入 -->
            <div class="flow-item">
              <div class="flow-index">01</div>
              <div>
                <div class="flow-title">OPC UA 数据接入</div>
                <div class="flow-desc">
                  通过 Prosys OPC UA 仿真服务器读取设备电压、电流、功率和累计能耗数据。
                </div>
              </div>
            </div>

            <!-- 流程 2：数据清洗与标准化 -->
            <div class="flow-item">
              <div class="flow-index">02</div>
              <div>
                <div class="flow-title">数据清洗与标准化</div>
                <div class="flow-desc">
                  对缺失值、重复值、异常范围和累计能耗回跳进行检查，保证历史数据可靠。
                </div>
              </div>
            </div>

            <!-- 流程 3：融合异常检测 -->
            <div class="flow-item">
              <div class="flow-index">03</div>
              <div>
                <div class="flow-title">融合异常检测</div>
                <div class="flow-desc">
                  结合功率超限、变化率异常和历史偏差检测，生成异常结果与报警记录。
                </div>
              </div>
            </div>

            <!-- 流程 4：LSTM 辅助分析 -->
            <div class="flow-item">
              <div class="flow-index">04</div>
              <div>
                <div class="flow-title">LSTM 辅助分析</div>
                <div class="flow-desc">
                  利用 LSTM Autoencoder 计算重构误差，对规则候选异常窗口进行辅助确认。
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧：核心功能模块 -->
      <el-col :span="9">
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="panel-header">
              <span>核心功能模块</span>
            </div>
          </template>

          <!--
            功能模块宫格。
            这里用于展示平台主要功能，让首页看起来更完整。
          -->
          <div class="module-grid">
            <div class="module-item">
              <el-icon><TrendCharts /></el-icon>
              <span>历史趋势</span>
            </div>

            <div class="module-item">
              <el-icon><Warning /></el-icon>
              <span>报警管理</span>
            </div>

            <div class="module-item">
              <el-icon><Histogram /></el-icon>
              <span>能耗排行</span>
            </div>

            <div class="module-item">
              <el-icon><DataAnalysis /></el-icon>
              <span>同比环比</span>
            </div>

            <div class="module-item">
              <el-icon><Monitor /></el-icon>
              <span>设备管理</span>
            </div>

            <div class="module-item">
              <el-icon><Document /></el-icon>
              <span>报表分析</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
/*
  ref：用于定义响应式变量。
  onMounted：组件挂载完成后执行，一般用于页面初始化加载数据。
  onUnmounted：组件卸载时执行，一般用于清除定时器。
*/
import { ref, onMounted, onUnmounted } from 'vue'

/*
  axios：用于向后端发送 HTTP 请求。
  本页面通过 axios 请求后端 /api/overview 接口。
*/
import axios from 'axios'

/*
  overview 保存首页概览统计数据。
  初始值设置为 0，避免页面刚打开时出现空白或 undefined。
*/
const overview = ref({
  device_count: 0,
  alarm_count: 0,
  history_count: 0
})

/*
  timer 用于保存定时器 ID。
  首页每 5 秒自动刷新一次概览数据。
  页面卸载时需要清除定时器，避免切换页面后仍然持续请求接口。
*/
let timer = null

/*
  loadOverview 用于加载首页概览数据。

  请求接口：
    GET http://127.0.0.1:8080/api/overview

  后端返回的数据大致为：
    {
      message: "查询成功",
      data: {
        device_count: 3,
        alarm_count: 9,
        history_count: 2353
      }
    }

  对应后端：
    GetOverviewData
*/
const loadOverview = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8080/api/overview')

    /*
      如果后端正常返回 data，则更新 overview。
      如果 data 为空，则使用默认值，避免页面报错。
    */
    overview.value = res.data.data || {
      device_count: 0,
      alarm_count: 0,
      history_count: 0
    }
  } catch (err) {
    /*
      请求失败时在控制台打印错误。
      例如后端没有启动、接口路径错误、数据库连接失败等，都可能进入这里。
    */
    console.error('获取首页概览失败：', err)
  }
}

/*
  页面加载完成后执行：
  1. 立即调用一次 loadOverview，加载首页数据；
  2. 设置定时器，每 5 秒刷新一次数据。
*/
onMounted(() => {
  loadOverview()
  timer = setInterval(loadOverview, 5000)
})

/*
  页面卸载时执行。
  如果不清除定时器，用户切换到其他页面后，首页仍然会继续请求后端接口。
*/
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
/*
  scoped 表示当前样式只作用于本组件，
  不会污染其他页面样式。
*/

/* 首页整体容器 */
.overview-page {
  width: 100%;
}

/* 顶部统计卡片统一样式 */
.stat-card {
  border: none;
  border-radius: 18px;
  overflow: hidden;
}

/* 统计卡片内部布局：左侧文字，右侧图标 */
.stat-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* 统计卡片标题，例如“设备总数” */
.stat-label {
  font-size: 15px;
  color: #6b7280;
}

/* 统计数值样式 */
.stat-value {
  margin-top: 10px;
  font-size: 38px;
  font-weight: 800;
  color: #1f2937;
}

/* 统计说明文字 */
.stat-desc {
  margin-top: 8px;
  font-size: 13px;
  color: #9ca3af;
}

/* 统计卡片右侧图标 */
.stat-icon {
  font-size: 56px;
  opacity: 0.2;
}

/* 蓝色渐变卡片，用于设备总数 */
.blue {
  background: linear-gradient(135deg, #ffffff, #eaf3ff);
}

/* 橙色渐变卡片，用于报警总数 */
.orange {
  background: linear-gradient(135deg, #ffffff, #fff4e5);
}

/* 绿色渐变卡片，用于历史数据总数 */
.green {
  background: linear-gradient(135deg, #ffffff, #ecfdf3);
}

/* 不同卡片中图标颜色 */
.blue .stat-icon {
  color: #409eff;
}

.orange .stat-icon {
  color: #e6a23c;
}

.green .stat-icon {
  color: #67c23a;
}

/* 第二行内容区域与统计卡片之间的间距 */
.content-row {
  margin-top: 22px;
}

/* 下方两个信息面板样式 */
.panel-card {
  border: none;
  border-radius: 18px;
  min-height: 330px;
}

/* 面板标题区域 */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 17px;
  font-weight: 700;
  color: #1f2937;
}

/* 系统运行流程列表 */
.flow-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* 每一个流程项 */
.flow-item {
  display: flex;
  gap: 14px;
  padding: 16px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
}

/* 流程编号，例如 01、02 */
.flow-index {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, #409eff, #67c23a);
  color: white;
  font-weight: 800;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 流程标题 */
.flow-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
}

/* 流程说明 */
.flow-desc {
  margin-top: 6px;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.6;
}

/* 核心功能模块宫格 */
.module-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

/* 单个功能模块 */
.module-item {
  height: 78px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #374151;
  font-weight: 600;
}

/* 功能模块图标 */
.module-item .el-icon {
  font-size: 24px;
  color: #409eff;
}
</style>