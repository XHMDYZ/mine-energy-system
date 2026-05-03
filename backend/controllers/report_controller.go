package controllers

import (
	"backend/config"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
)

type DailyReportItem struct {
	DeviceID    uint    `json:"device_id"`
	DeviceName  string  `json:"device_name"`
	StatDate    string  `json:"stat_date"`
	TotalEnergy float64 `json:"total_energy"`
	AvgPower    float64 `json:"avg_power"`
	MaxPower    float64 `json:"max_power"`
	MinPower    float64 `json:"min_power"`
	AlarmCount  int     `json:"alarm_count"`
}

type MonthlyReportItem struct {
	DeviceID    uint    `json:"device_id"`
	DeviceName  string  `json:"device_name"`
	StatMonth   string  `json:"stat_month"`
	TotalEnergy float64 `json:"total_energy"`
	AvgPower    float64 `json:"avg_power"`
	MaxPower    float64 `json:"max_power"`
	MinPower    float64 `json:"min_power"`
	AlarmCount  int     `json:"alarm_count"`
}

type AlarmStatItem struct {
	DeviceID         uint   `json:"device_id"`
	DeviceName       string `json:"device_name"`
	AlarmCount       int    `json:"alarm_count"`
	UnprocessedCount int    `json:"unprocessed_count"`
	SevereCount      int    `json:"severe_count"`
}

func GetDailyReport(c *gin.Context) {
	date := c.DefaultQuery("date", time.Now().Format("2006-01-02"))

	var result []DailyReportItem
	sql := `
		SELECT
			d.device_id,
			d.device_name,
			? AS stat_date,
			COALESCE(ROUND(MAX(e.energy_total) - MIN(e.energy_total), 2), 0) AS total_energy,
			COALESCE(ROUND(AVG(e.power), 2), 0) AS avg_power,
			COALESCE(ROUND(MAX(e.power), 2), 0) AS max_power,
			COALESCE(ROUND(MIN(e.power), 2), 0) AS min_power,
			(
				SELECT COUNT(*)
				FROM alarm_record ar
				WHERE ar.device_id = d.device_id
				  AND DATE(ar.alarm_time) = ?
			) AS alarm_count
		FROM device_info d
		LEFT JOIN energy_history e
			ON d.device_id = e.device_id
		   AND DATE(e.record_time) = ?
		GROUP BY d.device_id, d.device_name
		ORDER BY d.device_id ASC
	`

	if err := config.DB.Raw(sql, date, date, date).Scan(&result).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询日报表失败",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data":    result,
	})
}

func GetMonthlyReport(c *gin.Context) {
	month := c.DefaultQuery("month", time.Now().Format("2006-01"))

	var result []MonthlyReportItem
	sql := `
		SELECT
			d.device_id,
			d.device_name,
			? AS stat_month,
			COALESCE(ROUND(MAX(e.energy_total) - MIN(e.energy_total), 2), 0) AS total_energy,
			COALESCE(ROUND(AVG(e.power), 2), 0) AS avg_power,
			COALESCE(ROUND(MAX(e.power), 2), 0) AS max_power,
			COALESCE(ROUND(MIN(e.power), 2), 0) AS min_power,
			(
				SELECT COUNT(*)
				FROM alarm_record ar
				WHERE ar.device_id = d.device_id
				  AND DATE_FORMAT(ar.alarm_time, '%Y-%m') = ?
			) AS alarm_count
		FROM device_info d
		LEFT JOIN energy_history e
			ON d.device_id = e.device_id
		   AND DATE_FORMAT(e.record_time, '%Y-%m') = ?
		GROUP BY d.device_id, d.device_name
		ORDER BY d.device_id ASC
	`

	if err := config.DB.Raw(sql, month, month, month).Scan(&result).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询月报表失败",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data":    result,
	})
}

func GetAlarmStatReport(c *gin.Context) {
	startDate := c.DefaultQuery("start_date", time.Now().Format("2006-01-02"))
	endDate := c.DefaultQuery("end_date", time.Now().Format("2006-01-02"))

	endDateTime := endDate + " 23:59:59"
	startDateTime := startDate + " 00:00:00"

	var result []AlarmStatItem
	sql := `
		SELECT
			d.device_id,
			d.device_name,
			COALESCE(COUNT(ar.alarm_id), 0) AS alarm_count,
			COALESCE(SUM(CASE WHEN ar.process_status = 0 THEN 1 ELSE 0 END), 0) AS unprocessed_count,
			COALESCE(SUM(CASE WHEN ar.alarm_level = '严重' THEN 1 ELSE 0 END), 0) AS severe_count
		FROM device_info d
		LEFT JOIN alarm_record ar
			ON d.device_id = ar.device_id
		   AND ar.alarm_time BETWEEN ? AND ?
		GROUP BY d.device_id, d.device_name
		ORDER BY d.device_id ASC
	`

	if err := config.DB.Raw(sql, startDateTime, endDateTime).Scan(&result).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询异常统计报表失败",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data":    result,
	})
}
