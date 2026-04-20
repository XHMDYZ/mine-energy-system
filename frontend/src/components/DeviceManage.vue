<template>
  <div class="card">
    <h2>设备管理</h2>

    <div class="form-box">
      <div class="row">
        <input v-model="form.device_code" placeholder="设备编码" />
        <input v-model="form.device_name" placeholder="设备名称" />
        <input v-model="form.device_type" placeholder="设备类型" />
      </div>

      <div class="row">
        <input v-model="form.location" placeholder="安装位置" />
        <input v-model="form.area_name" placeholder="所属区域" />
        <input v-model="form.rated_power" type="number" placeholder="额定功率" />
      </div>

      <div class="row">
        <select v-model="form.status">
          <option :value="1">运行</option>
          <option :value="0">停机</option>
          <option :value="2">故障</option>
        </select>
        <input v-model="form.remark" placeholder="备注" />
      </div>

      <div class="btn-row">
        <button v-if="!isEdit" @click="createDevice">新增设备</button>
        <button v-if="isEdit" @click="updateDevice">保存修改</button>
        <button class="cancel-btn" @click="resetForm">重置</button>
      </div>
    </div>

    <table>
      <thead>
        <tr>
          <th>设备ID</th>
          <th>设备编码</th>
          <th>设备名称</th>
          <th>设备类型</th>
          <th>安装位置</th>
          <th>所属区域</th>
          <th>额定功率</th>
          <th>状态</th>
          <th>备注</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in deviceList" :key="item.device_id">
          <td>{{ item.device_id }}</td>
          <td>{{ item.device_code }}</td>
          <td>{{ item.device_name }}</td>
          <td>{{ item.device_type }}</td>
          <td>{{ item.location }}</td>
          <td>{{ item.area_name }}</td>
          <td>{{ item.rated_power }}</td>
          <td>{{ formatStatus(item.status) }}</td>
          <td>{{ item.remark }}</td>
          <td>
            <button class="edit-btn" @click="handleEdit(item)">编辑</button>
            <button class="delete-btn" @click="handleDelete(item.device_id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const deviceList = ref([])
const isEdit = ref(false)
const editId = ref(null)

const getDefaultForm = () => ({
  device_code: '',
  device_name: '',
  device_type: '',
  location: '',
  area_name: '',
  rated_power: '',
  status: 1,
  remark: ''
})

const form = ref(getDefaultForm())

const loadDevices = async () => {
  try {
    const res = await axios.get('http://127.0.0.1:8080/api/devices')
    deviceList.value = res.data.data || []
  } catch (err) {
    console.error('获取设备列表失败：', err)
    alert('获取设备列表失败')
  }
}

const createDevice = async () => {
  try {
    await axios.post('http://127.0.0.1:8080/api/devices', {
      ...form.value,
      rated_power: Number(form.value.rated_power),
      status: Number(form.value.status)
    })
    alert('新增成功')
    resetForm()
    loadDevices()
  } catch (err) {
    console.error('新增设备失败：', err)
    alert('新增设备失败')
  }
}

const handleEdit = (item) => {
  isEdit.value = true
  editId.value = item.device_id
  form.value = {
    device_code: item.device_code,
    device_name: item.device_name,
    device_type: item.device_type,
    location: item.location,
    area_name: item.area_name,
    rated_power: item.rated_power,
    status: item.status,
    remark: item.remark
  }
}

const updateDevice = async () => {
  try {
    await axios.put(`http://127.0.0.1:8080/api/devices/${editId.value}`, {
      ...form.value,
      rated_power: Number(form.value.rated_power),
      status: Number(form.value.status)
    })
    alert('修改成功')
    resetForm()
    loadDevices()
  } catch (err) {
    console.error('修改设备失败：', err)
    alert('修改设备失败')
  }
}

const handleDelete = async (id) => {
  const ok = confirm('确认删除该设备吗？')
  if (!ok) return

  try {
    await axios.delete(`http://127.0.0.1:8080/api/devices/${id}`)
    alert('删除成功')
    loadDevices()
  } catch (err) {
    console.error('删除设备失败：', err)
    alert('删除设备失败')
  }
}

const resetForm = () => {
  form.value = getDefaultForm()
  isEdit.value = false
  editId.value = null
}

const formatStatus = (status) => {
  if (status === 1) return '运行'
  if (status === 0) return '停机'
  if (status === 2) return '故障'
  return '未知'
}

onMounted(() => {
  loadDevices()
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