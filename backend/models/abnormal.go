package models

import "time"

type EnergyAbnormalRecord struct {
	AbnormalID     uint64    `gorm:"column:abnormal_id;primaryKey" json:"abnormal_id"`
	DeviceID       uint      `gorm:"column:device_id" json:"device_id"`
	AbnormalType   string    `gorm:"column:abnormal_type" json:"abnormal_type"`
	AbnormalScore  float64   `gorm:"column:abnormal_score" json:"abnormal_score"`
	RuleTriggered  string    `gorm:"column:rule_triggered" json:"rule_triggered"`
	CurrentPower   float64   `gorm:"column:current_power" json:"current_power"`
	ReferenceValue float64   `gorm:"column:reference_value" json:"reference_value"`
	ChangeRate     float64   `gorm:"column:change_rate" json:"change_rate"`
	DeviationRate  float64   `gorm:"column:deviation_rate" json:"deviation_rate"`
	DetectTime     time.Time `gorm:"column:detect_time" json:"detect_time"`
	CreateTime     time.Time `gorm:"column:create_time" json:"create_time"`
}

func (EnergyAbnormalRecord) TableName() string {
	return "energy_abnormal_record"
}
