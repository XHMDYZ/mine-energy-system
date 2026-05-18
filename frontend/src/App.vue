<template>
  <!-- 登录页单独显示，不带左侧菜单和顶部栏 -->
  <router-view v-if="isLoginPage" />

  <!-- 后台主布局 -->
  <el-container v-else class="app-layout">
    <el-aside width="230px" class="sidebar">
      <div class="logo-box">
        <div class="logo-icon">矿</div>

        <div>
          <div class="logo-title">矿山能耗平台</div>
          <div class="logo-subtitle">Energy Monitor</div>
        </div>
      </div>

      <!-- 根据当前角色动态渲染菜单 -->
      <el-menu
        router
        class="side-menu"
        background-color="#14213d"
        text-color="#cfd8e3"
        active-text-color="#ffffff"
        :default-active="$route.path"
      >
        <el-menu-item
          v-for="item in visibleMenus"
          :key="item.path"
          :index="item.path"
        >
          <el-icon>
            <component :is="item.icon" />
          </el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div>
          <div class="page-title">基于 Web 的矿山设备能耗监测与分析平台</div>
          <div class="page-desc">
            OPC UA 数据接入 · 数据清洗 · 融合异常检测 · LSTM 辅助分析
          </div>
        </div>

        <div class="right-box">
          <div class="role-tag">
            {{ roleText }}
          </div>

          <div class="user-box">
            <el-icon><UserFilled /></el-icon>
            <span>{{ username }}</span>
          </div>

          <el-button size="small" type="danger" plain @click="logout">
            退出登录
          </el-button>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const isLoginPage = computed(() => {
  return route.path === '/login'
})

const currentUserInfo = computed(() => {
  route.path
  return JSON.parse(localStorage.getItem('userInfo') || '{}')
})

const currentRole = computed(() => {
  return currentUserInfo.value.role_name || ''
})

const username = computed(() => {
  return currentUserInfo.value.real_name || currentUserInfo.value.username || '未登录'
})

const roleText = computed(() => {
  if (currentRole.value === 'admin') return '系统管理员'
  if (currentRole.value === 'manager') return '管理人员'
  if (currentRole.value === 'operator') return '值班员'
  return '未登录'
})

/*
  菜单权限配置：
  admin：全部功能
  manager：统计分析、设备管理、报警、报表
  operator：首页、历史趋势、报警列表
*/
const allMenus = [
  {
    path: '/overview',
    title: '首页概览',
    icon: 'DataBoard',
    roles: ['admin', 'manager', 'operator']
  },
  {
    path: '/history',
    title: '历史趋势',
    icon: 'TrendCharts',
    roles: ['admin', 'manager', 'operator']
  },
  {
    path: '/alarm',
    title: '报警列表',
    icon: 'Warning',
    roles: ['admin', 'manager', 'operator']
  },
  {
    path: '/ranking',
    title: '能耗排行',
    icon: 'Histogram',
    roles: ['admin', 'manager']
  },
  {
    path: '/compare',
    title: '同比环比分析',
    icon: 'DataAnalysis',
    roles: ['admin', 'manager']
  },
  {
    path: '/device',
    title: '设备管理',
    icon: 'Monitor',
    roles: ['admin', 'manager']
  },
  {
    path: '/user',
    title: '用户管理',
    icon: 'User',
    roles: ['admin']
  },
  {
    path: '/report',
    title: '报表分析',
    icon: 'Document',
    roles: ['admin', 'manager']
  }
]

const visibleMenus = computed(() => {
  return allMenus.filter(item => item.roles.includes(currentRole.value))
})

const logout = () => {
  localStorage.removeItem('userInfo')
  router.push('/login')
}
</script>

<style scoped>
.app-layout {
  min-height: 100vh;
  background: #f3f6fb;
}

.sidebar {
  background: #14213d;
  color: white;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.12);
}

.logo-box {
  height: 72px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.logo-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  background: linear-gradient(135deg, #409eff, #67c23a);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}

.logo-title {
  font-size: 17px;
  font-weight: 700;
}

.logo-subtitle {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 2px;
}

.side-menu {
  border-right: none;
}

.side-menu :deep(.el-menu-item) {
  margin: 6px 10px;
  border-radius: 10px;
}

.side-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, #409eff, #337ecc);
}

.topbar {
  height: 72px;
  background: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 26px;
  box-shadow: 0 2px 12px rgba(20, 33, 61, 0.06);
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
}

.page-desc {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
}

.right-box {
  display: flex;
  align-items: center;
  gap: 12px;
}

.role-tag {
  color: #409eff;
  background: #ecf5ff;
  padding: 7px 12px;
  border-radius: 18px;
  font-size: 13px;
  font-weight: 700;
}

.user-box {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #374151;
  background: #f3f6fb;
  padding: 8px 14px;
  border-radius: 20px;
}

.main-content {
  padding: 22px;
  background: #f3f6fb;
}
</style>