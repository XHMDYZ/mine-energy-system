package controllers

import (
	"backend/config"
	"backend/models"
	"backend/services"
	"net/http"
	"time"
	"strconv"
	
	"github.com/gin-gonic/gin"
)

type EnergyUploadRequest struct {
	DeviceID    uint    `json:"device_id"`
	Voltage     float64 `json:"voltage"`
	Current     float64 `json:"current"`
	Power       float64 `json:"power"`
	EnergyTotal float64 `json:"energy_total"`
}

func UploadEnergyData(c *gin.Context) {
	var req EnergyUploadRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "请求参数错误",
		})
		return
	}

	// 1. 保存历史数据
	data := models.EnergyHistory{
		DeviceID:        req.DeviceID,
		Voltage:         req.Voltage,
		Current:         req.Current,
		Power:           req.Power,
		EnergyIncrement: 0,
		EnergyTotal:     req.EnergyTotal,
		RecordTime:      time.Now(),
		DataSource:      "python_mock",
	}

	if err := config.DB.Create(&data).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "数据保存失败",
		})
		return
	}

	// 2. 查设备信息
	var device models.DeviceInfo
	if err := config.DB.Where("device_id = ?", req.DeviceID).First(&device).Error; err == nil {
		// 3. 执行融合异常检测
		detectResult := services.DetectAbnormal(device, data)

		// 4. 保存异常结果和报警记录
		if detectResult.IsAbnormal {
			_ = services.SaveAbnormalAndAlarm(device, data, detectResult)
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "上传成功",
		"data":    data,
	})
}
func GetEnergyHistory(c *gin.Context) {
	var history []models.EnergyHistory

	// 可选：按设备过滤
	deviceID := c.Query("device_id")

	db := config.DB.Order("history_id desc")

	if deviceID != "" {
		db = db.Where("device_id = ?", deviceID)
	}

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
func GetOverviewData(c *gin.Context) {
	var deviceCount int64
	var alarmCount int64
	var historyCount int64

	if err := config.DB.Model(&models.DeviceInfo{}).Count(&deviceCount).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"message": "查询设备总数失败"})
		return
	}

	if err := config.DB.Model(&models.AlarmRecord{}).Count(&alarmCount).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"message": "查询报警总数失败"})
		return
	}

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
type EnergyRankingItem struct {
	DeviceID    uint    `json:"device_id"`
	DeviceName  string  `json:"device_name"`
	TotalEnergy float64 `json:"total_energy"`
	AvgPower    float64 `json:"avg_power"`
}

func GetEnergyRanking(c *gin.Context) {
	startDate := c.DefaultQuery("start_date", time.Now().Format("2006-01-02"))
	endDate := c.DefaultQuery("end_date", time.Now().Format("2006-01-02"))

	startDateTime := startDate + " 00:00:00"
	endDateTime := endDate + " 23:59:59"

	var result []EnergyRankingItem
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
type CompareResult struct {
	DeviceID     uint    `json:"device_id"`
	DeviceName   string  `json:"device_name"`
	CurrentLabel string  `json:"current_label"`
	CompareLabel string  `json:"compare_label"`
	CurrentValue float64 `json:"current_value"`
	CompareValue float64 `json:"compare_value"`
	ChangeRate   float64 `json:"change_rate"`
}

type energyTotalResult struct {
	TotalEnergy float64 `json:"total_energy"`
}

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

func GetYoYAnalysis(c *gin.Context) {
	deviceIDStr := c.DefaultQuery("device_id", "1")
	month := c.DefaultQuery("month", time.Now().Format("2006-01"))

	deviceIDInt, err := strconv.Atoi(deviceIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "设备ID错误",
		})
		return
	}
	deviceID := uint(deviceIDInt)

	var device models.DeviceInfo
	if err := config.DB.Where("device_id = ?", deviceID).First(&device).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"message": "设备不存在",
		})
		return
	}

	currentTime, err := time.Parse("2006-01", month)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "月份格式错误，应为 YYYY-MM",
		})
		return
	}

	compareMonth := currentTime.AddDate(-1, 0, 0).Format("2006-01")

	currentValue, err := queryMonthTotalEnergy(deviceID, month)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询当前月份数据失败",
		})
		return
	}

	compareValue, err := queryMonthTotalEnergy(deviceID, compareMonth)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询去年同期数据失败",
		})
		return
	}

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

func GetMoMAnalysis(c *gin.Context) {
	deviceIDStr := c.DefaultQuery("device_id", "1")
	month := c.DefaultQuery("month", time.Now().Format("2006-01"))

	deviceIDInt, err := strconv.Atoi(deviceIDStr)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "设备ID错误",
		})
		return
	}
	deviceID := uint(deviceIDInt)

	var device models.DeviceInfo
	if err := config.DB.Where("device_id = ?", deviceID).First(&device).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"message": "设备不存在",
		})
		return
	}

	currentTime, err := time.Parse("2006-01", month)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "月份格式错误，应为 YYYY-MM",
		})
		return
	}

	compareMonth := currentTime.AddDate(0, -1, 0).Format("2006-01")

	currentValue, err := queryMonthTotalEnergy(deviceID, month)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询当前月份数据失败",
		})
		return
	}

	compareValue, err := queryMonthTotalEnergy(deviceID, compareMonth)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询上月数据失败",
		})
		return
	}

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