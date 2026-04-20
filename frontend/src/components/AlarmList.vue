<template>
  <div class="card">
    <h2>报警列表</h2>

    <div class="toolbar">
      <button @click="loadAlarms">刷新报警</button>
      <span class="tip">每 5 秒自动刷新一次</span>
    </div>

    <table>
      <thead>
        <tr>
          <th>报警ID</th>
          <th>设备ID</th>
          <th>设备名称</th>
          <th>报警类型</th>
          <th>报警级别</th>
          <th>报警内容</th>
          <th>报警时间</th>
          <th>处理状态</th>
          <th>处理人</th>
          <th>处理时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in alarms" :key="item.alarm_id">
          <td>{{ item.alarm_id }}</td>
          <td>{{ item.device_id }}</td>
          <td>{{ item.device_name }}</td>
          <td>{{ item.alarm_type }}</td>
          <td>
            <span :class="['level-tag', item.alarm_level === '严重' ? 'danger' : 'normal']">
              {{ item.alarm_level }}
            </span>
          </td>
          <td>{{ item.alarm_content }}</td>
          <td>{{ item.alarm_time }}</td>
          <td>
            <span :class="item.process_status === 0 ? 'status-wait' : 'status-done'">
              {{ item.process_status === 0 ? '未处理' : '已处理' }}
            </span>
          </td>
          <td>{{ item.process_user || '-' }}</td>
          <td>{{ item.process_time || '-' }}</td>
          <td>
            <button
              v-if="item.process_status === 0 && canProcess"
              class="process-btn"
              @click="handleProcess(item.alarm_id)"
            >
              处理报警
            </button>
            <span v-else>—</span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import axios from 'axios'

const alarms = ref([])
let timer = null

const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}')

const canProcess = computed(() => {
  return ['admin', 'monitor'].includes(userInfo.role_name)
})

const loadAlarms = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8080/api/alarms')
    alarms.value = res.data.data || []
  } catch (err) {
    console.error('获取报警失败', err)
  }
}

const handleProcess = async (alarmId) => {
  try {
    await axios.put(`http://127.0.0.1:8080/api/alarms/${alarmId}/process`, {
      process_user: userInfo.username || userInfo.real_name || 'unknown'
    })
    alert('报警处理成功')
    loadAlarms()
  } catch (err) {
    console.error('处理报警失败', err)
    alert('处理报警失败')
  }
}

onMounted(() => {
  loadAlarms()
  timer = setInterval(() => {
    loadAlarms()
  }, 5000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
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
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

button {
  padding: 8px 16px;
  border: none;
  background: #e6a23c;
  color: white;
  border-radius: 6px;
  cursor: pointer;
}

.tip {
  color: #666;
  font-size: 14px;
}

.process-btn {
  background: #67c23a;
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

.level-tag {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  color: white;
}

.danger {
  background: #f56c6c;
}

.normal {
  background: #409eff;
}

.status-wait {
  color: #e6a23c;
  font-weight: bold;
}

.status-done {
  color: #67c23a;
  font-weight: bold;
}
</style>