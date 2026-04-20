<template>
  <div class="card">
    <h2>历史功率趋势图</h2>

    <div class="toolbar">
      <label>选择设备：</label>
      <select v-model="deviceId" @change="loadData">
        <option value="1">设备1 - 主提升机</option>
        <option value="2">设备2 - 主通风机</option>
        <option value="3">设备3 - 排水泵</option>
      </select>

      <button @click="loadData">刷新数据</button>
    </div>

    <div ref="chartRef" class="chart"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const chartRef = ref(null)
const deviceId = ref('1')
let chartInstance = null

const deviceNameMap = {
  '1': '主提升机',
  '2': '主通风机',
  '3': '排水泵'
}

const loadData = async () => {
  try {
    const res = await axios.get(`http://127.0.0.1:8080/api/energy/history?device_id=${deviceId.value}`)
    const list = res.data.data || []

    const data = [...list].reverse()

    await nextTick()

    if (!chartInstance) {
      chartInstance = echarts.init(chartRef.value)
    }

    chartInstance.setOption({
      title: {
        text: `${deviceNameMap[deviceId.value]} 功率趋势图`,
        left: 'center'
      },
      tooltip: {
        trigger: 'axis'
      },
      xAxis: {
        type: 'category',
        data: data.map(item => item.record_time),
        axisLabel: {
          rotate: 30
        }
      },
      yAxis: {
        type: 'value',
        name: '功率'
      },
      series: [
        {
          name: '功率',
          type: 'line',
          smooth: true,
          data: data.map(item => item.power)
        }
      ]
    })
  } catch (err) {
    console.error('获取历史数据失败：', err)
  }
}

onMounted(() => {
  loadData()
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
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  justify-content: center;
  flex-wrap: wrap;
}

select {
  padding: 8px 12px;
  border: 1px solid #ccc;
  border-radius: 6px;
}

button {
  padding: 8px 16px;
  border: none;
  background: #67c23a;
  color: white;
  border-radius: 6px;
  cursor: pointer;
}

.chart {
  width: 100%;
  height: 450px;
}
</style>