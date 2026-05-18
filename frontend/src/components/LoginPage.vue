<template>
  <div class="login-page">
    <div class="login-left">
      <div class="brand">
        <div class="brand-icon">矿</div>
        <div>
          <div class="brand-title">矿山设备能耗监测与分析平台</div>
          <div class="brand-subtitle">Mine Energy Monitoring System</div>
        </div>
      </div>

      <div class="intro">
        <h1>设备能耗监测 · 数据清洗 · 异常报警</h1>
        <p>
          面向矿山设备能耗管理场景，平台支持 OPC UA 数据接入、能耗历史趋势展示、
          融合异常检测、报警处理和报表统计分析。
        </p>
      </div>

      <div class="feature-list">
        <div class="feature-item">
          <el-icon><Connection /></el-icon>
          <span>OPC UA 仿真接入</span>
        </div>

        <div class="feature-item">
          <el-icon><DataLine /></el-icon>
          <span>历史能耗趋势分析</span>
        </div>

        <div class="feature-item">
          <el-icon><Warning /></el-icon>
          <span>融合异常检测与报警</span>
        </div>

        <div class="feature-item">
          <el-icon><Cpu /></el-icon>
          <span>LSTM 辅助异常识别</span>
        </div>
      </div>
    </div>

    <div class="login-right">
      <el-card class="login-card" shadow="never">
        <div class="login-header">
          <div class="login-title">系统登录</div>
          <div class="login-subtitle">请输入账号和密码进入平台</div>
        </div>

        <el-form
          :model="form"
          class="login-form"
          @keyup.enter="handleLogin"
        >
          <el-form-item>
            <el-input
              v-model="form.username"
              size="large"
              placeholder="请输入用户名"
              clearable
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item>
            <el-input
              v-model="form.password"
              size="large"
              type="password"
              show-password
              placeholder="请输入密码"
              clearable
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-button
            class="login-btn"
            type="primary"
            size="large"
            :loading="loading"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form>

        <div class="demo-tip">
          账号角色示例：admin / manager / operator
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const router = useRouter()

const form = ref({
  username: '',
  password: ''
})

const loading = ref(false)

const validateForm = () => {
  if (!form.value.username) {
    ElMessage.warning('请输入用户名')
    return false
  }

  if (!form.value.password) {
    ElMessage.warning('请输入密码')
    return false
  }

  return true
}

/*
  角色解析：
  1. 优先使用后端返回的 role_name；
  2. 如果后端没有返回 role_name，则根据用户名兜底映射；
  3. 这样避免所有用户默认变成 admin。
*/
const getRoleName = (data) => {
  if (data.role_name) return data.role_name
  if (data.roleName) return data.roleName
  if (data.role) return data.role

  const usernameRoleMap = {
    admin: 'admin',
    manager: 'manager',
    operator: 'operator'
  }

  return usernameRoleMap[form.value.username] || 'operator'
}

const handleLogin = async () => {
  if (!validateForm()) return

  loading.value = true

  try {
    const res = await axios.post('http://127.0.0.1:8080/api/login', {
      username: form.value.username,
      password: form.value.password
    })

    const data = res.data.data || res.data.user || res.data || {}

    const userInfo = {
      username: data.username || form.value.username,
      real_name: data.real_name || data.realName || '',
      role_name: getRoleName(data),
      role_id: data.role_id || data.roleId || ''
    }

    localStorage.setItem('userInfo', JSON.stringify(userInfo))

    ElMessage.success('登录成功')
    router.push('/overview')
  } catch (err) {
    console.error('登录失败：', err)
    ElMessage.error('登录失败，请检查用户名或密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  background: #f3f6fb;
}

.login-left {
  position: relative;
  padding: 56px 70px;
  color: white;
  background:
    linear-gradient(135deg, rgba(20, 33, 61, 0.96), rgba(25, 80, 150, 0.92)),
    radial-gradient(circle at 20% 20%, rgba(64, 158, 255, 0.35), transparent 35%),
    radial-gradient(circle at 80% 75%, rgba(103, 194, 58, 0.25), transparent 35%);
  overflow: hidden;
}

.login-left::after {
  content: "";
  position: absolute;
  right: -120px;
  bottom: -120px;
  width: 360px;
  height: 360px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.08);
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  position: relative;
  z-index: 1;
}

.brand-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: linear-gradient(135deg, #409eff, #67c23a);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  font-size: 22px;
}

.brand-title {
  font-size: 22px;
  font-weight: 800;
}

.brand-subtitle {
  margin-top: 4px;
  color: #cbd5e1;
  font-size: 13px;
}

.intro {
  margin-top: 110px;
  position: relative;
  z-index: 1;
}

.intro h1 {
  font-size: 36px;
  line-height: 1.35;
  margin: 0;
}

.intro p {
  margin-top: 22px;
  max-width: 620px;
  color: #dbeafe;
  line-height: 1.9;
  font-size: 15px;
}

.feature-list {
  margin-top: 48px;
  display: grid;
  grid-template-columns: repeat(2, 220px);
  gap: 16px;
  position: relative;
  z-index: 1;
}

.feature-item {
  height: 54px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.12);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  backdrop-filter: blur(8px);
}

.feature-item .el-icon {
  font-size: 20px;
  color: #93c5fd;
}

.login-right {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.login-card {
  width: 420px;
  border: none;
  border-radius: 22px;
  padding: 18px;
  box-shadow: 0 18px 50px rgba(20, 33, 61, 0.12);
}

.login-header {
  text-align: center;
  margin-bottom: 28px;
}

.login-title {
  font-size: 26px;
  font-weight: 800;
  color: #1f2937;
}

.login-subtitle {
  margin-top: 8px;
  color: #6b7280;
  font-size: 14px;
}

.login-btn {
  width: 100%;
  margin-top: 6px;
  height: 44px;
  font-size: 16px;
  border-radius: 10px;
}

.demo-tip {
  margin-top: 18px;
  padding: 12px;
  border-radius: 12px;
  background: #f8fafc;
  color: #6b7280;
  text-align: center;
  font-size: 13px;
}
</style>