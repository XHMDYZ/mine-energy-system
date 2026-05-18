<template>
  <!--
    同比 / 环比分析页面。

    该页面用于展示某台设备在指定月份的能耗对比情况：
    1. 同比：当前月份 vs 去年同月；
    2. 环比：当前月份 vs 上一个月。

    数据来源于后端接口：
      GET /api/energy/yoy
      GET /api/energy/mom
  -->
  <el-card class="page-card" shadow="never">
    <!-- 页面顶部标题区域 -->
    <template #header>
      <div class="header-row">
        <div>
          <div class="title">同比 / 环比分析</div>
          <div class="subtitle">
            对比设备当前月份与去年同期、上月的能耗变化情况，辅助判断能耗变化趋势
          </div>
        </div>

        <!-- 刷新按钮 -->
        <el-button type="primary" :icon="Refresh" @click="loadCompareData">
          刷新数据
        </el-button>
      </div>
    </template>

    <!-- 页面说明 -->
    <el-alert
      class="tip-alert"
      title="同比用于比较当前月份与去年同月的能耗变化，环比用于比较当前月份与上一个月的能耗变化。"
      type="info"
      show-icon
      :closable="false"
    />

    <!--
      查询条件区域。
      用户可以选择设备和统计月份。
    -->
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <div class="filter-title">查询条件</div>

        <!-- 设备选择 -->
        <el-select
          v-model="deviceId"
          class="device-select"
          placeholder="请选择设备"
        >
          <el-option label="设备1 - 主提升机" value="1" />
          <el-option label="设备2 - 主通风机" value="2" />
          <el-option label="设备3 - 排水泵" value="3" />
        </el-select>

        <!--
          月份选择。
          value-format="YYYY-MM" 表示绑定值为 2026-05 这种字符串。
        -->
        <el-date-picker
          v-model="month"
          type="month"
          value-format="YYYY-MM"
          placeholder="选择统计月份"
          class="month-picker"
        />

        <!-- 查询按钮 -->
        <el-button type="primary" :icon="Search" @click="loadCompareData">
          查询
        </el-button>

        <!-- 下载按钮 -->
        <el-button type="success" :icon="Download" @click="downloadCsv">
          下载结果
        </el-button>
      </div>
    </el-card>

    <!-- 顶部统计卡片 -->
    <el-row :gutter="18" class="summary-row">
      <!-- 当前设备 -->
      <el-col :span="8">
        <el-card class="summary-card blue" shadow="hover">
          <div class="summary-content">
            <div>
              <div class="summary-label">当前设备</div>
              <div class="summary-value device-name">{{ currentDeviceName }}</div>
            </div>
            <el-icon class="summary-icon"><Monitor /></el-icon>
          </div>
        </el-card>
      </el-col>

      <!-- 同比变化率 -->
      <el-col :span="8">
        <el-card class="summary-card orange" shadow="hover">
          <div class="summary-content">
            <div>
              <div class="summary-label">同比变化率</div>
              <div class="summary-value">{{ formatRate(yoyResult.change_rate) }}</div>
            </div>
            <el-icon class="summary-icon"><DataAnalysis /></el-icon>
          </div>
        </el-card>
      </el-col>

      <!-- 环比变化率 -->
      <el-col :span="8">
        <el-card class="summary-card green" shadow="hover">
          <div class="summary-content">
            <div>
              <div class="summary-label">环比变化率</div>
              <div class="summary-value">{{ formatRate(momResult.change_rate) }}</div>
            </div>
            <el-icon class="summary-icon"><TrendCharts /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-card class="chart-card" shadow="never">
      <template #header>
        <div class="table-header">
          <span>同比环比能耗对比图</span>
          <el-tag type="primary">Compare Chart</el-tag>
        </div>
      </template>

      <!-- ECharts 图表容器 -->
      <div ref="chartRef" class="chart"></div>
    </el-card>

    <!-- 结果明细区域 -->
    <el-row :gutter="18">
      <!-- 同比分析结果 -->
      <el-col :span="12">
        <el-card class="result-card" shadow="never">
          <template #header>
            <div class="table-header">
              <span>同比分析结果</span>
              <el-tag type="warning">YoY</el-tag>
            </div>
          </template>

          <div class="result-list">
            <div class="result-item">
              <span class="result-label">当前周期</span>
              <span class="result-value">{{ yoyResult.current_label || '-' }}</span>
            </div>

            <div class="result-item">
              <span class="result-label">对比周期</span>
              <span class="result-value">{{ yoyResult.compare_label || '-' }}</span>
            </div>

            <div class="result-item">
              <span class="result-label">当前能耗</span>
              <span class="result-value">{{ yoyResult.current_value || 0 }} kWh</span>
            </div>

            <div class="result-item">
              <span class="result-label">对比能耗</span>
              <span class="result-value">{{ yoyResult.compare_value || 0 }} kWh</span>
            </div>

            <div class="result-item">
              <span class="result-label">变化率</span>
              <el-tag :type="getRateTagType(yoyResult.change_rate)">
                {{ formatRate(yoyResult.change_rate) }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 环比分析结果 -->
      <el-col :span="12">
        <el-card class="result-card" shadow="never">
          <template #header>
            <div class="table-header">
              <span>环比分析结果</span>
              <el-tag type="success">MoM</el-tag>
            </div>
          </template>

          <div class="result-list">
            <div class="result-item">
              <span class="result-label">当前周期</span>
              <span class="result-value">{{ momResult.current_label || '-' }}</span>
            </div>

            <div class="result-item">
              <span class="result-label">对比周期</span>
              <span class="result-value">{{ momResult.compare_label || '-' }}</span>
            </div>

            <div class="result-item">
              <span class="result-label">当前能耗</span>
              <span class="result-value">{{ momResult.current_value || 0 }} kWh</span>
            </div>

            <div class="result-item">
              <span class="result-label">对比能耗</span>
              <span class="result-value">{{ momResult.compare_value || 0 }} kWh</span>
            </div>

            <div class="result-item">
              <span class="result-label">变化率</span>
              <el-tag :type="getRateTagType(momResult.change_rate)">
                {{ formatRate(momResult.change_rate) }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
/*
  ref：定义响应式变量；
  computed：根据当前数据计算设备名称；
  onMounted：页面加载后执行；
  onUnmounted：页面卸载时释放图表资源；
  nextTick：等待 DOM 渲染完成后再绘图。
*/
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'

/*
  axios 用于请求后端接口。
*/
import axios from 'axios'

/*
  echarts 用于绘制同比环比图表。
*/
import * as echarts from 'echarts'

/*
  Element Plus 消息提示。
*/
import { ElMessage } from 'element-plus'

/*
  Element Plus 图标。
*/
import {
  Refresh,
  Search,
  Download,
  Monitor,
  DataAnalysis,
  TrendCharts
} from '@element-plus/icons-vue'

/*
  chartRef 是图表 DOM 引用。
*/
const chartRef = ref(null)

/*
  chartInstance 保存 ECharts 实例。
*/
let chartInstance = null

/*
  当前选择的设备。
*/
const deviceId = ref('1')

/*
  获取当前月份，格式为 YYYY-MM。
*/
const getCurrentMonth = () => {
  const d = new Date()
  const year = d.getFullYear()
  const monthValue = String(d.getMonth() + 1).padStart(2, '0')
  return `${year}-${monthValue}`
}

/*
  当前选择的统计月份。
  默认使用当前月份。
*/
const month = ref(getCurrentMonth())

/*
  设备名称映射。
*/
const deviceNameMap = {
  '1': '主提升机',
  '2': '主通风机',
  '3': '排水泵'
}

/*
  当前设备名称。
*/
const currentDeviceName = computed(() => {
  return deviceNameMap[deviceId.value] || '-'
})

/*
  同比分析结果。
  后端返回字段包括：
    device_id
    device_name
    current_label
    compare_label
    current_value
    compare_value
    change_rate
*/
const yoyResult = ref({
  device_id: '',
  device_name: '',
  current_label: '',
  compare_label: '',
  current_value: 0,
  compare_value: 0,
  change_rate: 0
})

/*
  环比分析结果。
*/
const momResult = ref({
  device_id: '',
  device_name: '',
  current_label: '',
  compare_label: '',
  current_value: 0,
  compare_value: 0,
  change_rate: 0
})

/*
  formatRate 用于格式化变化率。
  例如：
    12.3456 -> 12.35%
    -5.2 -> -5.20%
*/
const formatRate = (rate) => {
  const value = Number(rate || 0)
  return `${value.toFixed(2)}%`
}

/*
  getRateTagType 根据变化率返回标签颜色。
  正增长：warning；
  下降：success；
  持平：info。
*/
const getRateTagType = (rate) => {
  const value = Number(rate || 0)

  if (value > 0) return 'warning'
  if (value < 0) return 'success'
  return 'info'
}

/*
  加载同比和环比数据。

  同比接口：
    GET /api/energy/yoy

  环比接口：
    GET /api/energy/mom

  请求参数：
    device_id：设备ID；
    month：统计月份。
*/
const loadCompareData = async () => {
  try {
    const params = {
      device_id: deviceId.value,
      month: month.value
    }

    /*
      同时请求同比和环比接口。
    */
    const [yoyRes, momRes] = await Promise.all([
      axios.get('http://127.0.0.1:8080/api/energy/yoy', { params }),
      axios.get('http://127.0.0.1:8080/api/energy/mom', { params })
    ])

    /*
      保存同比结果。
    */
    yoyResult.value = yoyRes.data.data || {
      current_value: 0,
      compare_value: 0,
      change_rate: 0
    }

    /*
      保存环比结果。
    */
    momResult.value = momRes.data.data || {
      current_value: 0,
      compare_value: 0,
      change_rate: 0
    }

    /*
      数据加载完成后绘制图表。
    */
    await nextTick()
    renderChart()
  } catch (err) {
    console.error('获取同比环比数据失败：', err)
    ElMessage.error('获取同比环比数据失败，请检查后端服务是否启动')
  }
}

/*
  renderChart 绘制同比环比对比图。
  图中包含：
    1. 当前周期能耗；
    2. 对比周期能耗；
    3. 变化率折线。
*/
const renderChart = () => {
  if (!chartRef.value) return

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const currentValues = [
    Number(yoyResult.value.current_value || 0),
    Number(momResult.value.current_value || 0)
  ]

  const compareValues = [
    Number(yoyResult.value.compare_value || 0),
    Number(momResult.value.compare_value || 0)
  ]

  const changeRates = [
    Number(yoyResult.value.change_rate || 0),
    Number(momResult.value.change_rate || 0)
  ]

  chartInstance.setOption({
    title: {
      text: `${currentDeviceName.value} ${month.value} 同比 / 环比分析`,
      left: 'center',
      top: 6,
      textStyle: {
        fontSize: 18,
        fontWeight: 700,
        color: '#1f2937'
      }
    },

    tooltip: {
      trigger: 'axis'
    },

    legend: {
      top: 40,
      data: ['当前周期能耗', '对比周期能耗', '变化率']
    },

    grid: {
      left: 60,
      right: 70,
      top: 95,
      bottom: 45
    },

    xAxis: {
      type: 'category',
      data: ['同比分析', '环比分析'],
      axisLabel: {
        color: '#6b7280'
      },
      axisLine: {
        lineStyle: {
          color: '#d1d5db'
        }
      }
    },

    yAxis: [
      {
        type: 'value',
        name: '能耗 / kWh',
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
      {
        type: 'value',
        name: '变化率 / %',
        axisLabel: {
          color: '#6b7280',
          formatter: '{value}%'
        }
      }
    ],

    series: [
      {
        name: '当前周期能耗',
        type: 'bar',
        barWidth: 34,
        data: currentValues,
        itemStyle: {
          color: '#409eff',
          borderRadius: [8, 8, 0, 0]
        }
      },
      {
        name: '对比周期能耗',
        type: 'bar',
        barWidth: 34,
        data: compareValues,
        itemStyle: {
          color: '#67c23a',
          borderRadius: [8, 8, 0, 0]
        }
      },
      {
        name: '变化率',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'circle',
        symbolSize: 9,
        data: changeRates,
        lineStyle: {
          width: 3,
          color: '#e6a23c'
        },
        itemStyle: {
          color: '#e6a23c'
        }
      }
    ]
  })
}

/*
  resizeChart 用于窗口变化时重绘图表尺寸。
*/
const resizeChart = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
}

/*
  CSV 单元格转义。
*/
const escapeCsvValue = (value) => {
  if (value === null || value === undefined) return ''

  const str = String(value).replace(/"/g, '""')

  if (str.includes(',') || str.includes('\n') || str.includes('"')) {
    return `"${str}"`
  }

  return str
}

/*
  下载同比环比结果为 CSV。
*/
const downloadCsv = () => {
  const rows = [
    {
      type: '同比分析',
      device_name: currentDeviceName.value,
      current_label: yoyResult.value.current_label,
      compare_label: yoyResult.value.compare_label,
      current_value: yoyResult.value.current_value,
      compare_value: yoyResult.value.compare_value,
      change_rate: formatRate(yoyResult.value.change_rate)
    },
    {
      type: '环比分析',
      device_name: currentDeviceName.value,
      current_label: momResult.value.current_label,
      compare_label: momResult.value.compare_label,
      current_value: momResult.value.current_value,
      compare_value: momResult.value.compare_value,
      change_rate: formatRate(momResult.value.change_rate)
    }
  ]

  const columns = [
    { label: '分析类型', prop: 'type' },
    { label: '设备名称', prop: 'device_name' },
    { label: '当前周期', prop: 'current_label' },
    { label: '对比周期', prop: 'compare_label' },
    { label: '当前能耗(kWh)', prop: 'current_value' },
    { label: '对比能耗(kWh)', prop: 'compare_value' },
    { label: '变化率', prop: 'change_rate' }
  ]

  const header = columns.map(col => escapeCsvValue(col.label)).join(',')

  const body = rows.map(row => {
    return columns.map(col => escapeCsvValue(row[col.prop])).join(',')
  }).join('\n')

  const csvContent = `\uFEFF${header}\n${body}`

  const blob = new Blob([csvContent], {
    type: 'text/csv;charset=utf-8;'
  })

  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = `同比环比分析_${currentDeviceName.value}_${month.value}.csv`
  link.click()

  URL.revokeObjectURL(url)

  ElMessage.success('同比环比分析结果下载成功')
}

/*
  页面加载完成后：
  1. 加载同比环比数据；
  2. 监听窗口变化，保证图表自适应。
*/
onMounted(() => {
  loadCompareData()
  window.addEventListener('resize', resizeChart)
})

/*
  页面卸载时：
  1. 移除窗口监听；
  2. 销毁 ECharts 图表实例。
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
.page-card {
  border-radius: 18px;
  border: none;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
}

.subtitle {
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}

.tip-alert {
  margin-bottom: 16px;
}

.filter-card {
  border-radius: 16px;
  border: 1px solid #eef2f7;
  margin-bottom: 18px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-title {
  font-weight: 700;
  color: #1f2937;
}

.device-select {
  width: 190px;
}

.month-picker {
  width: 180px;
}

.summary-row {
  margin-bottom: 18px;
}

.summary-card {
  border-radius: 16px;
  border: none;
}

.summary-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.summary-label {
  color: #6b7280;
  font-size: 14px;
}

.summary-value {
  margin-top: 8px;
  font-size: 30px;
  font-weight: 800;
  color: #1f2937;
}

.device-name {
  font-size: 24px;
}

.summary-icon {
  font-size: 44px;
  opacity: 0.2;
}

.blue {
  background: linear-gradient(135deg, #ffffff, #eaf3ff);
}

.orange {
  background: linear-gradient(135deg, #ffffff, #fff4e5);
}

.green {
  background: linear-gradient(135deg, #ffffff, #ecfdf3);
}

.blue .summary-icon {
  color: #409eff;
}

.orange .summary-icon {
  color: #e6a23c;
}

.green .summary-icon {
  color: #67c23a;
}

.chart-card,
.result-card {
  border-radius: 16px;
  border: 1px solid #eef2f7;
  margin-bottom: 18px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 700;
  color: #1f2937;
}

.chart {
  width: 100%;
  height: 430px;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
}

.result-label {
  color: #6b7280;
}

.result-value {
  color: #1f2937;
  font-weight: 700;
}
</style>