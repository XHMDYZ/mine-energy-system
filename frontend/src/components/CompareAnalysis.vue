<template>
  <div class="card">
    <h2>同比 / 环比分析图</h2>

    <div class="toolbar">
      <label>选择设备：</label>
      <select v-model="deviceId">
        <option v-for="item in deviceList" :key="item.device_id" :value="item.device_id">
          {{ item.device_name }}
        </option>
      </select>

      <label>选择月份：</label>
      <input v-model="month" type="month" />

      <button @click="loadCompareData">查询分析</button>
    </div>

    <div class="summary-row">
      <div class="summary-card">
        <div class="title">同比增长率</div>
        <div class="value">{{ yoyData.change_rate?.toFixed(2) || '0.00' }}%</div>
      </div>
      <div class="summary-card">
        <div class="title">环比增长率</div>
        <div class="value">{{ momData.change_rate?.toFixed(2) || '0.00' }}%</div>
      </div>
    </div>

    <div class="chart-block">
      <h3>同比分析图</h3>
      <div ref="yoyChartRef" class="chart"></div>
    </div>

    <div class="chart-block">
      <h3>环比分析图</h3>
      <div ref="momChartRef" class="chart"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, onBeforeUnmount } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const deviceList = ref([])
const today = new Date().toISOString().slice(0, 7)
const month = ref(today)
const deviceId = ref(1)

const yoyData = ref({})
const momData = ref({})

const yoyChartRef = ref(null)
const momChartRef = ref(null)

let yoyChart = null
let momChart = null

const loadDevices = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8080/api/devices')
    deviceList.value = res.data.data || []
    if (deviceList.value.length > 0) {
      deviceId.value = deviceList.value[0].device_id
    }
  } catch (err) {
    console.error('获取设备列表失败：', err)
  }
}

const loadCompareData = async () => {
  try {
    const [yoyRes, momRes] = await Promise.all([
      axios.get(`http://127.0.0.1:8080/api/energy/yoy?device_id=${deviceId.value}&month=${month.value}`),
      axios.get(`http://127.0.0.1:8080/api/energy/mom?device_id=${deviceId.value}&month=${month.value}`)
    ])

    yoyData.value = yoyRes.data.data || {}
    momData.value = momRes.data.data || {}

    await nextTick()
    renderCharts()
  } catch (err) {
    console.error('获取同比环比数据失败：', err)
    alert('获取同比环比数据失败')
  }
}

const renderCharts = () => {
  if (!yoyChart) {
    yoyChart = echarts.init(yoyChartRef.value)
  }
  if (!momChart) {
    momChart = echarts.init(momChartRef.value)
  }

  yoyChart.setOption({
    title: {
      text: `${yoyData.value.device_name || ''} 同比分析`,
      left: 'center'
    },
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: [yoyData.value.compare_label, yoyData.value.current_label]
    },
    yAxis: {
      type: 'value',
      name: '总能耗'
    },
    series: [
      {
        name: '总能耗',
        type: 'bar',
        data: [yoyData.value.compare_value || 0, yoyData.value.current_value || 0]
      }
    ]
  })

  momChart.setOption({
    title: {
      text: `${momData.value.device_name || ''} 环比分析`,
      left: 'center'
    },
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: [momData.value.compare_label, momData.value.current_label]
    },
    yAxis: {
      type: 'value',
      name: '总能耗'
    },
    series: [
      {
        name: '总能耗',
        type: 'bar',
        data: [momData.value.compare_value || 0, momData.value.current_value || 0]
      }
    ]
  })
}

const resizeCharts = () => {
  if (yoyChart) yoyChart.resize()
  if (momChart) momChart.resize()
}

onMounted(async () => {
  await loadDevices()
  await loadCompareData()
  window.addEventListener('resize', resizeCharts)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  if (yoyChart) {
    yoyChart.dispose()
    yoyChart = null
  }
  if (momChart) {
    momChart.dispose()
    momChart = null
  }
})
</script>

<style scoped>
.card {
  background: white;
  padding: 20px;
  border-radius: 10px;
}

.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.toolbar select,
.toolbar input {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 6px;
}

.toolbar button {
  padding: 8px 14px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  color: white;
  background: #409eff;
}

.summary-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.summary-card {
  flex: 1;
  min-width: 220px;
  background: #f8f9fb;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
}

.summary-card .title {
  color: #666;
  margin-bottom: 10px;
}

.summary-card .value {
  font-size: 28px;
  font-weight: bold;
  color: #333;
}

.chart-block {
  margin-bottom: 24px;
}

.chart {
  width: 100%;
  height: 400px;
}
</style>