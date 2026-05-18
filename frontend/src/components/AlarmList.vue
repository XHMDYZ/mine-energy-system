<template>
  <!--
    报警列表页面。
    该页面用于展示后端 alarm_record 表中的报警记录，
    并支持有权限的用户对未处理报警进行处理。
  -->
  <el-card class="page-card" shadow="never">
    <!--
      卡片顶部标题区域。
      左侧显示页面标题和说明；
      右侧提供刷新按钮。
    -->
    <template #header>
      <div class="header-row">
        <div>
          <div class="title">报警列表</div>
          <div class="subtitle">
            展示融合异常检测生成的报警记录，并支持报警处理状态更新
          </div>
        </div>

        <!--
          刷新按钮。
          点击后重新请求后端 /api/alarms 接口。
        -->
        <el-button type="primary" :icon="Refresh" @click="loadAlarms">
          刷新报警
        </el-button>
      </div>
    </template>

    <!--
      顶部提示条。
      用于说明当前页面数据会自动刷新。
    -->
    <el-alert
      class="tip-alert"
      title="页面每 5 秒自动刷新一次，最新报警会自动显示在列表中。"
      type="info"
      show-icon
      :closable="false"
    />

    <!--
      Element Plus 表格组件。
      :data="alarms" 表示表格数据来自 alarms 数组。
      border 表示显示边框；
      stripe 表示隔行变色；
      v-loading 表示加载时显示加载动画。
    -->
    <el-table
      v-loading="loading"
      :data="alarms"
      border
      stripe
      style="width: 100%"
      class="alarm-table"
    >
      <!-- 报警编号 -->
      <el-table-column
        prop="alarm_id"
        label="报警ID"
        width="90"
        align="center"
      />

      <!-- 设备名称 -->
      <el-table-column
        prop="device_name"
        label="设备名称"
        width="120"
        align="center"
      />

      <!-- 报警类型，例如功率超限、变化率异常、历史偏差异常等 -->
      <el-table-column
        prop="alarm_type"
        label="报警类型"
        min-width="180"
        show-overflow-tooltip
      />

      <!--
        报警级别。
        使用 el-tag 标签展示，不同级别显示不同颜色。
      -->
      <el-table-column
        label="报警级别"
        width="110"
        align="center"
      >
        <template #default="{ row }">
          <el-tag :type="getLevelType(row.alarm_level)" effect="dark">
            {{ row.alarm_level }}
          </el-tag>
        </template>
      </el-table-column>

      <!--
        报警内容可能较长，使用 show-overflow-tooltip。
        鼠标悬停时可以看到完整内容。
      -->
      <el-table-column
        prop="alarm_content"
        label="报警内容"
        min-width="320"
        show-overflow-tooltip
      />

      <!-- 报警生成时间 -->
      <el-table-column
        prop="alarm_time"
        label="报警时间"
        width="170"
        align="center"
      />

      <!--
        处理状态。
        process_status = 0 表示未处理；
        process_status = 1 表示已处理。
      -->
      <el-table-column
        label="处理状态"
        width="110"
        align="center"
      >
        <template #default="{ row }">
          <el-tag :type="row.process_status === 0 ? 'warning' : 'success'">
            {{ row.process_status === 0 ? '未处理' : '已处理' }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 处理人 -->
      <el-table-column
        label="处理人"
        width="110"
        align="center"
      >
        <template #default="{ row }">
          {{ row.process_user || '-' }}
        </template>
      </el-table-column>

      <!-- 处理时间 -->
      <el-table-column
        label="处理时间"
        width="170"
        align="center"
      >
        <template #default="{ row }">
          {{ row.process_time || '-' }}
        </template>
      </el-table-column>

      <!--
        操作列。
        只有未处理报警，并且当前用户有处理权限时，才显示处理按钮。
      -->
      <el-table-column
        label="操作"
        width="130"
        align="center"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button
            v-if="row.process_status === 0 && canProcess"
            type="success"
            size="small"
            @click="handleProcess(row.alarm_id)"
          >
            处理
          </el-button>

          <span v-else class="empty">—</span>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
/*
  ref：定义响应式变量。
  computed：根据当前用户角色计算是否有报警处理权限。
  onMounted：组件加载完成后执行。
  onUnmounted：组件卸载时清除定时器。
*/
import { ref, onMounted, onUnmounted, computed } from 'vue'

/*
  axios：用于请求后端接口。
*/
import axios from 'axios'

/*
  ElMessage：Element Plus 消息提示组件。
  Refresh：刷新按钮图标。
*/
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

/*
  alarms 保存报警列表数据。
  后端 /api/alarms 返回的数据会写入该数组。
*/
const alarms = ref([])

/*
  loading 控制表格加载动画。
  请求报警列表时为 true，请求结束后改为 false。
*/
const loading = ref(false)

/*
  timer 保存定时器 ID。
  页面每 5 秒自动刷新报警数据，卸载时需要清除。
*/
let timer = null

/*
  从 localStorage 读取当前登录用户信息。
  登录成功后，系统会将用户信息保存到 localStorage。
  这里用于判断角色权限，以及处理报警时记录处理人。
*/
const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}')

/*
  报警处理权限。
  这里允许系统管理员、管理人员和值班员处理报警。
  如果你只想让管理员和值班员处理，可以删掉 manager。
*/
const canProcess = computed(() => {
  return ['admin', 'manager', 'operator'].includes(userInfo.role_name)
})

/*
  根据报警等级返回 Element Plus 标签类型。
  严重：红色 danger；
  重要：橙色 warning；
  一般：蓝色 primary。
*/
const getLevelType = (level) => {
  if (level === '严重') return 'danger'
  if (level === '重要') return 'warning'
  return 'primary'
}

/*
  加载报警列表。

  请求接口：
    GET http://127.0.0.1:8080/api/alarms

  后端返回：
    {
      message: "查询成功",
      data: [...]
    }

  对应后端：
    GetAlarmList
*/
const loadAlarms = async () => {
  loading.value = true

  try {
    const res = await axios.get('http://127.0.0.1:8080/api/alarms')
    alarms.value = res.data.data || []
  } catch (err) {
    console.error('获取报警失败', err)
    ElMessage.error('获取报警失败，请检查后端服务是否启动')
  } finally {
    loading.value = false
  }
}

/*
  处理报警。

  参数：
    alarmId：当前要处理的报警 ID。

  请求接口：
    PUT http://127.0.0.1:8080/api/alarms/:id/process

  请求体：
    {
      process_user: 当前用户名
    }

  对应后端：
    ProcessAlarm
*/
const handleProcess = async (alarmId) => {
  try {
    await axios.put(`http://127.0.0.1:8080/api/alarms/${alarmId}/process`, {
      process_user: userInfo.username || userInfo.real_name || 'unknown'
    })

    ElMessage.success('报警处理成功')

    /*
      处理成功后重新加载列表，
      这样页面可以立即看到“未处理”变成“已处理”。
    */
    loadAlarms()
  } catch (err) {
    console.error('处理报警失败', err)
    ElMessage.error('处理报警失败')
  }
}

/*
  页面挂载时执行：
  1. 立即加载一次报警列表；
  2. 设置定时器，每 5 秒自动刷新一次。
*/
onMounted(() => {
  loadAlarms()
  timer = setInterval(loadAlarms, 5000)
})

/*
  页面卸载时清除定时器。
  否则切换页面后，报警列表仍会继续请求后端接口。
*/
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
/*
  页面外层卡片样式。
  使用圆角和无边框，让页面更像后台系统。
*/
.page-card {
  border-radius: 18px;
  border: none;
}

/*
  卡片头部区域布局：
  左侧标题，右侧按钮。
*/
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 页面主标题 */
.title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
}

/* 页面副标题 */
.subtitle {
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}

/* 自动刷新提示条 */
.tip-alert {
  margin-bottom: 16px;
}

/* 表格样式微调 */
.alarm-table {
  border-radius: 12px;
  overflow: hidden;
}

/* 无操作时的占位符 */
.empty {
  color: #9ca3af;
}
</style>
//Alarm.vue 是报警列表页面。页面会调用后端 /api/alarms 接口获取报警记录，并以表格方式展示报警设备、报警类型、报警级别、报警内容和处理状态。
页面每5秒自动刷新一次，所以后端生成新报警后前端可以及时看到。对于 admin 和 monitor 角色，页面会显示“处理报警”按钮，
点击后调用 /api/alarms/:id/process 接口，把报警状态更新为已处理，并记录处理人和处理时间。