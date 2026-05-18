<template>
  <!--
    历史功率趋势图页面。
    该页面用于展示不同设备的历史功率变化情况，
    对应论文中的“历史趋势图”和“平台主要功能实现”部分。
  -->
  <el-card class="page-card" shadow="never">
    <!--
      卡片顶部标题区域。
      左侧显示页面标题和说明；
      右侧放置设备选择框和刷新按钮。
    -->
    <template #header>
      <div class="header-row">
        <div>
          <div class="title">历史功率趋势图</div>
          <div class="subtitle">
            展示清洗入库后的设备历史功率数据，用于观察设备运行变化趋势
          </div>
        </div>

        <!--
          查询工具栏。
          用户可以选择不同设备，并手动刷新趋势图。
        -->
        <div class="toolbar">
          <el-select
            v-model="deviceId"
            class="device-select"
            placeholder="请选择设备"
            @change="loadData"
          >
            <el-option label="设备1 - 主提升机" value="1" />
            <el-option label="设备2 - 主通风机" value="2" />
            <el-option label="设备3 - 排水泵" value="3" />
          </el-select>

          <el-button type="primary" @click="loadData">
            <el-icon><Refresh /></el-icon>
            <span>刷新数据</span>
          </el-button>
        </div>
      </div>
    </template>

    <!--
      页面提示信息。
      说明趋势图数据来自 energy_history 表。
    -->
    <el-alert
      class="tip-alert"
      title="趋势图数据来自清洗通过后的 energy_history 历史数据表。"
      type="info"
      show-icon
      :closable="false"
    />

    <!--
      当前设备说明卡片。
      这里展示当前选择的设备名称和数据条数，让页面信息更完整。
    -->
    <div class="summary-row">
      <div class="summary-item">
        <div class="summary-label">当前设备</div>
        <div class="summary-value">{{ deviceNameMap[deviceId] }}</div>
      </div>

      <div class="summary-item">
        <div class="summary-label">趋势数据条数</div>
        <div class="summary-value">{{ historyList.length }}</div>
      </div>

      <div class="summary-item">
        <div class="summary-label">数据来源</div>
        <div class="summary-value">energy_history</div>
      </div>
    </div>

    <!--
      ECharts 图表容器。
      ref="chartRef" 用于在 script 中获取 DOM 节点，
      然后通过 echarts.init(chartRef.value) 初始化图表。
    -->
    <div ref="chartRef" class="chart"></div>
  </el-card>
</template>

<script setup>
/*
  ref：定义响应式变量；
  onMounted：组件挂载后执行初始化逻辑；
  onUnmounted：组件卸载时清理事件；
  nextTick：等待 DOM 渲染完成后再初始化图表。
*/
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

/*
  axios 用于请求后端接口。
*/
import axios from 'axios'

/*
  echarts 用于绘制历史功率趋势折线图。
*/
import * as echarts from 'echarts'

/*
  ElMessage 是 Element Plus 的消息提示组件。
  当接口请求失败时，用它提示用户。
*/
import { ElMessage } from 'element-plus'

/*
  图表容器 DOM 引用。
  模板中的 <div ref="chartRef"> 会对应到这里。
*/
const chartRef = ref(null)

/*
  当前选择的设备 ID。
  默认显示设备1：主提升机。
*/
const deviceId = ref('1')

/*
  historyList 保存后端返回的历史数据列表。
  页面中的“趋势数据条数”会根据它显示。
*/
const historyList = ref([])

/*
  chartInstance 保存 ECharts 实例。
  这样后续刷新数据时不用重复创建图表，只需要更新配置。
*/
let chartInstance = null

/*
  设备 ID 和设备名称映射。
  用于动态显示图表标题和页面统计信息。
*/
const deviceNameMap = {
  '1': '主提升机',
  '2': '主通风机',
  '3': '排水泵'
}

/*
  加载历史数据并绘制趋势图。

  请求接口：
    GET http://127.0.0.1:8080/api/energy/history?device_id=设备ID

  对应后端：
    GetEnergyHistory

  对应数据库：
    energy_history
*/
const loadData = async () => {
  try {
    /*
      请求当前设备的历史数据。
      后端会根据 device_id 查询对应设备的最近历史记录。
    */
    const res = await axios.get(
      `http://127.0.0.1:8080/api/energy/history?device_id=${deviceId.value}`
    )

    /*
      后端返回的数据一般是按 history_id 倒序排列，
      也就是最新的数据在前面。
    */
    const list = res.data.data || []

    /*
      为了让折线图按照时间从左到右展示，
      这里需要把数据反转成从早到晚。
    */
    const data = [...list].reverse()

    /*
      保存到响应式变量中，用于页面显示趋势数据条数。
    */
    historyList.value = data

    /*
      等待 DOM 更新完成。
      如果页面刚进入时 chartRef 还没有渲染出来，
      直接初始化 ECharts 可能会失败。
    */
    await nextTick()

    /*
      如果图表实例不存在，则初始化图表。
      如果已经存在，就复用原来的图表实例。
    */
    if (!chartInstance) {
      chartInstance = echarts.init(chartRef.value)
    }

    /*
      提取横轴时间数据。
      record_time 是后端返回的历史记录时间。
    */
    const xData = data.map(item => item.record_time)

    /*
      提取纵轴功率数据。
      power 表示设备功率。
    */
    const powerData = data.map(item => item.power)

    /*
      设置图表配置。
      这里采用折线图 + 面积渐变背景，让趋势图更美观。
    */
    chartInstance.setOption({
      /*
        图表标题。
        根据当前设备动态变化。
      */
      title: {
        text: `${deviceNameMap[deviceId.value]} 功率趋势`,
        left: 'center',
        top: 5,
        textStyle: {
          fontSize: 18,
          fontWeight: 700,
          color: '#1f2937'
        }
      },

      /*
        鼠标悬停提示框。
        trigger: 'axis' 表示按坐标轴触发，
        鼠标移动到某个时间点时显示该时刻功率。
      */
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#e5e7eb',
        borderWidth: 1,
        textStyle: {
          color: '#374151'
        },
        formatter: params => {
          const item = params[0]
          return `
            <div style="font-weight: 700; margin-bottom: 6px;">${item.axisValue}</div>
            <div>功率：${item.data} kW</div>
          `
        }
      },

      /*
        图表网格区域。
        控制折线图距离卡片边缘的距离。
      */
      grid: {
        left: 55,
        right: 35,
        top: 70,
        bottom: 75
      },

      /*
        X 轴为采集时间。
      */
      xAxis: {
        type: 'category',
        data: xData,
        boundaryGap: false,
        axisLabel: {
          rotate: 30,
          color: '#6b7280'
        },
        axisLine: {
          lineStyle: {
            color: '#d1d5db'
          }
        },
        axisTick: {
          alignWithLabel: true
        }
      },

      /*
        Y 轴为功率值。
      */
      yAxis: {
        type: 'value',
        name: '功率 / kW',
        nameTextStyle: {
          color: '#6b7280'
        },
        axisLabel: {
          color: '#6b7280'
        },
        splitLine: {
          lineStyle: {
            type: 'dashed',
            color: '#e5e7eb'
          }
        }
      },

      /*
        数据缩放条。
        当历史数据较多时，可以拖动下方滑块查看局部趋势。
      */
      dataZoom: [
        {
          type: 'inside'
        },
        {
          type: 'slider',
          height: 22,
          bottom: 25
        }
      ],

      /*
        series 表示图表数据系列。
        这里使用一条平滑折线展示功率趋势。
      */
      series: [
        {
          name: '功率',
          type: 'line',
          smooth: true,
          symbol: 'circle',
          symbolSize: 7,
          data: powerData,

          /*
            折线样式。
          */
          lineStyle: {
            width: 3,
            color: '#409eff'
          },

          /*
            数据点样式。
          */
          itemStyle: {
            color: '#409eff'
          },

          /*
            面积样式。
            让折线下方出现淡蓝色渐变区域，看起来更像后台图表。
          */
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                {
                  offset: 0,
                  color: 'rgba(64, 158, 255, 0.28)'
                },
                {
                  offset: 1,
                  color: 'rgba(64, 158, 255, 0.02)'
                }
              ]
            }
          }
        }
      ]
    })
  } catch (err) {
    console.error('获取历史数据失败：', err)
    ElMessage.error('获取历史数据失败，请检查后端服务是否启动')
  }
}

/*
  resizeChart 用于浏览器窗口大小变化时重新调整图表尺寸。
  如果不处理，窗口变化后 ECharts 容器可能会出现显示异常。
*/
const resizeChart = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
}

/*
  页面挂载后执行：
  1. 加载历史数据；
  2. 监听浏览器窗口变化，让图表自适应宽度。
*/
onMounted(() => {
  loadData()
  window.addEventListener('resize', resizeChart)
})

/*
  页面卸载时执行：
  1. 移除窗口 resize 监听；
  2. 销毁 ECharts 实例，避免内存占用。
*/
onUnmounted(() => {
  window.removeEventListener('resize', resizeChart)

  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
/*
  页面外层卡片。
*/
.page-card {
  border-radius: 18px;
  border: none;
}

/*
  顶部标题和工具栏布局。
*/
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/*
  页面标题。
*/
.title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
}

/*
  页面说明文字。
*/
.subtitle {
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}

/*
  右侧工具栏布局。
*/
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

/*
  设备选择框宽度。
*/
.device-select {
  width: 190px;
}

/*
  提示信息区域。
*/
.tip-alert {
  margin-bottom: 16px;
}

/*
  设备摘要信息区域。
*/
.summary-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 18px;
}

/*
  单个摘要卡片。
*/
.summary-item {
  padding: 16px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
}

/*
  摘要标题。
*/
.summary-label {
  color: #6b7280;
  font-size: 13px;
}

/*
  摘要值。
*/
.summary-value {
  margin-top: 8px;
  color: #1f2937;
  font-size: 18px;
  font-weight: 700;
}

/*
  ECharts 图表容器。
  高度可以根据页面需要调整。
*/
.chart {
  width: 100%;
  height: 480px;
}
</style>
//这个页面是历史功率趋势图页面。用户可以选择主提升机、主通风机或排水泵，前端会调用后端 /api/energy/history 接口查询该设备的历史数据，
并使用 ECharts 绘制功率折线图。后端返回的是最近历史数据，前端会按时间顺序整理后展示，这样可以直观看到设备功率随时间的变化情况。