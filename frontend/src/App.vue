<template>
  <LoginPage v-if="!isLoggedIn" @login-success="onLoginSuccess" />

  <div v-else class="container">
    <h1>矿山设备能耗监测平台</h1>

    <div class="user-bar">
      <span>
        当前用户：{{ userInfo.real_name }}
        （{{ roleLabelMap[userInfo.role_name] || userInfo.role_name }}）
      </span>
      <button @click="logout">退出登录</button>
    </div>

    <OverviewCards v-if="hasMenu('overview')" />

    <div class="nav">
      <button
        v-for="item in visibleMenus"
        :key="item.key"
        :class="{ active: currentPage === item.key }"
        @click="currentPage = item.key"
      >
        {{ item.label }}
      </button>
    </div>

    <HistoryChart v-if="currentPage === 'history' && hasMenu('history')" />
    <AlarmList v-if="currentPage === 'alarms' && hasMenu('alarms')" />
    <DeviceManage v-if="currentPage === 'devices' && hasMenu('devices')" />
    <UserManage v-if="currentPage === 'users' && hasMenu('users')" />
    <ReportPage v-if="currentPage === 'reports' && hasMenu('reports')" />
    <EnergyRanking v-if="currentPage === 'ranking' && hasMenu('ranking')" />
    <CompareAnalysis v-if="currentPage === 'compare' && hasMenu('compare')" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import LoginPage from './components/LoginPage.vue'
import OverviewCards from './components/OverviewCards.vue'
import HistoryChart from './components/HistoryChart.vue'
import AlarmList from './components/AlarmList.vue'
import DeviceManage from './components/DeviceManage.vue'
import UserManage from './components/UserManage.vue'
import ReportPage from './components/ReportPage.vue'
import EnergyRanking from './components/EnergyRanking.vue'
import CompareAnalysis from './components/CompareAnalysis.vue'

const isLoggedIn = ref(false)
const userInfo = ref({})
const currentPage = ref('history')

const roleLabelMap = {
  admin: '系统管理员',
  monitor: '监测人员',
  manager: '管理人员'
}

const menuConfig = {
  admin: [
    { key: 'history', label: '历史趋势图' },
    { key: 'ranking', label: '能耗排行图' },
    { key: 'compare', label: '同比/环比分析' },
    { key: 'alarms', label: '报警列表' },
    { key: 'devices', label: '设备管理' },
    { key: 'users', label: '用户管理' },
    { key: 'reports', label: '报表管理' }
  ],
  monitor: [
    { key: 'history', label: '历史趋势图' },
    { key: 'alarms', label: '报警列表' }
  ],
  manager: [
    { key: 'history', label: '历史趋势图' },
    { key: 'ranking', label: '能耗排行图' },
    { key: 'compare', label: '同比/环比分析' },
    { key: 'reports', label: '报表管理' }
  ]
}

const defaultPageMap = {
  admin: 'history',
  monitor: 'history',
  manager: 'history'
}

const visibleMenus = computed(() => {
  const roleName = userInfo.value.role_name
  return menuConfig[roleName] || []
})

const hasMenu = (menuKey) => {
  if (menuKey === 'overview') {
    return ['admin', 'manager'].includes(userInfo.value.role_name)
  }

  return visibleMenus.value.some(item => item.key === menuKey)
}

const setDefaultPageByRole = () => {
  const roleName = userInfo.value.role_name
  currentPage.value = defaultPageMap[roleName] || 'history'
}

const onLoginSuccess = (data) => {
  userInfo.value = data
  isLoggedIn.value = true
  localStorage.setItem('userInfo', JSON.stringify(data))
  setDefaultPageByRole()
}

const logout = () => {
  localStorage.removeItem('userInfo')
  userInfo.value = {}
  isLoggedIn.value = false
  currentPage.value = 'history'
}

onMounted(() => {
  const saved = localStorage.getItem('userInfo')
  if (saved) {
    userInfo.value = JSON.parse(saved)
    isLoggedIn.value = true
    setDefaultPageByRole()
  }
})
</script>

<style>
body {
  margin: 0;
  font-family: Arial, sans-serif;
  background: #f5f7fa;
}

.container {
  padding: 20px;
}

h1 {
  text-align: center;
  margin-bottom: 20px;
}

.user-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  background: white;
  padding: 12px 16px;
  border-radius: 10px;
}

.user-bar button {
  padding: 8px 14px;
  border: none;
  background: #f56c6c;
  color: white;
  border-radius: 6px;
  cursor: pointer;
}

.nav {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.nav button {
  padding: 10px 18px;
  border: none;
  background: #409eff;
  color: white;
  border-radius: 6px;
  cursor: pointer;
}

.nav button:hover {
  background: #66b1ff;
}

.nav button.active {
  background: #1f78d1;
  font-weight: bold;
}
</style>