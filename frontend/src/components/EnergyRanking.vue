<template>
  <div class="card">
    <h2>设备能耗排行图</h2>

    <div class="toolbar">
      <label>开始日期：</label>
      <input v-model="startDate" type="date" />

      <label>结束日期：</label>
      <input v-model="endDate" type="date" />

      <button @click="loadRanking">查询排行</button>
    </div>

    <div ref="chartRef" class="chart"></div>

    <table>
      <thead>
        <tr>
          <th>排名</th>
          <th>设备ID</th>
          <th>设备名称</th>
          <th>总能耗</th>
          <th>平均功率</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(item, index) in rankingList" :key="item.device_id">
          <td>{{ index + 1 }}</td>
          <td>{{ item.device_id }}</td>
          <td>{{ item.device_name }}</td>
          <td>{{ item.total_energy }}</td>
          <td>{{ item.avg_power }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, onBeforeUnmount } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'

const chartRef = ref(null)
const rankingList = ref([])
let chartInstance = null

const today = new Date().toISOString().slice(0, 10)
const monthStart = today.slice(0, 8) + '01'

const startDate = ref(monthStart)
const endDate = ref(today)

const loadRanking = async () => {
  try {
    const res = await axios.get(
      `http://127.0.0.1:8080/api/energy/ranking?start_date=${startDate.value}&end_date=${endDate.value}`
    )

    rankingList.value = res.data.data || []

    await nextTick()

    if (!chartInstance) {
      chartInstance = echarts.init(chartRef.value)
    }

    chartInstance.setOption({
      title: {
        text: '设备能耗排行柱状图',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis'
      },
      xAxis: {
        type: 'category',
        data: rankingList.value.map(item => item.device_name)
      },
      yAxis: {
        type: 'value',
        name: '总能耗'
      },
      series: [
        {
          name: '总能耗',
          type: 'bar',
          data: rankingList.value.map(item => item.total_energy)
        }
      ]
    })
  } catch (err) {
    console.error('获取设备能耗排行失败：', err)
    alert('获取设备能耗排行失败')
  }
}

const resizeChart = () => {
  if (chartInstance) {
    chartInstance.resize()
  }
}

onMounted(() => {
  loadRanking()
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
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
  margin-bottom: 16px;
  flex-wrap: wrap;
}

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

.chart {
  width: 100%;
  height: 420px;
  margin-bottom: 20px;
}

table {
  width: 100%;
  border-collapse: collapse;
  background: white;
}

th,
td {
  border: 1px solid #ddd;
  padding: 10px;
  text-align: center;
}

th {
  background: #f2f2f2;
}
</style>