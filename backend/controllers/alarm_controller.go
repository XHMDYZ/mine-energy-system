package controllers

import (
	"backend/config"
	"backend/models"
	"net/http"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
)

// AlarmListItem 定义前端报警列表需要展示的数据结构。
// 这里没有直接把 alarm_record 表原样返回给前端，
// 而是额外拼接了设备名称，并把时间格式化成字符串，方便前端页面直接展示。
type AlarmListItem struct {
	AlarmID       uint64 `json:"alarm_id"`       // 报警编号
	DeviceID      uint   `json:"device_id"`      // 设备编号
	DeviceName    string `json:"device_name"`    // 设备名称，从 device_info 表查询得到
	AlarmType     string `json:"alarm_type"`     // 报警类型，例如功率超限、功率突变等
	AlarmLevel    string `json:"alarm_level"`    // 报警等级，例如重要、严重
	AlarmContent  string `json:"alarm_content"`  // 报警详细内容
	AlarmTime     string `json:"alarm_time"`     // 报警时间，格式化后返回给前端
	ProcessStatus int    `json:"process_status"` // 处理状态：0表示未处理，1表示已处理
	ProcessUser   string `json:"process_user"`   // 处理人
	ProcessTime   string `json:"process_time"`   // 处理时间，未处理时为空字符串
}

// ProcessAlarmRequest 定义处理报警时前端提交的请求结构。
// 前端点击“处理”按钮后，需要传入处理人信息。
type ProcessAlarmRequest struct {
	ProcessUser string `json:"process_user"` // 报警处理人
}

// GetAlarmList 查询报警列表。
// 对应接口：GET /api/alarms
//
// 主要流程：
// 1. 从 alarm_record 表中查询报警记录；
// 2. 按 alarm_id 倒序排列，使最新报警显示在前面；
// 3. 根据每条报警的 device_id 查询设备名称；
// 4. 格式化报警时间和处理时间；
// 5. 返回给前端报警列表页面展示。
func GetAlarmList(c *gin.Context) {
	// 查询全部报警记录，按报警ID倒序排列。
	// 这样前端报警列表中最新生成的报警会显示在最前面。
	var alarms []models.AlarmRecord
	if err := config.DB.Order("alarm_id desc").Find(&alarms).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询报警记录失败",
		})
		return
	}

	// result 用于保存返回给前端的报警列表数据。
	var result []AlarmListItem

	for _, alarm := range alarms {
		// 根据报警记录中的 DeviceID 查询设备基础信息。
		// 这样前端可以显示“主通风机”“排水泵”等设备名称，
		// 而不是只显示 device_id。
		var device models.DeviceInfo
		config.DB.Where("device_id = ?", alarm.DeviceID).First(&device)

		// 如果报警还没有被处理，ProcessTime 通常是零值时间。
		// 这里将零值时间处理为空字符串，避免前端显示默认时间。
		processTime := ""
		if !alarm.ProcessTime.IsZero() {
			processTime = alarm.ProcessTime.Format("2006-01-02 15:04:05")
		}

		// 将数据库中的报警记录转换为前端展示结构。
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

	// 返回报警列表给前端。
	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data":    result,
	})
}

// ProcessAlarm 处理报警记录。
// 对应接口：PUT /api/alarms/:id/process
//
// 主要流程：
// 1. 从 URL 参数中获取报警ID；
// 2. 解析前端提交的处理人信息；
// 3. 查询对应报警记录是否存在；
// 4. 如果已经处理，则直接返回提示；
// 5. 如果未处理，则更新处理状态、处理人和处理时间；
// 6. 保存更新结果并返回给前端。
func ProcessAlarm(c *gin.Context) {
	// 从路由参数中获取报警ID。
	// 例如 /api/alarms/12/process 中的 12。
	id := c.Param("id")

	// 将字符串形式的ID转换为整数。
	alarmID, err := strconv.Atoi(id)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "报警ID错误",
		})
		return
	}

	// 解析前端提交的 JSON 请求体。
	// 请求体中主要包含 process_user。
	var req ProcessAlarmRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "请求参数错误",
		})
		return
	}

	// 根据 alarm_id 查询报警记录。
	var alarm models.AlarmRecord
	if err := config.DB.Where("alarm_id = ?", alarmID).First(&alarm).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"message": "报警记录不存在",
		})
		return
	}

	// 如果报警已经处理过，则不重复处理。
	// 这样可以避免同一条报警被多次更新。
	if alarm.ProcessStatus == 1 {
		c.JSON(http.StatusOK, gin.H{
			"message": "该报警已处理",
		})
		return
	}

	// 更新报警处理状态。
	// ProcessStatus = 1 表示已处理。
	alarm.ProcessStatus = 1

	// 保存处理人。
	alarm.ProcessUser = req.ProcessUser

	// 保存处理时间。
	alarm.ProcessTime = time.Now()

	// 将更新后的报警记录保存到数据库。
	if err := config.DB.Save(&alarm).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "更新报警状态失败",
		})
		return
	}

	// 返回处理成功结果。
	c.JSON(http.StatusOK, gin.H{
		"message": "报警处理成功",
		"data":    alarm,
	})
}
//alarm_controller.go 主要对应前端报警列表页面。GetAlarmList 会从报警表中查询所有报警记录，
// 并根据 device_id 补充设备名称，然后把报警时间、报警等级、报警内容和处理状态返回给前端。
// ProcessAlarm 用于处理报警，前端点击处理按钮后，后端会把该报警更新为已处理，并记录处理人和处理时间。