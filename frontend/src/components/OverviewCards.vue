<template>
  <div class="overview">
    <div class="card">
      <div class="label">设备总数</div>
      <div class="value">{{ overview.device_count }}</div>
    </div>

    <div class="card warning">
      <div class="label">报警总数</div>
      <div class="value">{{ overview.alarm_count }}</div>
    </div>

    <div class="card success">
      <div class="label">历史数据总数</div>
      <div class="value">{{ overview.history_count }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

const overview = ref({
  device_count: 0,
  alarm_count: 0,
  history_count: 0
})

let timer = null

const loadOverview = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8080/api/overview')
    overview.value = res.data.data || {
      device_count: 0,
      alarm_count: 0,
      history_count: 0
    }
  } catch (err) {
    console.error('获取首页概览失败：', err)
  }
}

onMounted(() => {
  loadOverview()
  timer = setInterval(() => {
    loadOverview()
  }, 5000)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<style scoped>
.overview {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.label {
  font-size: 16px;
  color: #666;
  margin-bottom: 10px;
}

.value {
  font-size: 32px;
  font-weight: bold;
  color: #333;
}

.warning .value {
  color: #e6a23c;
}

.success .value {
  color: #67c23a;
}
</style>