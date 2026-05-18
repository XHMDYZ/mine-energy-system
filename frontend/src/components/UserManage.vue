<template>
  <!--
    用户管理页面。
    该页面用于维护系统用户信息，包括用户名、密码、真实姓名、角色和启用状态。
    对应数据库中的 user 表和 role 表。
    在平台中，用户角色会影响菜单显示和报警处理权限。
  -->
  <el-card class="page-card" shadow="never">
    <!-- 页面顶部标题区域 -->
    <template #header>
      <div class="header-row">
        <div>
          <div class="title">用户管理</div>
          <div class="subtitle">
            维护系统用户、角色和账号状态，用于平台登录、菜单显示和报警处理权限控制
          </div>
        </div>

        <!-- 刷新按钮：重新加载用户列表和角色列表 -->
        <el-button type="primary" :icon="Refresh" @click="refreshAll">
          刷新列表
        </el-button>
      </div>
    </template>

    <!--
      提示信息。
      这里说明当前系统属于原型系统，真实系统中密码不应明文展示。
    -->
    <el-alert
      class="tip-alert"
      title="当前页面用于毕业设计原型演示，真实系统中应对密码进行加密存储，并避免前端展示明文密码。"
      type="warning"
      show-icon
      :closable="false"
    />

    <!--
      用户表单区域。
      同一个表单既用于新增用户，也用于编辑已有用户。
      isEdit = false 表示新增模式；
      isEdit = true 表示编辑模式。
    -->
    <el-card class="form-card" shadow="never">
      <template #header>
        <div class="form-header">
          <span>{{ isEdit ? '编辑用户信息' : '新增用户信息' }}</span>
          <el-tag :type="isEdit ? 'warning' : 'success'">
            {{ isEdit ? '编辑模式' : '新增模式' }}
          </el-tag>
        </div>
      </template>

      <!--
        Element Plus 表单组件。
        :model="form" 表示表单数据对象。
        label-width 用来统一标签宽度。
      -->
      <el-form
        :model="form"
        label-width="90px"
        class="user-form"
      >
        <!-- 第一行：用户名、密码、真实姓名 -->
        <el-row :gutter="18">
          <el-col :span="8">
            <el-form-item label="用户名">
              <el-input
                v-model="form.username"
                placeholder="请输入用户名"
                clearable
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="密码">
              <!--
                show-password 表示输入框支持显示/隐藏密码。
                原型系统中可以直接编辑密码。
                真实系统中建议单独设计“重置密码”功能。
              -->
              <el-input
                v-model="form.password"
                type="password"
                show-password
                placeholder="请输入密码"
                clearable
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="真实姓名">
              <el-input
                v-model="form.real_name"
                placeholder="请输入真实姓名"
                clearable
              />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 第二行：角色、状态 -->
        <el-row :gutter="18">
          <el-col :span="8">
            <el-form-item label="用户角色">
              <!--
                角色下拉框。
                角色数据来自后端 /api/roles 接口。
                role_id 会提交给后端保存。
              -->
              <el-select
                v-model="form.role_id"
                class="full-width"
                placeholder="请选择角色"
              >
                <el-option
                  v-for="role in roleList"
                  :key="role.role_id"
                  :label="formatRole(role.role_name)"
                  :value="role.role_id"
                />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="账号状态">
              <!--
                状态：
                1 表示启用；
                0 表示禁用。
              -->
              <el-select
                v-model="form.status"
                class="full-width"
                placeholder="请选择状态"
              >
                <el-option label="启用" :value="1" />
                <el-option label="禁用" :value="0" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 表单操作按钮 -->
        <div class="form-actions">
          <!-- 新增模式下显示“新增用户” -->
          <el-button
            v-if="!isEdit"
            type="primary"
            :icon="Plus"
            @click="createUser"
          >
            新增用户
          </el-button>

          <!-- 编辑模式下显示“保存修改” -->
          <el-button
            v-if="isEdit"
            type="warning"
            :icon="Edit"
            @click="updateUser"
          >
            保存修改
          </el-button>

          <!-- 重置表单，同时退出编辑模式 -->
          <el-button :icon="Close" @click="resetForm">
            重置
          </el-button>
        </div>
      </el-form>
    </el-card>

    <!--
      用户列表表格。
      数据来自后端 GET /api/users 接口。
    -->
    <el-card class="table-card" shadow="never">
      <template #header>
        <div class="table-header">
          <span>用户列表</span>
          <el-tag type="primary">共 {{ userList.length }} 个用户</el-tag>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="userList"
        border
        stripe
        class="user-table"
        style="width: 100%"
      >
        <!-- 用户ID -->
        <el-table-column
          prop="user_id"
          label="用户ID"
          width="90"
          align="center"
        />

        <!-- 用户名 -->
        <el-table-column
          prop="username"
          label="用户名"
          width="140"
          align="center"
        />

        <!--
          密码列。
          为了页面展示更规范，这里不直接显示明文密码，而显示 ******。
          但编辑时仍然会把 item.password 回填到表单。
        -->
        <el-table-column
          label="密码"
          width="130"
          align="center"
        >
          <template #default>
            <span class="password-mask">******</span>
          </template>
        </el-table-column>

        <!-- 真实姓名 -->
        <el-table-column
          prop="real_name"
          label="真实姓名"
          width="130"
          align="center"
        />

        <!--
          用户角色。
          后端返回 role_name，例如 admin、monitor、manager。
          前端通过 formatRole 转成中文显示。
        -->
        <el-table-column
          label="角色"
          width="140"
          align="center"
        >
          <template #default="{ row }">
            <el-tag :type="getRoleType(row.role_name)">
              {{ formatRole(row.role_name) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 账号状态 -->
        <el-table-column
          label="状态"
          width="110"
          align="center"
        >
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'info'">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 创建时间 -->
        <el-table-column
          prop="create_time"
          label="创建时间"
          min-width="180"
          align="center"
        />

        <!-- 操作列 -->
        <el-table-column
          label="操作"
          width="160"
          align="center"
          fixed="right"
        >
          <template #default="{ row }">
            <!-- 编辑按钮 -->
            <el-button
              type="warning"
              size="small"
              :icon="Edit"
              @click="handleEdit(row)"
            >
              编辑
            </el-button>

            <!-- 删除按钮 -->
            <el-button
              type="danger"
              size="small"
              :icon="Delete"
              @click="handleDelete(row.user_id)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </el-card>
</template>

<script setup>
/*
  ref：定义响应式变量。
  onMounted：页面加载完成后执行初始化逻辑。
*/
import { ref, onMounted } from 'vue'

/*
  axios：用于向后端接口发送 HTTP 请求。
*/
import axios from 'axios'

/*
  ElMessage：消息提示。
  ElMessageBox：确认弹窗。
*/
import { ElMessage, ElMessageBox } from 'element-plus'

/*
  Element Plus 图标。
  用于按钮装饰，让页面更像后台管理系统。
*/
import {
  Refresh,
  Plus,
  Edit,
  Delete,
  Close
} from '@element-plus/icons-vue'

/*
  userList 保存用户列表数据。
  后端 /api/users 返回的数据会写入这里。
*/
const userList = ref([])

/*
  roleList 保存角色列表数据。
  后端 /api/roles 返回的数据会写入这里。
  新增或编辑用户时，角色下拉框使用该数据。
*/
const roleList = ref([])

/*
  loading 控制用户表格的加载动画。
*/
const loading = ref(false)

/*
  isEdit 表示当前表单是否处于编辑模式。
  false：新增模式；
  true：编辑模式。
*/
const isEdit = ref(false)

/*
  editId 保存当前正在编辑的用户ID。
*/
const editId = ref(null)

/*
  getDefaultForm 返回默认表单对象。
  使用函数返回对象，可以避免多次重置时引用同一个对象。
*/
const getDefaultForm = () => ({
  username: '',
  password: '',
  real_name: '',
  role_id: '',
  status: 1
})

/*
  form 保存当前表单输入内容。
  新增用户和编辑用户共用这一份表单。
*/
const form = ref(getDefaultForm())

/*
  将后端返回的角色英文名转换为中文名称。
*/
const formatRole = (roleName) => {
  if (roleName === 'admin') return '系统管理员'
  if (roleName === 'manager') return '管理人员'
  if (roleName === 'operator') return '值班员'
  return roleName || '未分配'
}

/*
  根据角色返回标签颜色。
  admin：红色，表示权限较高；
  monitor：蓝色，表示监测角色；
  manager：绿色，表示管理角色。
*/
const getRoleType = (roleName) => {
  if (roleName === 'admin') return 'danger'
  if (roleName === 'manager') return 'success'
  if (roleName === 'operator') return 'primary'
  return 'info'
}

/*
  加载角色列表。

  请求接口：
    GET http://127.0.0.1:8080/api/roles

  对应后端：
    GetRoleList
*/
const loadRoles = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8080/api/roles')
    roleList.value = res.data.data || []
  } catch (err) {
    console.error('获取角色列表失败：', err)
    ElMessage.error('获取角色列表失败')
  }
}

/*
  加载用户列表。

  请求接口：
    GET http://127.0.0.1:8080/api/users

  对应后端：
    GetUserList
*/
const loadUsers = async () => {
  loading.value = true

  try {
    const res = await axios.get('http://127.0.0.1:8080/api/users')
    userList.value = res.data.data || []
  } catch (err) {
    console.error('获取用户列表失败：', err)
    ElMessage.error('获取用户列表失败，请检查后端服务是否启动')
  } finally {
    loading.value = false
  }
}

/*
  刷新角色列表和用户列表。
*/
const refreshAll = () => {
  loadRoles()
  loadUsers()
}

/*
  表单基础校验。
  防止用户名、密码、角色等关键字段为空。
*/
const validateForm = () => {
  if (!form.value.username) {
    ElMessage.warning('请输入用户名')
    return false
  }

  if (!form.value.password) {
    ElMessage.warning('请输入密码')
    return false
  }

  if (!form.value.real_name) {
    ElMessage.warning('请输入真实姓名')
    return false
  }

  if (!form.value.role_id) {
    ElMessage.warning('请选择用户角色')
    return false
  }

  return true
}

/*
  新增用户。

  请求接口：
    POST http://127.0.0.1:8080/api/users

  成功后：
    1. 提示新增成功；
    2. 重置表单；
    3. 重新加载用户列表。
*/
const createUser = async () => {
  if (!validateForm()) return

  try {
    await axios.post('http://127.0.0.1:8080/api/users', {
      ...form.value,
      role_id: Number(form.value.role_id),
      status: Number(form.value.status)
    })

    ElMessage.success('新增用户成功')
    resetForm()
    loadUsers()
  } catch (err) {
    console.error('新增用户失败：', err)
    ElMessage.error('新增用户失败')
  }
}

/*
  点击编辑按钮时执行。
  将当前用户信息回填到上方表单，并切换为编辑模式。
*/
const handleEdit = (item) => {
  isEdit.value = true
  editId.value = item.user_id

  form.value = {
    username: item.username,
    password: item.password,
    real_name: item.real_name,
    role_id: item.role_id,
    status: item.status
  }

  /*
    滚动到页面顶部，让用户看到表单已经填充。
  */
  window.scrollTo({
    top: 0,
    behavior: 'smooth'
  })
}

/*
  保存用户修改。

  请求接口：
    PUT http://127.0.0.1:8080/api/users/:id

  成功后：
    1. 提示修改成功；
    2. 重置表单；
    3. 重新加载用户列表。
*/
const updateUser = async () => {
  if (!validateForm()) return

  try {
    await axios.put(`http://127.0.0.1:8080/api/users/${editId.value}`, {
      ...form.value,
      role_id: Number(form.value.role_id),
      status: Number(form.value.status)
    })

    ElMessage.success('修改用户成功')
    resetForm()
    loadUsers()
  } catch (err) {
    console.error('修改用户失败：', err)
    ElMessage.error('修改用户失败')
  }
}

/*
  删除用户。

  请求接口：
    DELETE http://127.0.0.1:8080/api/users/:id

  删除前通过确认框进行二次确认，避免误删。
*/
const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm(
      '确认删除该用户吗？删除后该账号将无法继续用于系统登录。',
      '删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await axios.delete(`http://127.0.0.1:8080/api/users/${id}`)

    ElMessage.success('删除用户成功')
    loadUsers()
  } catch (err) {
    /*
      用户点击取消时也会进入 catch。
      如果是取消操作，不显示错误提示。
    */
    if (err !== 'cancel') {
      console.error('删除用户失败：', err)
      ElMessage.error('删除用户失败')
    }
  }
}

/*
  重置表单。
  清空表单内容，并退出编辑模式。
*/
const resetForm = () => {
  form.value = getDefaultForm()
  isEdit.value = false
  editId.value = null
}

/*
  页面加载完成后：
  1. 加载角色列表；
  2. 加载用户列表。
*/
onMounted(() => {
  loadRoles()
  loadUsers()
})
</script>

<style scoped>
/*
  页面外层卡片。
*/
.page-card {
  border-radius: 18px;
  border: none;
}

/*
  页面顶部标题区域。
*/
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/*
  页面主标题。
*/
.title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
}

/*
  页面副标题。
*/
.subtitle {
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}

/*
  顶部提示条。
*/
.tip-alert {
  margin-bottom: 16px;
}

/*
  表单卡片。
*/
.form-card {
  border-radius: 16px;
  border: 1px solid #eef2f7;
  margin-bottom: 18px;
}

/*
  表单卡片标题区域。
*/
.form-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 700;
  color: #1f2937;
}

/*
  表单区域。
*/
.user-form {
  padding-top: 4px;
}

/*
  让下拉框占满列宽。
*/
.full-width {
  width: 100%;
}

/*
  表单按钮区域。
*/
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

/*
  表格卡片。
*/
.table-card {
  border-radius: 16px;
  border: 1px solid #eef2f7;
}

/*
  表格标题区域。
*/
.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 700;
  color: #1f2937;
}

/*
  表格圆角。
*/
.user-table {
  border-radius: 12px;
  overflow: hidden;
}

/*
  密码掩码显示。
*/
.password-mask {
  color: #909399;
  letter-spacing: 2px;
}
</style>
//User.vue 是用户管理页面。它通过 /api/roles 获取角色列表，通过 /api/users 获取用户列表，并支持新增、编辑和删除用户。
用户角色包括系统管理员、监测人员和管理人员，不同角色可以和菜单权限、报警处理权限对应起来。
这个页面主要用于说明平台具备基础的用户与权限管理能力。