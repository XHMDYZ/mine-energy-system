<template>
  <!--
    报表分析页面。
    该页面用于展示平台统计报表，包括：
    1. 设备能耗日报；
    2. 设备能耗月报；
    3. 报警统计报表。

    本版本增加了：
    1. 时间筛选功能；
    2. 当前表格 CSV 下载功能。
  -->
  <el-card class="page-card" shadow="never">
    <!-- 页面顶部标题区域 -->
    <template #header>
      <div class="header-row">
        <div>
          <div class="title">报表分析</div>
          <div class="subtitle">
            汇总展示设备能耗统计结果和报警统计结果，用于辅助平台运行分析
          </div>
        </div>

        <!-- 刷新全部报表按钮 -->
        <el-button type="primary" :icon="Refresh" @click="loadAllReports">
          刷新报表
        </el-button>
      </div>
    </template>

    <!-- 报表数据来源说明 -->
    <el-alert
      class="tip-alert"
      title="报表数据基于 energy_history 历史能耗数据和 alarm_record 报警记录统计生成。"
      type="info"
      show-icon
      :closable="false"
    />

    <!-- 顶部统计卡片 -->
    <el-row :gutter="18" class="summary-row">
      <el-col :span="8">
        <el-card class="summary-card blue" shadow="hover">
          <div class="summary-content">
            <div>
              <div class="summary-label">日报记录数</div>
              <div class="summary-value">{{ filteredDailyReports.length }}</div>
            </div>
            <el-icon class="summary-icon"><Calendar /></el-icon>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="summary-card green" shadow="hover">
          <div class="summary-content">
            <div>
              <div class="summary-label">月报记录数</div>
              <div class="summary-value">{{ filteredMonthlyReports.length }}</div>
            </div>
            <el-icon class="summary-icon"><DataAnalysis /></el-icon>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="summary-card orange" shadow="hover">
          <div class="summary-content">
            <div>
              <div class="summary-label">报警统计项</div>
              <div class="summary-value">{{ filteredAlarmStats.length }}</div>
            </div>
            <el-icon class="summary-icon"><Warning /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 报表标签页 -->
    <el-tabs v-model="activeTab" class="report-tabs">
      <!-- 设备能耗日报 -->
      <el-tab-pane label="设备能耗日报" name="daily">
        <el-card class="table-card" shadow="never">
          <template #header>
            <div class="table-header">
              <div>
                <span>设备能耗日报</span>
                <el-tag class="header-tag" type="primary">Daily Report</el-tag>
              </div>

              <!-- 日报筛选与下载区域 -->
              <div class="filter-row">
                <!--
                  选择日报日期。
                  value-format="YYYY-MM-DD" 表示绑定值就是 2026-05-18 这种字符串，
                  后面筛选和下载文件命名都比较方便。
                -->
                <el-date-picker
                  v-model="dailyDate"
                  type="date"
                  value-format="YYYY-MM-DD"
                  placeholder="选择统计日期"
                  class="date-picker"
                  clearable
                />

                <el-button :icon="Search" @click="loadDailyReport">
                  查询
                </el-button>

                <el-button
                  type="success"
                  :icon="Download"
                  @click="downloadCsv(filteredDailyReports, dailyColumns, `设备能耗日报_${dailyDate || '全部'}.csv`)"
                >
                  下载日报
                </el-button>
              </div>
            </div>
          </template>

          <el-table
            v-loading="loading"
            :data="filteredDailyReports"
            border
            stripe
            style="width: 100%"
            class="report-table"
            empty-text="暂无日报数据"
          >
            <el-table-column
              v-for="col in dailyColumns"
              :key="col.prop"
              :prop="col.prop"
              :label="col.label"
              min-width="130"
              align="center"
              show-overflow-tooltip
            />
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 设备能耗月报 -->
      <el-tab-pane label="设备能耗月报" name="monthly">
        <el-card class="table-card" shadow="never">
          <template #header>
            <div class="table-header">
              <div>
                <span>设备能耗月报</span>
                <el-tag class="header-tag" type="success">Monthly Report</el-tag>
              </div>

              <!-- 月报筛选与下载区域 -->
              <div class="filter-row">
                <!--
                  选择月份。
                  value-format="YYYY-MM" 表示绑定值是 2026-05 这种字符串。
                -->
                <el-date-picker
                  v-model="monthlyMonth"
                  type="month"
                  value-format="YYYY-MM"
                  placeholder="选择统计月份"
                  class="date-picker"
                  clearable
                />

                <el-button :icon="Search" @click="loadMonthlyReport">
                  查询
                </el-button>

                <el-button
                  type="success"
                  :icon="Download"
                  @click="downloadCsv(filteredMonthlyReports, monthlyColumns, `设备能耗月报_${monthlyMonth || '全部'}.csv`)"
                >
                  下载月报
                </el-button>
              </div>
            </div>
          </template>

          <el-table
            v-loading="loading"
            :data="filteredMonthlyReports"
            border
            stripe
            style="width: 100%"
            class="report-table"
            empty-text="暂无月报数据"
          >
            <el-table-column
              v-for="col in monthlyColumns"
              :key="col.prop"
              :prop="col.prop"
              :label="col.label"
              min-width="130"
              align="center"
              show-overflow-tooltip
            />
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 报警统计报表 -->
      <el-tab-pane label="报警统计报表" name="alarm">
        <el-card class="table-card" shadow="never">
          <template #header>
            <div class="table-header">
              <div>
                <span>报警统计报表</span>
                <el-tag class="header-tag" type="warning">Alarm Statistics</el-tag>
              </div>

              <!-- 报警统计筛选与下载区域 -->
              <div class="filter-row">
                <!--
                  选择报警统计时间范围。
                  value-format="YYYY-MM-DD" 表示返回值为日期字符串数组：
                  ["2026-05-01", "2026-05-18"]
                -->
                <el-date-picker
                  v-model="alarmDateRange"
                  type="daterange"
                  value-format="YYYY-MM-DD"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  class="range-picker"
                  clearable
                />

                <el-button :icon="Search" @click="loadAlarmStats">
                  查询
                </el-button>

                <el-button
                  type="success"
                  :icon="Download"
                  @click="downloadCsv(filteredAlarmStats, alarmColumns, `报警统计报表_${alarmRangeText}.csv`)"
                >
                  下载报警统计
                </el-button>
              </div>
            </div>
          </template>

          <el-table
            v-loading="loading"
            :data="filteredAlarmStats"
            border
            stripe
            style="width: 100%"
            class="report-table"
            empty-text="暂无报警统计数据"
          >
            <el-table-column
              v-for="col in alarmColumns"
              :key="col.prop"
              :prop="col.prop"
              :label="col.label"
              min-width="130"
              align="center"
              show-overflow-tooltip
            />
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script setup>
/*
  ref：定义响应式变量；
  computed：根据原始数据和时间条件计算筛选后的数据；
  onMounted：页面加载完成后自动加载报表数据。
*/
import { ref, computed, onMounted } from 'vue'

/*
  axios 用于请求后端接口。
*/
import axios from 'axios'

/*
  ElMessage 用于消息提示。
*/
import { ElMessage } from 'element-plus'

/*
  Element Plus 图标。
*/
import {
  Refresh,
  Calendar,
  DataAnalysis,
  Warning,
  Search,
  Download
} from '@element-plus/icons-vue'

/*
  activeTab 表示当前选中的标签页。
*/
const activeTab = ref('daily')

/*
  loading 控制表格加载状态。
*/
const loading = ref(false)

/*
  报表原始数据。
  dailyReports：日报数据；
  monthlyReports：月报数据；
  alarmStats：报警统计数据。
*/
const dailyReports = ref([])
const monthlyReports = ref([])
const alarmStats = ref([])

/*
  时间筛选条件。
  dailyDate：日报日期，例如 2026-05-18；
  monthlyMonth：月报月份，例如 2026-05；
  alarmDateRange：报警统计日期范围，例如 ["2026-05-01", "2026-05-18"]。
*/
const dailyDate = ref('')
const monthlyMonth = ref('')
const alarmDateRange = ref([])

/*
  字段中文名称映射表。
  如果后端返回字段名为 device_name，则前端显示为“设备名称”。
*/
const labelMap = {
  device_id: '设备ID',
  device_name: '设备名称',
  device_code: '设备编码',
  stat_date: '统计日期',
  date: '日期',
  day: '日期',
  stat_month: '统计月份',
  month: '月份',
  total_energy: '总能耗',
  energy_total: '累计能耗',
  energy_increment: '能耗增量',
  avg_power: '平均功率',
  max_power: '最大功率',
  min_power: '最小功率',
  alarm_id: '报警ID',
  alarm_type: '报警类型',
  alarm_level: '报警级别',
  alarm_count: '报警数量',
  count: '数量',
  process_status: '处理状态',
  create_time: '创建时间',
  update_time: '更新时间'
}

/*
  formatLabel 用于将字段名转换为中文表头。
*/
const formatLabel = (key) => {
  return labelMap[key] || key
}

/*
  buildColumns 根据数据自动生成表格列。
  这样日报、月报、报警统计即使字段不同，也能正常展示。
*/
const buildColumns = (list) => {
  if (!Array.isArray(list) || list.length === 0) {
    return []
  }

  return Object.keys(list[0]).map(key => ({
    prop: key,
    label: formatLabel(key)
  }))
}

/*
  三个表格对应的动态列。
*/
const dailyColumns = computed(() => buildColumns(filteredDailyReports.value))
const monthlyColumns = computed(() => buildColumns(filteredMonthlyReports.value))
const alarmColumns = computed(() => buildColumns(filteredAlarmStats.value))

/*
  alarmRangeText 用于生成下载文件名。
*/
const alarmRangeText = computed(() => {
  if (!alarmDateRange.value || alarmDateRange.value.length !== 2) {
    return '全部'
  }

  return `${alarmDateRange.value[0]}_${alarmDateRange.value[1]}`
})

/*
  normalizeResponseData 用于兼容不同后端返回格式。

  常见后端返回格式：
  1. { data: [...] }
  2. { data: { list: [...] } }
  3. 直接返回 [...]
*/
const normalizeResponseData = (res) => {
  const data = res.data?.data

  if (Array.isArray(data)) {
    return data
  }

  if (Array.isArray(data?.list)) {
    return data.list
  }

  if (Array.isArray(res.data)) {
    return res.data
  }

  return []
}

/*
  getRowDate 用于从某条报表记录中尽量提取日期字段。
  因为不同接口可能字段名不同，所以这里做兼容处理。
*/
const getRowDate = (row) => {
  return row.stat_date || row.date || row.day || row.alarm_date || row.create_time || ''
}

/*
  getRowMonth 用于从某条月报记录中尽量提取月份字段。
*/
const getRowMonth = (row) => {
  return row.stat_month || row.month || row.date || ''
}

/*
  filteredDailyReports 是筛选后的日报数据。
  如果未选择日期，则显示全部日报；
  如果选择了日期，则只显示对应日期的数据。
*/
const filteredDailyReports = computed(() => {
  if (!dailyDate.value) {
    return dailyReports.value
  }

  return dailyReports.value.filter(row => {
    const rowDate = String(getRowDate(row)).slice(0, 10)
    return rowDate === dailyDate.value
  })
})

/*
  filteredMonthlyReports 是筛选后的月报数据。
  如果未选择月份，则显示全部月报；
  如果选择了月份，则只显示对应月份的数据。
*/
const filteredMonthlyReports = computed(() => {
  if (!monthlyMonth.value) {
    return monthlyReports.value
  }

  return monthlyReports.value.filter(row => {
    const rowMonth = String(getRowMonth(row)).slice(0, 7)
    return rowMonth === monthlyMonth.value
  })
})

/*
  filteredAlarmStats 是筛选后的报警统计数据。
  如果未选择时间范围，则显示全部；
  如果选择了时间范围，则按日期范围筛选。

  注意：
  如果后端返回的报警统计数据没有日期字段，那么前端无法准确过滤时间。
  这种情况下会显示全部数据。后续可以在后端报警统计接口中增加 stat_date 字段。
*/
const filteredAlarmStats = computed(() => {
  if (!alarmDateRange.value || alarmDateRange.value.length !== 2) {
    return alarmStats.value
  }

  const [start, end] = alarmDateRange.value

  return alarmStats.value.filter(row => {
    const rowDate = String(getRowDate(row)).slice(0, 10)

    if (!rowDate) {
      return true
    }

    return rowDate >= start && rowDate <= end
  })
})

/*
  加载日报数据。
  这里附带 date 参数，如果后端支持 date 查询，就能直接按日期返回；
  如果后端暂时不处理该参数，前端也会通过 filteredDailyReports 再筛选一次。
*/
const loadDailyReport = async () => {
  const res = await axios.get('http://127.0.0.1:8080/api/reports/daily', {
    params: {
      date: dailyDate.value || undefined
    }
  })

  dailyReports.value = normalizeResponseData(res)
}

/*
  加载月报数据。
  附带 month 参数，便于后端后续扩展按月查询。
*/
const loadMonthlyReport = async () => {
  const res = await axios.get('http://127.0.0.1:8080/api/reports/monthly', {
    params: {
      month: monthlyMonth.value || undefined
    }
  })

  monthlyReports.value = normalizeResponseData(res)
}

/*
  加载报警统计数据。
  附带 start_date 和 end_date 参数，便于后端后续扩展按时间范围查询。
*/
const loadAlarmStats = async () => {
  const startDate = alarmDateRange.value?.[0]
  const endDate = alarmDateRange.value?.[1]

  const res = await axios.get('http://127.0.0.1:8080/api/reports/alarm-stats', {
    params: {
      start_date: startDate || undefined,
      end_date: endDate || undefined
    }
  })

  alarmStats.value = normalizeResponseData(res)
}

/*
  一次性加载全部报表数据。
*/
const loadAllReports = async () => {
  loading.value = true

  try {
    await Promise.all([
      loadDailyReport(),
      loadMonthlyReport(),
      loadAlarmStats()
    ])
  } catch (err) {
    console.error('加载报表失败：', err)
    ElMessage.error('加载报表失败，请检查后端服务是否启动')
  } finally {
    loading.value = false
  }
}

/*
  escapeCsvValue 用于处理 CSV 单元格内容。
  如果内容中有逗号、换行或双引号，需要进行转义。
*/
const escapeCsvValue = (value) => {
  if (value === null || value === undefined) {
    return ''
  }

  const str = String(value).replace(/"/g, '""')

  if (str.includes(',') || str.includes('\n') || str.includes('"')) {
    return `"${str}"`
  }

  return str
}

/*
  downloadCsv 下载当前表格数据为 CSV 文件。

  参数：
    rows：当前表格数据；
    columns：当前表格列配置；
    filename：下载文件名。

  说明：
    这里导出的是 CSV 文件，Excel 可以直接打开。
    加上 BOM 头 \uFEFF 是为了避免中文乱码。
*/
const downloadCsv = (rows, columns, filename) => {
  if (!rows || rows.length === 0) {
    ElMessage.warning('当前没有可下载的数据')
    return
  }

  if (!columns || columns.length === 0) {
    ElMessage.warning('当前表格列为空，无法下载')
    return
  }

  const header = columns.map(col => escapeCsvValue(col.label)).join(',')

  const body = rows.map(row => {
    return columns.map(col => escapeCsvValue(row[col.prop])).join(',')
  }).join('\n')

  const csvContent = `\uFEFF${header}\n${body}`

  const blob = new Blob([csvContent], {
    type: 'text/csv;charset=utf-8;'
  })

  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')

  link.href = url
  link.download = filename
  link.click()

  URL.revokeObjectURL(url)

  ElMessage.success('报表下载成功')
}

/*
  页面加载完成后自动加载报表数据。
*/
onMounted(() => {
  loadAllReports()
})
</script>

<style scoped>
.page-card {
  border-radius: 18px;
  border: none;
}

.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2937;
}

.subtitle {
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}

.tip-alert {
  margin-bottom: 16px;
}

.summary-row {
  margin-bottom: 18px;
}

.summary-card {
  border-radius: 16px;
  border: none;
}

.summary-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.summary-label {
  color: #6b7280;
  font-size: 14px;
}

.summary-value {
  margin-top: 8px;
  font-size: 30px;
  font-weight: 800;
  color: #1f2937;
}

.summary-icon {
  font-size: 44px;
  opacity: 0.2;
}

.blue {
  background: linear-gradient(135deg, #ffffff, #eaf3ff);
}

.green {
  background: linear-gradient(135deg, #ffffff, #ecfdf3);
}

.orange {
  background: linear-gradient(135deg, #ffffff, #fff4e5);
}

.blue .summary-icon {
  color: #409eff;
}

.green .summary-icon {
  color: #67c23a;
}

.orange .summary-icon {
  color: #e6a23c;
}

.report-tabs {
  margin-top: 8px;
}

.table-card {
  border-radius: 16px;
  border: 1px solid #eef2f7;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-weight: 700;
  color: #1f2937;
}

.header-tag {
  margin-left: 10px;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  font-weight: normal;
}

.date-picker {
  width: 180px;
}

.range-picker {
  width: 300px;
}

.report-table {
  border-radius: 12px;
  overflow: hidden;
}
</style>