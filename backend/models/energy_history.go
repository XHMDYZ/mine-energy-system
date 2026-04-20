package models

import "time"

type EnergyHistory struct {
	HistoryID       uint64    `gorm:"column:history_id;primaryKey" json:"history_id"`
	DeviceID        uint      `gorm:"column:device_id" json:"device_id"`
	Voltage         float64   `gorm:"column:voltage" json:"voltage"`
	Current         float64   `gorm:"column:current" json:"current"`
	Power           float64   `gorm:"column:power" json:"power"`
	EnergyIncrement float64   `gorm:"column:energy_increment" json:"energy_increment"`
	EnergyTotal     float64   `gorm:"column:energy_total" json:"energy_total"`
	RecordTime      time.Time `gorm:"column:record_time" json:"record_time"`
	DataSource      string    `gorm:"column:data_source" json:"data_source"`
}

func (EnergyHistory) TableName() string {
	return "energy_history"
}
