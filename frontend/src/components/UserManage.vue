<template>
  <div class="card">
    <h2>用户管理</h2>

    <div class="form-box">
      <div class="row">
        <input v-model="form.username" placeholder="用户名" />
        <input v-model="form.password" placeholder="密码" />
        <input v-model="form.real_name" placeholder="真实姓名" />
      </div>

      <div class="row">
        <select v-model="form.role_id">
          <option value="">请选择角色</option>
          <option v-for="role in roleList" :key="role.role_id" :value="role.role_id">
            {{ formatRole(role.role_name) }}
          </option>
        </select>

        <select v-model="form.status">
          <option :value="1">启用</option>
          <option :value="0">禁用</option>
        </select>
      </div>

      <div class="btn-row">
        <button v-if="!isEdit" @click="createUser">新增用户</button>
        <button v-if="isEdit" @click="updateUser">保存修改</button>
        <button class="cancel-btn" @click="resetForm">重置</button>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th>用户ID</th>
          <th>用户名</th>
          <th>密码</th>
          <th>真实姓名</th>
          <th>角色</th>
          <th>状态</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in userList" :key="item.user_id">
          <td>{{ item.user_id }}</td>
          <td>{{ item.username }}</td>
          <td>{{ item.password }}</td>
          <td>{{ item.real_name }}</td>
          <td>{{ formatRole(item.role_name) }}</td>
          <td>{{ item.status === 1 ? '启用' : '禁用' }}</td>
          <td>{{ item.create_time }}</td>
          <td>
            <button class="edit-btn" @click="handleEdit(item)">编辑</button>
            <button class="delete-btn" @click="handleDelete(item.user_id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const userList = ref([])
const roleList = ref([])
const isEdit = ref(false)
const editId = ref(null)

const getDefaultForm = () => ({
  username: '',
  password: '',
  real_name: '',
  role_id: '',
  status: 1
})

const form = ref(getDefaultForm())

const formatRole = (roleName) => {
  if (roleName === 'admin') return '系统管理员'
  if (roleName === 'monitor') return '监测人员'
  if (roleName === 'manager') return '管理人员'
  return roleName
}

const loadRoles = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8080/api/roles')
    roleList.value = res.data.data || []
  } catch (err) {
    console.error('获取角色列表失败：', err)
    alert('获取角色列表失败')
  }
}

const loadUsers = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8080/api/users')
    userList.value = res.data.data || []
  } catch (err) {
    console.error('获取用户列表失败：', err)
    alert('获取用户列表失败')
  }
}

const createUser = async () => {
  try {
    await axios.post('http://127.0.0.1:8080/api/users', {
      ...form.value,
      role_id: Number(form.value.role_id),
      status: Number(form.value.status)
    })
    alert('新增用户成功')
    resetForm()
    loadUsers()
  } catch (err) {
    console.error('新增用户失败：', err)
    alert('新增用户失败')
  }
}

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
}

const updateUser = async () => {
  try {
    await axios.put(`http://127.0.0.1:8080/api/users/${editId.value}`, {
      ...form.value,
      role_id: Number(form.value.role_id),
      status: Number(form.value.status)
    })
    alert('修改用户成功')
    resetForm()
    loadUsers()
  } catch (err) {
    console.error('修改用户失败：', err)
    alert('修改用户失败')
  }
}

const handleDelete = async (id) => {
  const ok = confirm('确认删除该用户吗？')
  if (!ok) return

  try {
    await axios.delete(`http://127.0.0.1:8080/api/users/${id}`)
    alert('删除用户成功')
    loadUsers()
  } catch (err) {
    console.error('删除用户失败：', err)
    alert('删除用户失败')
  }
}

const resetForm = () => {
  form.value = getDefaultForm()
  isEdit.value = false
  editId.value = null
}

onMounted(() => {
  loadRoles()
  loadUsers()
})
</script>

<style scoped>
.card {
  background: white;
  padding: 20px;
  border-radius: 10px;
}

.form-box {
  background: #f8f9fb;
  padding: 16px;
  border-radius: 10px;
  margin-bottom: 20px;
}

.row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

input,
select {
  padding: 8px;
  min-width: 180px;
  border: 1px solid #ccc;
  border-radius: 6px;
}

.btn-row {
  display: flex;
  gap: 10px;
}

button {
  padding: 8px 14px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  color: white;
  background: #409eff;
}

.cancel-btn {
  background: #909399;
}

.edit-btn {
  background: #e6a23c;
  margin-right: 6px;
}

.delete-btn {
  background: #f56c6c;
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