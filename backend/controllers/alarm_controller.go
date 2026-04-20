package controllers

import (
	"backend/config"
	"backend/models"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

type AlarmListItem struct {
	AlarmID       uint64 `json:"alarm_id"`
	DeviceID      uint   `json:"device_id"`
	DeviceName    string `json:"device_name"`
	AlarmType     string `json:"alarm_type"`
	AlarmLevel    string `json:"alarm_level"`
	AlarmContent  string `json:"alarm_content"`
	AlarmTime     string `json:"alarm_time"`
	ProcessStatus int    `json:"process_status"`
	ProcessUser   string `json:"process_user"`
	ProcessTime   string `json:"process_time"`
}

type ProcessAlarmRequest struct {
	ProcessUser string `json:"process_user"`
}

func GetAlarmList(c *gin.Context) {
	var alarms []models.AlarmRecord
	if err := config.DB.Order("alarm_id desc").Find(&alarms).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询报警记录失败",
		})
		return
	}

	var result []AlarmListItem
	for _, alarm := range alarms {
		var device models.DeviceInfo
		config.DB.Where("device_id = ?", alarm.DeviceID).First(&device)

		processTime := ""
		if !alarm.ProcessTime.IsZero() {
			processTime = alarm.ProcessTime.Format("2006-01-02 15:04:05")
		}

		result = append(result, AlarmListItem{
			AlarmID:       alarm.AlarmID,
			DeviceID:      alarm.DeviceID,
			DeviceName:    device.DeviceName,
			AlarmType:     alarm.AlarmType,
			AlarmLevel:    alarm.AlarmLevel,
			AlarmContent:  alarm.AlarmContent,
			AlarmTime:     alarm.AlarmTime.Format("2006-01-02 15:04:05"),
			ProcessStatus: alarm.ProcessStatus,
			ProcessUser:   alarm.ProcessUser,
			ProcessTime:   processTime,
		})
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data":    result,
	})
}

func ProcessAlarm(c *gin.Context) {
	id := c.Param("id")
	alarmID, err := strconv.Atoi(id)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "报警ID错误",
		})
		return
	}

	var req ProcessAlarmRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "请求参数错误",
		})
		return
	}

	var alarm models.AlarmRecord
	if err := config.DB.Where("alarm_id = ?", alarmID).First(&alarm).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"message": "报警记录不存在",
		})
		return
	}

	if alarm.ProcessStatus == 1 {
		c.JSON(http.StatusOK, gin.H{
			"message": "该报警已处理",
		})
		return
	}

	alarm.ProcessStatus = 1
	alarm.ProcessUser = req.ProcessUser
	alarm.ProcessTime = time.Now()

	if err := config.DB.Save(&alarm).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "更新报警状态失败",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "报警处理成功",
		"data":    alarm,
	})
}