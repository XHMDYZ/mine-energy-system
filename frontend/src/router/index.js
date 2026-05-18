import { createRouter, createWebHistory } from 'vue-router'

import OverviewCards from '../components/OverviewCards.vue'
import HistoryChart from '../components/HistoryChart.vue'
import AlarmList from '../components/AlarmList.vue'
import DeviceManage from '../components/DeviceManage.vue'
import UserManage from '../components/UserManage.vue'
import EnergyRanking from '../components/EnergyRanking.vue'
import CompareAnalysis from '../components/CompareAnalysis.vue'
import ReportPage from '../components/ReportPage.vue'
import LoginPage from '../components/LoginPage.vue'

const routes = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/login',
    component: LoginPage
  },
  {
    path: '/overview',
    component: OverviewCards,
    meta: {
      roles: ['admin', 'manager', 'operator']
    }
  },
  {
    path: '/history',
    component: HistoryChart,
    meta: {
      roles: ['admin', 'manager', 'operator']
    }
  },
  {
    path: '/alarm',
    component: AlarmList,
    meta: {
      roles: ['admin', 'manager', 'operator']
    }
  },
  {
    path: '/ranking',
    component: EnergyRanking,
    meta: {
      roles: ['admin', 'manager']
    }
  },
  {
    path: '/compare',
    component: CompareAnalysis,
    meta: {
      roles: ['admin', 'manager']
    }
  },
  {
    path: '/device',
    component: DeviceManage,
    meta: {
      roles: ['admin', 'manager']
    }
  },
  {
    path: '/user',
    component: UserManage,
    meta: {
      roles: ['admin']
    }
  },
  {
    path: '/report',
    component: ReportPage,
    meta: {
      roles: ['admin', 'manager']
    }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/overview'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

/*
  路由权限守卫。
  作用：
  1. 未登录时，不能进入后台页面；
  2. 已登录但角色不匹配时，不能进入无权限页面；
  3. 比如 operator 手动输入 /user，也会被拦截回首页。
*/
router.beforeEach((to) => {
  const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}')
  const roleName = userInfo.role_name

  if (to.path === '/login') {
    return true
  }

  if (!roleName) {
    return '/login'
  }

  const allowRoles = to.meta.roles

  if (allowRoles && !allowRoles.includes(roleName)) {
    return '/overview'
  }

  return true
})

export default router