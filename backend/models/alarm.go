package models

import "time"

type AlarmRecord struct {
	AlarmID       uint64    `gorm:"column:alarm_id;primaryKey" json:"alarm_id"`
	DeviceID      uint      `gorm:"column:device_id" json:"device_id"`
	AlarmType     string    `gorm:"column:alarm_type" json:"alarm_type"`
	AlarmLevel    string    `gorm:"column:alarm_level" json:"alarm_level"`
	AlarmContent  string    `gorm:"column:alarm_content" json:"alarm_content"`
	AlarmTime     time.Time `gorm:"column:alarm_time" json:"alarm_time"`
	ProcessStatus int       `gorm:"column:process_status" json:"process_status"`
	ProcessUser   string    `gorm:"column:process_user" json:"process_user"`
	ProcessTime   time.Time `gorm:"column:process_time" json:"process_time"`
}

func (AlarmRecord) TableName() string {
	return "alarm_record"
}
