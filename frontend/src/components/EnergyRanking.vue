<template>
  <!--
    设备能耗排行页面。
    该页面用于展示不同矿山设备在指定时间范围内的能耗对比情况。
    数据来自后端接口：
      GET /api/energy/ranking

    对应论文中的：
      平台主要功能实现 —— 设备能耗排行图
      能耗统计分析功能
  -->
  <el-card class="page-card" shadow="never">
    <!-- 页面顶部标题区域 -->
    <template #header>
      <div class="header-row">
        <div>
          <div class="title">设备能耗排行</div>
          <div class="subtitle">
            对比不同设备在指定时间范围内的总能耗和平均功率，辅助判断高耗能设备
          </div>
        </div>

        <!-- 刷新按钮 -->
        <el-button type="primary" :icon="Refresh" @click="loadRanking">
          刷新数据
        </el-button>
      </div>
    </template>

    <!-- 页面说明 -->
    <el-alert
      class="tip-alert"
      title="能耗排行数据基于 energy_history 表统计生成，总能耗按统计周期内累计能耗最大值与最小值之差计算。"
      type="info"
      show-icon
      :closable="false"
    />

    <!--
      查询条件区域。
      用户可以选择统计日期范围。
    -->
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <div class="filter-title">统计时间范围</div>

        <!--
          日期范围选择器。
          value-format="YYYY-MM-DD" 表示绑定值为字符串数组：
          ["2026-05-01", "2026-05-18"]
        -->
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          class="range-picker"
          clearable
        />

        <!-- 查询按钮 -->
        <el-button type="primary" :icon="Search" @click="loadRanking">
          查询
        </el-button>

        <!-- 下载按钮，将当前排行数据下载成 CSV 文件 -->
        <el-button type="success" :icon="Download" @click="downloadRankingCsv">
          下载排行
        </el-button>
      </div>
    </el-card>

    <!-- 顶部统计卡片 -->
    <el-row :gutter="18" class="summary-row">
      <el-col :span="8">
        <el-card class="summary-card blue" shadow="hover">
          <div class="summary-content">
            <div>
              <div class="summary-label">统计设备数</div>
              <div class="summary-value">{{ rankingList.length }}</div>
            </div>
            <el-icon class="summary-icon"><Monitor /></el-icon>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="summary-card green" shadow="hover">
          <div class="summary-content">
            <div>
              <div class="summary-label">最高能耗设备</div>
              <div class="summary-value device-name">{{ topDeviceName }}</div>
            </div>
            <el-icon class="summary-icon"><Histogram /></el-icon>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="summary-card orange" shadow="hover">
          <div class="summary-content">
            <div>
              <div class="summary-label">最高总能耗</div>
              <div class="summary-value">{{ topEnergy }}</div>
            </div>
            <el-icon class="summary-icon"><DataLine /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-card class="chart-card" shadow="never">
      <template #header>
        <div class="table-header">
          <span>能耗排行图</span>
          <el-tag type="primary">Ranking Chart</el-tag>
        </div>
      </template>

      <!--
        ECharts 容器。
        chartRef 用于在 script 中拿到 DOM 节点并初始化图表。
      -->
      <div ref="chartRef" class="chart"></div>
    </el-card>

    <!-- 表格区域 -->
    <el-card class="table-card" shadow="never">
      <template #header>
        <div class="table-header">
          <span>排行数据明细</span>
          <el-tag type="success">共 {{ rankingList.length }} 条</el-tag>
        </div>
      </template>

      <!--
        Element Plus 表格。
        展示每台设备的总能耗和平均功率。
      -->
      <el-table
        v-loading="loading"
        :data="rankingList"
        border
        stripe
        style="width: 100%"
        class="ranking-table"
        empty-text="暂无能耗排行数据"
      >
        <!-- 排名列 -->
        <el-table-column label="排名" width="90" align="center">
          <template #default="{ $index }">
            <el-tag :type="getRankTagType($index)">
              第 {{ $index + 1 }} 名
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="device_id" label="设备ID" width="100" align="center" />
        <el-table-column prop="device_name" label="设备名称" width="160" align="center" />

        <!-- 总能耗 -->
        <el-table-column label="总能耗" min-width="140" align="center">
          <template #default="{ row }">
            <span class="number-text">{{ row.total_energy }}</span>
            <span class="unit"> kWh</span>
          </template>
        </el-table-column>

        <!-- 平均功率 -->
        <el-table-column label="平均功率" min-width="140" align="center">
          <template #default="{ row }">
            <span class="number-text">{{ row.avg_power }}</span>
            <span class="unit"> kW</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </el-card>
</template>

<script setup>
/*
  ref：定义响应式变量；
  computed：根据排行数据计算最高能耗设备；
  onMounted：页面加载完成后执行；
  onUnmounted：页面卸载时释放图表资源；
  nextTick：等待 DOM 渲染完成后再绘图。
*/
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'

/*
  axios 用于请求后端接口。
*/
import axios from 'axios'

/*
  echarts 用于绘制能耗排行图。
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
  Histogram,
  DataLine
} from '@element-plus/icons-vue'

/*
  chartRef 是图表 DOM 容器引用。
*/
const chartRef = ref(null)

/*
  chartInstance 保存 ECharts 实例。
  后续刷新数据时复用该实例。
*/
let chartInstance = null

/*
  loading 控制表格加载状态。
*/
const loading = ref(false)

/*
  rankingList 保存后端返回的能耗排行数据。
  每条数据通常包括：
    device_id
    device_name
    total_energy
    avg_power
*/
const rankingList = ref([])

/*
  getToday 用于获取当前日期字符串，格式为 YYYY-MM-DD。
*/
const getToday = () => {
  const d = new Date()
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/*
  日期范围。
  默认统计当天数据。
*/
const dateRange = ref([getToday(), getToday()])

/*
  topDeviceName 计算最高能耗设备名称。
  如果没有数据，则显示“-”。
*/
const topDeviceName = computed(() => {
  if (!rankingList.value.length) return '-'
  return rankingList.value[0].device_name || '-'
})

/*
  topEnergy 计算最高总能耗。
*/
const topEnergy = computed(() => {
  if (!rankingList.value.length) return '0'
  return rankingList.value[0].total_energy || 0
})

/*
  根据排名返回标签颜色。
  第1名红色，第2名橙色，第3名绿色，其他为默认。
*/
const getRankTagType = (index) => {
  if (index === 0) return 'danger'
  if (index === 1) return 'warning'
  if (index === 2) return 'success'
  return 'info'
}

/*
  加载设备能耗排行数据。

  请求接口：
    GET http://127.0.0.1:8080/api/energy/ranking

  请求参数：
    start_date：开始日期；
    end_date：结束日期。

  对应后端：
    GetEnergyRanking
*/
const loadRanking = async () => {
  loading.value = true

  try {
    const startDate = dateRange.value?.[0] || getToday()
    const endDate = dateRange.value?.[1] || getToday()

    const res = await axios.get('http://127.0.0.1:8080/api/energy/ranking', {
      params: {
        start_date: startDate,
        end_date: endDate
      }
    })

    /*
      后端返回格式一般为：
      {
        message: "查询成功",
        data: [...]
      }
    */
    rankingList.value = res.data.data || []

    /*
      数据更新后重新绘制图表。
    */
    await nextTick()
    renderChart()
  } catch (err) {
    console.error('获取能耗排行失败：', err)
    ElMessage.error('获取能耗排行失败，请检查后端服务是否启动')
  } finally {
    loading.value = false
  }
}

/*
  renderChart 用于绘制设备能耗排行图。
  图中：
    柱状图表示总能耗；
    折线图表示平均功率。
*/
const renderChart = () => {
  if (!chartRef.value) return

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const deviceNames = rankingList.value.map(item => item.device_name)
  const totalEnergyData = rankingList.value.map(item => Number(item.total_energy || 0))
  const avgPowerData = rankingList.value.map(item => Number(item.avg_power || 0))

  chartInstance.setOption({
    title: {
      text: '设备能耗排行对比',
      left: 'center',
      top: 6,
      textStyle: {
        fontSize: 18,
        fontWeight: 700,
        color: '#1f2937'
      }
    },

    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },

    legend: {
      top: 40,
      data: ['总能耗', '平均功率']
    },

    grid: {
      left: 60,
      right: 60,
      top: 90,
      bottom: 45
    },

    xAxis: {
      type: 'category',
      data: deviceNames,
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
        name: '总能耗 / kWh',
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
        name: '平均功率 / kW',
        axisLabel: {
          color: '#6b7280'
        }
      }
    ],

    series: [
      {
        name: '总能耗',
        type: 'bar',
        barWidth: 42,
        data: totalEnergyData,
        itemStyle: {
          color: '#409eff',
          borderRadius: [8, 8, 0, 0]
        }
      },
      {
        name: '平均功率',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        data: avgPowerData,
        lineStyle: {
          width: 3,
          color: '#67c23a'
        },
        itemStyle: {
          color: '#67c23a'
        }
      }
    ]
  })
}

/*
  resizeChart 用于浏览器窗口大小变化时调整图表大小。
*/
const resizeChart = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
}

/*
  CSV 转义函数。
  防止字段中包含逗号、换行或双引号时导出异常。
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
  下载能耗排行数据为 CSV 文件。
  Excel 可以直接打开 CSV 文件。
*/
const downloadRankingCsv = () => {
  if (!rankingList.value.length) {
    ElMessage.warning('当前没有可下载的排行数据')
    return
  }

  const columns = [
    { label: '排名', prop: 'rank' },
    { label: '设备ID', prop: 'device_id' },
    { label: '设备名称', prop: 'device_name' },
    { label: '总能耗(kWh)', prop: 'total_energy' },
    { label: '平均功率(kW)', prop: 'avg_power' }
  ]

  const rows = rankingList.value.map((item, index) => ({
    rank: index + 1,
    ...item
  }))

  const header = columns.map(col => escapeCsvValue(col.label)).join(',')

  const body = rows.map(row => {
    return columns.map(col => escapeCsvValue(row[col.prop])).join(',')
  }).join('\n')

  /*
    \uFEFF 是 BOM 头，防止 Excel 打开中文 CSV 时乱码。
  */
  const csvContent = `\uFEFF${header}\n${body}`

  const blob = new Blob([csvContent], {
    type: 'text/csv;charset=utf-8;'
  })

  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  const startDate = dateRange.value?.[0] || '开始'
  const endDate = dateRange.value?.[1] || '结束'

  link.href = url
  link.download = `设备能耗排行_${startDate}_${endDate}.csv`
  link.click()

  URL.revokeObjectURL(url)

  ElMessage.success('能耗排行下载成功')
}

/*
  页面加载完成后：
  1. 加载排行数据；
  2. 监听窗口变化，让图表自适应。
*/
onMounted(() => {
  loadRanking()
  window.addEventListener('resize', resizeChart)
})

/*
  页面卸载时：
  1. 移除窗口监听；
  2. 销毁图表实例。
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

.range-picker {
  width: 300px;
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

.green {
  background: linear-gradient(135deg, #ffffff, #ecfdf3);
}

.orange {
  background: linear-gradient(135deg, #ffffff, #fff4e5);
}

.blue .summary-icon {
  color: #409eff;
}

.green .summary-icon {
  color: #67c23a;
}

.orange .summary-icon {
  color: #e6a23c;
}

.chart-card,
.table-card {
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

.ranking-table {
  border-radius: 12px;
  overflow: hidden;
}

.number-text {
  font-weight: 700;
  color: #1f2937;
}

.unit {
  color: #6b7280;
}
</style>