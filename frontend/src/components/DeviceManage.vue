<template>
  <!--
    设备管理页面。
    该页面用于维护 device_info 表中的设备基础信息。
    设备基础信息不仅用于前端展示，也会参与异常检测逻辑，
    例如 rated_power 额定功率会被后端用于判断功率是否超限。
  -->
  <el-card class="page-card" shadow="never">
    <!-- 页面顶部标题区域 -->
    <template #header>
      <div class="header-row">
        <div>
          <div class="title">设备管理</div>
          <div class="subtitle">
            维护矿山设备基础信息，包括设备编码、名称、类型、安装位置、额定功率和运行状态
          </div>
        </div>

        <!-- 刷新按钮：重新加载设备列表 -->
        <el-button type="primary" :icon="Refresh" @click="loadDevices">
          刷新列表
        </el-button>
      </div>
    </template>

    <!--
      提示信息。
      这里说明额定功率字段和异常检测有关，方便成果展示时解释系统逻辑。
    -->
    <el-alert
      class="tip-alert"
      title="额定功率会作为规则融合异常检测的重要参考值，用于判断设备功率是否超限。"
      type="info"
      show-icon
      :closable="false"
    />

    <!--
      设备表单区域。
      同一个表单既用于新增设备，也用于编辑设备。
      isEdit = false 时表示新增模式；
      isEdit = true 时表示编辑模式。
    -->
    <el-card class="form-card" shadow="never">
      <template #header>
        <div class="form-header">
          <span>{{ isEdit ? '编辑设备信息' : '新增设备信息' }}</span>
          <el-tag :type="isEdit ? 'warning' : 'success'">
            {{ isEdit ? '编辑模式' : '新增模式' }}
          </el-tag>
        </div>
      </template>

      <!--
        el-form 是 Element Plus 表单组件。
        label-width 用于统一表单项标签宽度。
      -->
      <el-form
        :model="form"
        label-width="90px"
        class="device-form"
      >
        <!-- 第一行表单：设备编码、设备名称、设备类型 -->
        <el-row :gutter="18">
          <el-col :span="8">
            <el-form-item label="设备编码">
              <el-input
                v-model="form.device_code"
                placeholder="请输入设备编码"
                clearable
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="设备名称">
              <el-input
                v-model="form.device_name"
                placeholder="请输入设备名称"
                clearable
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="设备类型">
              <el-input
                v-model="form.device_type"
                placeholder="例如：通风设备、排水设备"
                clearable
              />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 第二行表单：安装位置、所属区域、额定功率 -->
        <el-row :gutter="18">
          <el-col :span="8">
            <el-form-item label="安装位置">
              <el-input
                v-model="form.location"
                placeholder="请输入安装位置"
                clearable
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="所属区域">
              <el-input
                v-model="form.area_name"
                placeholder="请输入所属区域"
                clearable
              />
            </el-form-item>
          </el-col>

          <el-col :span="8">
            <el-form-item label="额定功率">
              <!--
                el-input-number 用于输入数字。
                rated_power 是异常检测中的重要参数。
              -->
              <el-input-number
                v-model="form.rated_power"
                :min="0"
                :precision="2"
                :step="10"
                controls-position="right"
                class="full-width"
                placeholder="请输入额定功率"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 第三行表单：设备状态、备注 -->
        <el-row :gutter="18">
          <el-col :span="8">
            <el-form-item label="设备状态">
              <el-select
                v-model="form.status"
                class="full-width"
                placeholder="请选择设备状态"
              >
                <el-option label="运行" :value="1" />
                <el-option label="停机" :value="0" />
                <el-option label="故障" :value="2" />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :span="16">
            <el-form-item label="备注">
              <el-input
                v-model="form.remark"
                placeholder="请输入备注信息"
                clearable
              />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 表单操作按钮 -->
        <div class="form-actions">
          <!-- 新增模式下显示“新增设备”按钮 -->
          <el-button
            v-if="!isEdit"
            type="primary"
            :icon="Plus"
            @click="createDevice"
          >
            新增设备
          </el-button>

          <!-- 编辑模式下显示“保存修改”按钮 -->
          <el-button
            v-if="isEdit"
            type="warning"
            :icon="Edit"
            @click="updateDevice"
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
      设备列表表格。
      数据来自后端 GET /api/devices 接口。
    -->
    <el-card class="table-card" shadow="never">
      <template #header>
        <div class="table-header">
          <span>设备列表</span>
          <el-tag type="primary">共 {{ deviceList.length }} 台设备</el-tag>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="deviceList"
        border
        stripe
        class="device-table"
        style="width: 100%"
      >
        <!-- 设备ID -->
        <el-table-column
          prop="device_id"
          label="设备ID"
          width="90"
          align="center"
        />

        <!-- 设备编码 -->
        <el-table-column
          prop="device_code"
          label="设备编码"
          width="130"
          align="center"
        />

        <!-- 设备名称 -->
        <el-table-column
          prop="device_name"
          label="设备名称"
          width="130"
          align="center"
        />

        <!-- 设备类型 -->
        <el-table-column
          prop="device_type"
          label="设备类型"
          width="130"
          align="center"
        />

        <!-- 安装位置 -->
        <el-table-column
          prop="location"
          label="安装位置"
          min-width="140"
          show-overflow-tooltip
        />

        <!-- 所属区域 -->
        <el-table-column
          prop="area_name"
          label="所属区域"
          width="130"
          align="center"
        />

        <!--
          额定功率。
          这里显示 kW 单位，便于和异常检测规则对应。
        -->
        <el-table-column
          label="额定功率"
          width="130"
          align="center"
        >
          <template #default="{ row }">
            <span class="power-text">{{ row.rated_power }}</span>
            <span class="unit"> kW</span>
          </template>
        </el-table-column>

        <!--
          设备状态。
          用不同颜色的标签展示运行、停机、故障。
        -->
        <el-table-column
          label="状态"
          width="110"
          align="center"
        >
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ formatStatus(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <!-- 备注信息 -->
        <el-table-column
          prop="remark"
          label="备注"
          min-width="150"
          show-overflow-tooltip
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
              @click="handleDelete(row.device_id)"
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
  axios：用于向后端接口发送请求。
*/
import axios from 'axios'

/*
  Element Plus 消息组件和确认框。
  ElMessage 用于提示新增、修改、删除是否成功。
  ElMessageBox 用于删除前确认。
*/
import { ElMessage, ElMessageBox } from 'element-plus'

/*
  Element Plus 图标。
  这些图标用于按钮上，让页面更像后台管理系统。
*/
import {
  Refresh,
  Plus,
  Edit,
  Delete,
  Close
} from '@element-plus/icons-vue'

/*
  deviceList 保存设备列表数据。
  后端 /api/devices 返回的设备数据会写入这里。
*/
const deviceList = ref([])

/*
  loading 控制表格加载动画。
  请求设备列表时为 true，请求完成后改为 false。
*/
const loading = ref(false)

/*
  isEdit 表示当前表单是否处于编辑模式。
  false：新增模式；
  true：编辑模式。
*/
const isEdit = ref(false)

/*
  editId 保存当前正在编辑的设备ID。
  点击编辑按钮后赋值，保存修改时使用。
*/
const editId = ref(null)

/*
  getDefaultForm 返回默认表单对象。
  使用函数返回对象，可以避免多次重置时引用同一个对象。
*/
const getDefaultForm = () => ({
  device_code: '',
  device_name: '',
  device_type: '',
  location: '',
  area_name: '',
  rated_power: 0,
  status: 1,
  remark: ''
})

/*
  form 保存表单输入内容。
  新增设备和编辑设备共用这一个表单。
*/
const form = ref(getDefaultForm())

/*
  加载设备列表。

  请求接口：
    GET http://127.0.0.1:8080/api/devices

  对应后端：
    GetDeviceList

  对应数据库：
    device_info
*/
const loadDevices = async () => {
  loading.value = true

  try {
    const res = await axios.get('http://127.0.0.1:8080/api/devices')
    deviceList.value = res.data.data || []
  } catch (err) {
    console.error('获取设备列表失败：', err)
    ElMessage.error('获取设备列表失败，请检查后端服务是否启动')
  } finally {
    loading.value = false
  }
}

/*
  表单基础校验。
  这里不做复杂校验，只保证核心字段不为空。
*/
const validateForm = () => {
  if (!form.value.device_code) {
    ElMessage.warning('请输入设备编码')
    return false
  }

  if (!form.value.device_name) {
    ElMessage.warning('请输入设备名称')
    return false
  }

  if (!form.value.device_type) {
    ElMessage.warning('请输入设备类型')
    return false
  }

  if (Number(form.value.rated_power) <= 0) {
    ElMessage.warning('请输入大于 0 的额定功率')
    return false
  }

  return true
}

/*
  新增设备。

  请求接口：
    POST http://127.0.0.1:8080/api/devices

  请求数据：
    表单中的设备编码、设备名称、设备类型、安装位置、所属区域、额定功率、状态和备注。

  成功后：
    1. 提示新增成功；
    2. 重置表单；
    3. 重新加载设备列表。
*/
const createDevice = async () => {
  if (!validateForm()) return

  try {
    await axios.post('http://127.0.0.1:8080/api/devices', {
      ...form.value,
      rated_power: Number(form.value.rated_power),
      status: Number(form.value.status)
    })

    ElMessage.success('新增设备成功')
    resetForm()
    loadDevices()
  } catch (err) {
    console.error('新增设备失败：', err)
    ElMessage.error('新增设备失败')
  }
}

/*
  点击编辑按钮时执行。
  将当前行设备信息回填到上方表单，并切换为编辑模式。
*/
const handleEdit = (item) => {
  isEdit.value = true
  editId.value = item.device_id

  form.value = {
    device_code: item.device_code,
    device_name: item.device_name,
    device_type: item.device_type,
    location: item.location,
    area_name: item.area_name,
    rated_power: Number(item.rated_power || 0),
    status: Number(item.status),
    remark: item.remark || ''
  }

  /*
    页面滚动到顶部，方便用户看到表单。
    如果不滚动，用户在表格底部点击编辑后可能不知道表单已经被填充。
  */
  window.scrollTo({
    top: 0,
    behavior: 'smooth'
  })
}

/*
  保存设备修改。

  请求接口：
    PUT http://127.0.0.1:8080/api/devices/:id

  成功后：
    1. 提示修改成功；
    2. 重置表单；
    3. 重新加载设备列表。
*/
const updateDevice = async () => {
  if (!validateForm()) return

  try {
    await axios.put(`http://127.0.0.1:8080/api/devices/${editId.value}`, {
      ...form.value,
      rated_power: Number(form.value.rated_power),
      status: Number(form.value.status)
    })

    ElMessage.success('修改设备成功')
    resetForm()
    loadDevices()
  } catch (err) {
    console.error('修改设备失败：', err)
    ElMessage.error('修改设备失败')
  }
}

/*
  删除设备。

  请求接口：
    DELETE http://127.0.0.1:8080/api/devices/:id

  删除前会弹出确认框，避免误删。
*/
const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm(
      '确认删除该设备吗？删除后设备基础信息将从列表中移除。',
      '删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await axios.delete(`http://127.0.0.1:8080/api/devices/${id}`)

    ElMessage.success('删除设备成功')
    loadDevices()
  } catch (err) {
    /*
      用户点击取消也会进入 catch。
      如果是取消操作，不需要显示错误。
    */
    if (err !== 'cancel') {
      console.error('删除设备失败：', err)
      ElMessage.error('删除设备失败')
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
  将设备状态数字转换为中文。
*/
const formatStatus = (status) => {
  if (Number(status) === 1) return '运行'
  if (Number(status) === 0) return '停机'
  if (Number(status) === 2) return '故障'
  return '未知'
}

/*
  根据设备状态返回 Element Plus 标签颜色。
  运行：绿色；
  停机：灰色；
  故障：红色。
*/
const getStatusType = (status) => {
  if (Number(status) === 1) return 'success'
  if (Number(status) === 0) return 'info'
  if (Number(status) === 2) return 'danger'
  return 'info'
}

/*
  页面加载完成后，自动查询设备列表。
*/
onMounted(() => {
  loadDevices()
})
</script>

<style scoped>
/*
  外层页面卡片。
*/
.page-card {
  border-radius: 18px;
  border: none;
}

/*
  页面顶部标题区域布局。
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
.device-form {
  padding-top: 4px;
}

/*
  让输入数字组件占满列宽。
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
  表格圆角处理。
*/
.device-table {
  border-radius: 12px;
  overflow: hidden;
}

/*
  额定功率数字强调显示。
*/
.power-text {
  font-weight: 700;
  color: #1f2937;
}

/*
  kW 单位文字。
*/
.unit {
  color: #6b7280;
}
</style>
//Device.vue 是设备管理页面。它通过 /api/devices 接口查询设备列表，并支持新增、编辑和删除设备。
这里的额定功率字段比较重要，因为后端异常检测会根据设备额定功率判断功率是否超限。设备状态包括运行、停机和故障，用于展示设备当前管理状态。