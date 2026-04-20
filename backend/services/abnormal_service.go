package services

import (
	"backend/config"
	"backend/models"
	"fmt"
	"math"
	"strings"
	"time"
)

type DetectResult struct {
	IsAbnormal     bool
	AbnormalType   string
	AlarmLevel     string
	AbnormalScore  float64
	RuleTriggered  string
	CurrentPower   float64
	ReferenceValue float64
	ChangeRate     float64
	DeviationRate  float64
	AlarmContent   string
}

func DetectAbnormal(device models.DeviceInfo, current models.EnergyHistory) DetectResult {
	result := DetectResult{
		IsAbnormal:     false,
		AbnormalType:   "正常",
		AlarmLevel:     "",
		AbnormalScore:  0,
		RuleTriggered:  "",
		CurrentPower:   current.Power,
		ReferenceValue: 0,
		ChangeRate:     0,
		DeviationRate:  0,
		AlarmContent:   "",
	}

	var triggeredRules []string
	score := 0.0

	// 1. 阈值超限检测
	if device.RatedPower > 0 {
		threshold := device.RatedPower * 1.2
		if current.Power > threshold {
			triggeredRules = append(triggeredRules, "阈值超限")
			score += 40
			result.ReferenceValue = threshold
		}
	}

	// 2. 变化率检测：查上一条历史数据
	var prev models.EnergyHistory
	err := config.DB.
		Where("device_id = ? AND history_id < ?", current.DeviceID, current.HistoryID).
		Order("history_id desc").
		First(&prev).Error

	if err == nil && prev.Power > 0 {
		changeRate := (current.Power - prev.Power) / prev.Power * 100
		result.ChangeRate = round2(changeRate)

		if math.Abs(changeRate) > 50 {
			triggeredRules = append(triggeredRules, "功率突变")
			score += 30
			if result.ReferenceValue == 0 {
				result.ReferenceValue = prev.Power
			}
		}
	}

	// 3. 历史偏差检测：最近10条均值
	var records []models.EnergyHistory
	config.DB.
		Where("device_id = ?", current.DeviceID).
		Order("history_id desc").
		Limit(10).
		Find(&records)

	if len(records) >= 5 {
		sum := 0.0
		for _, r := range records {
			sum += r.Power
		}
		avg := sum / float64(len(records))

		if avg > 0 {
			deviationRate := (current.Power - avg) / avg * 100
			result.DeviationRate = round2(deviationRate)

			if math.Abs(deviationRate) > 30 {
				triggeredRules = append(triggeredRules, "历史偏差异常")
				score += 30
				if result.ReferenceValue == 0 {
					result.ReferenceValue = round2(avg)
				}
			}
		}
	}

	if len(triggeredRules) > 0 {
		result.IsAbnormal = true
		result.RuleTriggered = strings.Join(triggeredRules, " + ")
		result.AbnormalScore = score

		switch {
		case score >= 70:
			result.AlarmLevel = "严重"
		case score >= 40:
			result.AlarmLevel = "重要"
		default:
			result.AlarmLevel = "一般"
		}

		result.AbnormalType = result.RuleTriggered
		result.AlarmContent = fmt.Sprintf(
			"设备[%s]检测到异常：%s；当前功率 %.2f；变化率 %.2f%%；偏差率 %.2f%%",
			device.DeviceName,
			result.RuleTriggered,
			current.Power,
			result.ChangeRate,
			result.DeviationRate,
		)
	}

	return result
}

func SaveAbnormalAndAlarm(device models.DeviceInfo, current models.EnergyHistory, detectResult DetectResult) error {
	if !detectResult.IsAbnormal {
		return nil
	}

	abnormal := models.EnergyAbnormalRecord{
		DeviceID:       current.DeviceID,
		AbnormalType:   detectResult.AbnormalType,
		AbnormalScore:  detectResult.AbnormalScore,
		RuleTriggered:  detectResult.RuleTriggered,
		CurrentPower:   detectResult.CurrentPower,
		ReferenceValue: detectResult.ReferenceValue,
		ChangeRate:     detectResult.ChangeRate,
		DeviationRate:  detectResult.DeviationRate,
		DetectTime:     time.Now(),
		CreateTime:     time.Now(),
	}

	if err := config.DB.Create(&abnormal).Error; err != nil {
		return err
	}

	alarm := models.AlarmRecord{
		DeviceID:      current.DeviceID,
		AlarmType:     detectResult.AbnormalType,
		AlarmLevel:    detectResult.AlarmLevel,
		AlarmContent:  detectResult.AlarmContent,
		AlarmTime:     time.Now(),
		ProcessStatus: 0,
	}

	return config.DB.Create(&alarm).Error
}

func round2(v float64) float64 {
	return math.Round(v*100) / 100
}