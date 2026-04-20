<template>
  <div class="card">
    <h2>报表管理</h2>

    <div class="tab-row">
      <button :class="{ active: reportType === 'daily' }" @click="reportType = 'daily'">日报表</button>
      <button :class="{ active: reportType === 'monthly' }" @click="reportType = 'monthly'">月报表</button>
      <button :class="{ active: reportType === 'alarm' }" @click="reportType = 'alarm'">异常统计报表</button>
    </div>

    <div class="filter-box">
      <template v-if="reportType === 'daily'">
        <label>日期：</label>
        <input v-model="dailyDate" type="date" />
        <button @click="loadDailyReport">查询日报表</button>
      </template>

      <template v-if="reportType === 'monthly'">
        <label>月份：</label>
        <input v-model="monthlyDate" type="month" />
        <button @click="loadMonthlyReport">查询月报表</button>
      </template>

      <template v-if="reportType === 'alarm'">
        <label>开始日期：</label>
        <input v-model="alarmStartDate" type="date" />
        <label>结束日期：</label>
        <input v-model="alarmEndDate" type="date" />
        <button @click="loadAlarmReport">查询异常统计</button>
      </template>

      <button class="export-btn" @click="exportCsv">导出 CSV</button>
    </div>

    <table v-if="reportType === 'daily'">
      <thead>
        <tr>
          <th>设备ID</th>
          <th>设备名称</th>
          <th>统计日期</th>
          <th>当日总能耗</th>
          <th>平均功率</th>
          <th>最大功率</th>
          <th>最小功率</th>
          <th>报警次数</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in reportList" :key="item.device_id">
          <td>{{ item.device_id }}</td>
          <td>{{ item.device_name }}</td>
          <td>{{ item.stat_date }}</td>
          <td>{{ item.total_energy }}</td>
          <td>{{ item.avg_power }}</td>
          <td>{{ item.max_power }}</td>
          <td>{{ item.min_power }}</td>
          <td>{{ item.alarm_count }}</td>
        </tr>
      </tbody>
    </table>

    <table v-if="reportType === 'monthly'">
      <thead>
        <tr>
          <th>设备ID</th>
          <th>设备名称</th>
          <th>统计月份</th>
          <th>月总能耗</th>
          <th>平均功率</th>
          <th>最大功率</th>
          <th>最小功率</th>
          <th>报警次数</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in reportList" :key="item.device_id">
          <td>{{ item.device_id }}</td>
          <td>{{ item.device_name }}</td>
          <td>{{ item.stat_month }}</td>
          <td>{{ item.total_energy }}</td>
          <td>{{ item.avg_power }}</td>
          <td>{{ item.max_power }}</td>
          <td>{{ item.min_power }}</td>
          <td>{{ item.alarm_count }}</td>
        </tr>
      </tbody>
    </table>

    <table v-if="reportType === 'alarm'">
      <thead>
        <tr>
          <th>设备ID</th>
          <th>设备名称</th>
          <th>报警总数</th>
          <th>未处理数</th>
          <th>严重报警数</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in reportList" :key="item.device_id">
          <td>{{ item.device_id }}</td>
          <td>{{ item.device_name }}</td>
          <td>{{ item.alarm_count }}</td>
          <td>{{ item.unprocessed_count }}</td>
          <td>{{ item.severe_count }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const reportType = ref('daily')
const reportList = ref([])

const today = new Date().toISOString().slice(0, 10)
const currentMonth = today.slice(0, 7)

const dailyDate = ref(today)
const monthlyDate = ref(currentMonth)
const alarmStartDate = ref(today)
const alarmEndDate = ref(today)

const loadDailyReport = async () => {
  try {
    const res = await axios.get(`http://127.0.0.1:8080/api/reports/daily?date=${dailyDate.value}`)
    reportList.value = res.data.data || []
  } catch (err) {
    console.error('获取日报表失败：', err)
    alert('获取日报表失败')
  }
}

const loadMonthlyReport = async () => {
  try {
    const res = await axios.get(`http://127.0.0.1:8080/api/reports/monthly?month=${monthlyDate.value}`)
    reportList.value = res.data.data || []
  } catch (err) {
    console.error('获取月报表失败：', err)
    alert('获取月报表失败')
  }
}

const loadAlarmReport = async () => {
  try {
    const res = await axios.get(
      `http://127.0.0.1:8080/api/reports/alarm-stats?start_date=${alarmStartDate.value}&end_date=${alarmEndDate.value}`
    )
    reportList.value = res.data.data || []
  } catch (err) {
    console.error('获取异常统计报表失败：', err)
    alert('获取异常统计报表失败')
  }
}

const exportCsv = () => {
  if (!reportList.value.length) {
    alert('当前没有可导出的数据')
    return
  }

  let headers = []
  let rows = []

  if (reportType.value === 'daily') {
    headers = ['设备ID', '设备名称', '统计日期', '当日总能耗', '平均功率', '最大功率', '最小功率', '报警次数']
    rows = reportList.value.map(item => [
      item.device_id,
      item.device_name,
      item.stat_date,
      item.total_energy,
      item.avg_power,
      item.max_power,
      item.min_power,
      item.alarm_count
    ])
  }

  if (reportType.value === 'monthly') {
    headers = ['设备ID', '设备名称', '统计月份', '月总能耗', '平均功率', '最大功率', '最小功率', '报警次数']
    rows = reportList.value.map(item => [
      item.device_id,
      item.device_name,
      item.stat_month,
      item.total_energy,
      item.avg_power,
      item.max_power,
      item.min_power,
      item.alarm_count
    ])
  }

  if (reportType.value === 'alarm') {
    headers = ['设备ID', '设备名称', '报警总数', '未处理数', '严重报警数']
    rows = reportList.value.map(item => [
      item.device_id,
      item.device_name,
      item.alarm_count,
      item.unprocessed_count,
      item.severe_count
    ])
  }

  const csvContent =
    '\ufeff' +
    [headers, ...rows]
      .map(row => row.map(cell => `"${cell ?? ''}"`).join(','))
      .join('\n')

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)

  link.href = url
  link.download = `${reportType.value}_report.csv`
  link.click()

  URL.revokeObjectURL(url)
}

onMounted(() => {
  loadDailyReport()
})
</script>

<style scoped>
.card {
  background: white;
  padding: 20px;
  border-radius: 10px;
}

.tab-row {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.tab-row button,
.filter-box button {
  padding: 8px 14px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  color: white;
  background: #409eff;
}

.tab-row button.active {
  background: #1f78d1;
}

.filter-box {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.filter-box input {
  padding: 8px;
  border: 1px solid #ccc;
  border-radius: 6px;
}

.export-btn {
  background: #67c23a !important;
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