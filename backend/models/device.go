package models

type DeviceInfo struct {
	DeviceID   uint    `gorm:"column:device_id;primaryKey" json:"device_id"`
	DeviceCode string  `gorm:"column:device_code" json:"device_code"`
	DeviceName string  `gorm:"column:device_name" json:"device_name"`
	DeviceType string  `gorm:"column:device_type" json:"device_type"`
	Location   string  `gorm:"column:location" json:"location"`
	AreaName   string  `gorm:"column:area_name" json:"area_name"`
	RatedPower float64 `gorm:"column:rated_power" json:"rated_power"`
	Status     int     `gorm:"column:status" json:"status"`
	Remark     string  `gorm:"column:remark" json:"remark"`
}

func (DeviceInfo) TableName() string {
	return "device_info"
}
