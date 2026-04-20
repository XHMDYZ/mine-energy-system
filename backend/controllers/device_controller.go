package controllers

import (
	"backend/config"
	"backend/models"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
)

type DeviceRequest struct {
	DeviceCode string  `json:"device_code"`
	DeviceName string  `json:"device_name"`
	DeviceType string  `json:"device_type"`
	Location   string  `json:"location"`
	AreaName   string  `json:"area_name"`
	RatedPower float64 `json:"rated_power"`
	Status     int     `json:"status"`
	Remark     string  `json:"remark"`
}

func GetDeviceList(c *gin.Context) {
	var devices []models.DeviceInfo

	if err := config.DB.Order("device_id asc").Find(&devices).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询设备列表失败",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data":    devices,
	})
}

func CreateDevice(c *gin.Context) {
	var req DeviceRequest

	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "请求参数错误",
		})
		return
	}

	device := models.DeviceInfo{
		DeviceCode: req.DeviceCode,
		DeviceName: req.DeviceName,
		DeviceType: req.DeviceType,
		Location:   req.Location,
		AreaName:   req.AreaName,
		RatedPower: req.RatedPower,
		Status:     req.Status,
		Remark:     req.Remark,
	}

	if err := config.DB.Create(&device).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "新增设备失败，设备编码可能重复",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "新增成功",
		"data":    device,
	})
}

func UpdateDevice(c *gin.Context) {
	id := c.Param("id")
	deviceID, err := strconv.Atoi(id)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "设备ID错误",
		})
		return
	}

	var req DeviceRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "请求参数错误",
		})
		return
	}

	var device models.DeviceInfo
	if err := config.DB.Where("device_id = ?", deviceID).First(&device).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"message": "设备不存在",
		})
		return
	}

	device.DeviceCode = req.DeviceCode
	device.DeviceName = req.DeviceName
	device.DeviceType = req.DeviceType
	device.Location = req.Location
	device.AreaName = req.AreaName
	device.RatedPower = req.RatedPower
	device.Status = req.Status
	device.Remark = req.Remark

	if err := config.DB.Save(&device).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "修改失败",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "修改成功",
		"data":    device,
	})
}

func DeleteDevice(c *gin.Context) {
	id := c.Param("id")
	deviceID, err := strconv.Atoi(id)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "设备ID错误",
		})
		return
	}

	var device models.DeviceInfo
	if err := config.DB.Where("device_id = ?", deviceID).First(&device).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"message": "设备不存在",
		})
		return
	}

	if err := config.DB.Delete(&device).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "删除失败",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "删除成功",
	})
}