package controllers

import (
	"backend/config"
	"backend/models"
	"backend/services"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

// EnergyUploadRequest 定义采集端上传能耗数据时的请求结构。
// Python 采集端 prosys_collector.py 清洗通过数据后，
// 会通过 POST /api/energy/upload 接口把这些字段上传给 Go 后端。
type EnergyUploadRequest struct {
	DeviceID    uint    `json:"device_id"`    // 设备编号，对应 device_info 表中的 device_id
	Voltage     float64 `json:"voltage"`      // 电压
	Current     float64 `json:"current"`      // 电流
	Power       float64 `json:"power"`        // 功率
	EnergyTotal float64 `json:"energy_total"` // 累计能耗
	DataSource  string  `json:"data_source"`  // 数据来源，例如 opcua
	CollectTime string  `json:"collect_time"` // 采集时间，格式为 yyyy-MM-dd HH:mm:ss
}

// UploadEnergyData 接收采集端上传的能耗数据。
// 该接口是系统数据进入后端的核心入口之一。
//
// 主要流程：
// 1. 解析采集端上传的 JSON 数据；
// 2. 处理采集时间和数据来源；
// 3. 校验设备是否存在；
// 4. 计算本次能耗增量；
// 5. 写入 energy_history 历史数据表；
// 6. 调用融合异常检测方法；
// 7. 如果检测到异常，则保存异常记录和报警记录。
func UploadEnergyData(c *gin.Context) {
	var req EnergyUploadRequest

	// 1. 解析请求 JSON。
	// 如果采集端上传的数据格式不符合 EnergyUploadRequest 结构，
	// 则返回请求参数错误。
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "请求参数错误",
		})
		return
	}

	// 2. 设置时区。
	// 系统中的采集时间、历史趋势时间和报警时间都采用北京时间。
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		// 如果系统无法加载 Asia/Shanghai，则手动设置东八区。
		loc = time.FixedZone("CST", 8*3600)
	}

	// 默认使用当前服务器时间作为记录时间。
	recordTime := time.Now().In(loc)

	// 如果采集端传入 collect_time，则优先使用采集端时间。
	// 这样可以保证数据库中的 record_time 与采集端实际采样时间一致。
	if strings.TrimSpace(req.CollectTime) != "" {
		if t, err := time.ParseInLocation("2006-01-02 15:04:05", req.CollectTime, loc); err == nil {
			recordTime = t
		}
	}

	// 处理数据来源字段。
	// 如果采集端没有传 data_source，则默认写为 python_mock。
	dataSource := strings.TrimSpace(req.DataSource)
	if dataSource == "" {
		dataSource = "python_mock"
	}

	// ============================================================
	// 3. 校验设备是否存在
	// ============================================================
	// 在写入历史数据之前，先检查 device_id 是否存在于 device_info 表中。
	// 这样可以避免不存在的设备编号写入 energy_history，导致后续统计和展示异常。
	var device models.DeviceInfo
	if err := config.DB.Where("device_id = ?", req.DeviceID).First(&device).Error; err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "设备不存在，数据未保存",
		})
		return
	}

	// ============================================================
	// 4. 计算本次能耗增量
	// ============================================================
	// energy_total 是累计能耗。
	// 为了前端统计和报表分析方便，这里根据上一条历史记录计算本次能耗增量。
	energyIncrement := 0.0

	var last models.EnergyHistory
	if err := config.DB.
		Where("device_id = ?", req.DeviceID).
		Order("history_id desc").
		First(&last).Error; err == nil {

		// 本次增量 = 当前累计能耗 - 上一次累计能耗。
		energyIncrement = req.EnergyTotal - last.EnergyTotal

		// 如果增量小于0，可能说明累计能耗发生回跳。
		// 正常情况下，这类数据应该已经在 Python 清洗端被拦截。
		// 这里再做一次保护，避免负增量进入历史统计。
		if energyIncrement < 0 {
			energyIncrement = 0
		}
	}

	// ============================================================
	// 5. 保存历史能耗数据
	// ============================================================
	// 这里的数据已经经过采集端 data_cleaner.py 清洗，
	// 因此可以写入 energy_history 表，作为趋势分析、能耗排行、
	// 异常检测和深度学习训练的数据来源。
	data := models.EnergyHistory{
		DeviceID:        req.DeviceID,
		Voltage:         req.Voltage,
		Current:         req.Current,
		Power:           req.Power,
		EnergyIncrement: energyIncrement,
		EnergyTotal:     req.EnergyTotal,
		RecordTime:      recordTime,
		DataSource:      dataSource,
	}

	if err := config.DB.Create(&data).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "数据保存失败",
		})
		return
	}

	// ============================================================
	// 6. 执行融合异常检测
	// ============================================================
	// DetectAbnormal 是本文规则融合异常检测的核心方法。
	// 它会结合设备约束规则、变化率分析和历史偏差分析，
	// 判断当前数据是否存在功率超限、短时突变或历史偏离等异常。
	detectResult := services.DetectAbnormal(device, data)

	// ============================================================
	// 7. 保存异常结果和报警记录
	// ============================================================
	// 如果检测结果为异常，则写入异常结果表和报警记录表。
	// SaveAbnormalAndAlarm 内部会根据异常得分和等级决定报警记录内容。
	if detectResult.IsAbnormal {
		if err := services.SaveAbnormalAndAlarm(device, data, detectResult); err != nil {
			// 这里不直接返回错误给前端，是因为历史数据已经成功入库。
			// 即使异常记录保存失败，也不影响本次能耗数据上传主流程。
			fmt.Println("异常检测结果保存失败：", err)
		}
	}

	// 返回上传成功结果。
	c.JSON(http.StatusOK, gin.H{
		"message": "上传成功",
		"data":    data,
	})
}

// GetEnergyHistory 查询历史能耗数据。
// 前端历史趋势页面会调用 GET /api/energy/history 接口。
// 可以通过 device_id 参数筛选某一台设备的数据。
func GetEnergyHistory(c *gin.Context) {
	var history []models.EnergyHistory

	// 获取前端传来的设备编号。
	// 如果不传 device_id，则查询所有设备最近的数据。
	deviceID := c.Query("device_id")

	// 默认按 history_id 倒序，优先返回最新数据。
	db := config.DB.Order("history_id desc")

	// 如果传入了设备编号，则只查询该设备的历史数据。
	if deviceID != "" {
		db = db.Where("device_id = ?", deviceID)
	}

	// 限制返回最近50条，避免一次查询数据过多影响前端加载。
	if err := db.Limit(50).Find(&history).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询失败",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data":    history,
	})
}

// GetOverviewData 查询首页概览数据。
// 前端首页通常展示设备总数、报警总数和历史数据总数。
// 这些统计信息用于让用户快速了解平台当前运行情况。
func GetOverviewData(c *gin.Context) {
	var deviceCount int64
	var alarmCount int64
	var historyCount int64

	// 查询设备总数。
	if err := config.DB.Model(&models.DeviceInfo{}).Count(&deviceCount).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"message": "查询设备总数失败"})
		return
	}

	// 查询报警记录总数。
	if err := config.DB.Model(&models.AlarmRecord{}).Count(&alarmCount).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"message": "查询报警总数失败"})
		return
	}

	// 查询历史能耗数据总数。
	if err := config.DB.Model(&models.EnergyHistory{}).Count(&historyCount).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"message": "查询历史数据总数失败"})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data": gin.H{
			"device_count":  deviceCount,
			"alarm_count":   alarmCount,
			"history_count": historyCount,
		},
	})
}

// EnergyRankingItem 定义设备能耗排行接口返回的数据结构。
type EnergyRankingItem struct {
	DeviceID    uint    `json:"device_id"`    // 设备编号
	DeviceName  string  `json:"device_name"`  // 设备名称
	TotalEnergy float64 `json:"total_energy"` // 指定时间范围内的能耗
	AvgPower    float64 `json:"avg_power"`    // 指定时间范围内的平均功率
}

// GetEnergyRanking 查询设备能耗排行。
// 前端能耗排行图会调用该接口。
// 查询逻辑：
// 在指定日期范围内，根据每台设备累计能耗的最大值和最小值之差，计算阶段能耗。
func GetEnergyRanking(c *gin.Context) {
	// 获取查询日期。
	// 如果前端未传日期，则默认查询当天。
	startDate := c.DefaultQuery("start_date", time.Now().Format("2006-01-02"))
	endDate := c.DefaultQuery("end_date", time.Now().Format("2006-01-02"))

	startDateTime := startDate + " 00:00:00"
	endDateTime := endDate + " 23:59:59"

	var result []EnergyRankingItem

	// 通过 LEFT JOIN 保证即使某台设备在该时间范围内没有历史数据，
	// 也能在排行结果中出现，能耗和平均功率用0表示。
	sql := `
		SELECT
			d.device_id,
			d.device_name,
			COALESCE(ROUND(MAX(e.energy_total) - MIN(e.energy_total), 2), 0) AS total_energy,
			COALESCE(ROUND(AVG(e.power), 2), 0) AS avg_power
		FROM device_info d
		LEFT JOIN energy_history e
			ON d.device_id = e.device_id
		   AND e.record_time BETWEEN ? AND ?
		GROUP BY d.device_id, d.device_name
		ORDER BY total_energy DESC, d.device_id ASC
	`

	if err := config.DB.Raw(sql, startDateTime, endDateTime).Scan(&result).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询设备能耗排行失败",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data":    result,
	})
}

// CompareResult 定义同比、环比分析接口返回的数据结构。
type CompareResult struct {
	DeviceID     uint    `json:"device_id"`     // 设备编号
	DeviceName   string  `json:"device_name"`   // 设备名称
	CurrentLabel string  `json:"current_label"` // 当前周期标签，例如 2026-04
	CompareLabel string  `json:"compare_label"` // 对比周期标签，例如去年同期或上月
	CurrentValue float64 `json:"current_value"` // 当前周期能耗
	CompareValue float64 `json:"compare_value"` // 对比周期能耗
	ChangeRate   float64 `json:"change_rate"`   // 变化率，单位 %
}

// energyTotalResult 用于接收 SQL 聚合查询结果。
type energyTotalResult struct {
	TotalEnergy float64 `json:"total_energy"`
}

// queryMonthTotalEnergy 查询某设备在指定月份的能耗。
// 计算方式：
// 月内最大累计能耗 - 月内最小累计能耗。
func queryMonthTotalEnergy(deviceID uint, month string) (float64, error) {
	var result energyTotalResult

	sql := `
		SELECT COALESCE(ROUND(MAX(energy_total) - MIN(energy_total), 2), 0) AS total_energy
		FROM energy_history
		WHERE device_id = ?
		  AND DATE_FORMAT(record_time, '%Y-%m') = ?
	`

	err := config.DB.Raw(sql, deviceID, month).Scan(&result).Error
	return result.TotalEnergy, err
}

// GetYoYAnalysis 查询同比分析结果。
// 同比：当前月份与去年同月进行比较。
// 例如当前月份为 2026-04，则对比月份为 2025-04。
func GetYoYAnalysis(c *gin.Context) {
	// 获取设备ID，默认查询设备1。
	deviceIDStr := c.DefaultQuery("device_id", "1")

	// 获取月份，默认当前月份。
	month := c.DefaultQuery("month", time.Now().Format("2006-01"))

	deviceIDInt, err := strconv.Atoi(deviceIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "设备ID错误",
		})
		return
	}
	deviceID := uint(deviceIDInt)

	// 校验设备是否存在。
	var device models.DeviceInfo
	if err := config.DB.Where("device_id = ?", deviceID).First(&device).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"message": "设备不存在",
		})
		return
	}

	// 校验月份格式。
	currentTime, err := time.Parse("2006-01", month)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "月份格式错误，应为 YYYY-MM",
		})
		return
	}

	// 去年同期月份。
	compareMonth := currentTime.AddDate(-1, 0, 0).Format("2006-01")

	// 查询当前月份能耗。
	currentValue, err := queryMonthTotalEnergy(deviceID, month)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询当前月份数据失败",
		})
		return
	}

	// 查询去年同期能耗。
	compareValue, err := queryMonthTotalEnergy(deviceID, compareMonth)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询去年同期数据失败",
		})
		return
	}

	// 计算变化率。
	// 如果去年同期能耗为0，则变化率记为0，避免除零错误。
	changeRate := 0.0
	if compareValue != 0 {
		changeRate = (currentValue - compareValue) / compareValue * 100
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data": CompareResult{
			DeviceID:     deviceID,
			DeviceName:   device.DeviceName,
			CurrentLabel: month,
			CompareLabel: compareMonth,
			CurrentValue: currentValue,
			CompareValue: compareValue,
			ChangeRate:   changeRate,
		},
	})
}

// GetMoMAnalysis 查询环比分析结果。
// 环比：当前月份与上一个月份进行比较。
// 例如当前月份为 2026-04，则对比月份为 2026-03。
func GetMoMAnalysis(c *gin.Context) {
	// 获取设备ID，默认查询设备1。
	deviceIDStr := c.DefaultQuery("device_id", "1")

	// 获取月份，默认当前月份。
	month := c.DefaultQuery("month", time.Now().Format("2006-01"))

	deviceIDInt, err := strconv.Atoi(deviceIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "设备ID错误",
		})
		return
	}
	deviceID := uint(deviceIDInt)

	// 校验设备是否存在。
	var device models.DeviceInfo
	if err := config.DB.Where("device_id = ?", deviceID).First(&device).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"message": "设备不存在",
		})
		return
	}

	// 校验月份格式。
	currentTime, err := time.Parse("2006-01", month)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "月份格式错误，应为 YYYY-MM",
		})
		return
	}

	// 上月月份。
	compareMonth := currentTime.AddDate(0, -1, 0).Format("2006-01")

	// 查询当前月份能耗。
	currentValue, err := queryMonthTotalEnergy(deviceID, month)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询当前月份数据失败",
		})
		return
	}

	// 查询上月能耗。
	compareValue, err := queryMonthTotalEnergy(deviceID, compareMonth)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询上月数据失败",
		})
		return
	}

	// 计算变化率。
	changeRate := 0.0
	if compareValue != 0 {
		changeRate = (currentValue - compareValue) / compareValue * 100
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data": CompareResult{
			DeviceID:     deviceID,
			DeviceName:   device.DeviceName,
			CurrentLabel: month,
			CompareLabel: compareMonth,
			CurrentValue: currentValue,
			CompareValue: compareValue,
			ChangeRate:   changeRate,
		},
	})
}
//这个 controller 是后端能耗数据相关接口的核心文件。UploadEnergyData 接收 Python 采集端上传的清洗后数据，
// 先校验设备是否存在，再计算能耗增量并写入 energy_history 表，然后调用融合异常检测服务。如果检测到异常，就保存异常记录和报警记录。
// 其他接口主要服务前端展示，包括历史数据查询、首页概览、设备能耗排行、同比分析和环比分析。