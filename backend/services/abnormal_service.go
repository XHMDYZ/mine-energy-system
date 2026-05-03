package services

import (
	"backend/config"
	"backend/models"
	"fmt"
	"math"
	"sort"
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

	// 查询当前记录之前的历史记录，避免把当前值混进基线
	var recent []models.EnergyHistory
	_ = config.DB.
		Where("device_id = ? AND history_id < ?", current.DeviceID, current.HistoryID).
		Order("history_id desc").
		Limit(20).
		Find(&recent).Error

	// -----------------------------
	// 1. 规则层检测
	// -----------------------------
	if device.RatedPower > 0 {
		threshold := round2(device.RatedPower * 1.2)
		if current.Power > threshold {
			triggeredRules = append(triggeredRules, "规则层-功率超限")
			score += 40
			result.ReferenceValue = threshold
		}
	}

	if current.Power < 0 || current.Voltage < 0 || current.Current < 0 {
		triggeredRules = append(triggeredRules, "规则层-非法负值")
		score += 40
	}

	if len(recent) > 0 && current.EnergyTotal < recent[0].EnergyTotal {
		triggeredRules = append(triggeredRules, "规则层-累计能耗回跳")
		score += 40
	}

	// -----------------------------
	// 2. 变化率层检测
	// -----------------------------
	if len(recent) >= 1 && recent[0].Power > 0 {
		currentRate := (current.Power - recent[0].Power) / (recent[0].Power + 0.0001) * 100
		result.ChangeRate = round2(currentRate)

		historyRates := make([]float64, 0)
		for i := 0; i < len(recent)-1; i++ {
			base := recent[i+1].Power
			if math.Abs(base) < 0.0001 {
				continue
			}
			r := (recent[i].Power - base) / (base + 0.0001) * 100
			historyRates = append(historyRates, r)
		}

		if len(historyRates) >= 3 {
			medRate := median(historyRates)
			madRate := mad(historyRates, medRate)

			band := math.Max(3*madRate, 30)

			if math.Abs(currentRate-medRate) > band {
				triggeredRules = append(triggeredRules, "变化率层-功率突变")
				score += 30
				if result.ReferenceValue == 0 {
					result.ReferenceValue = round2(recent[0].Power)
				}
			}
		} else {
			if math.Abs(currentRate) > 50 {
				triggeredRules = append(triggeredRules, "变化率层-功率突变")
				score += 30
				if result.ReferenceValue == 0 {
					result.ReferenceValue = round2(recent[0].Power)
				}
			}
		}
	}

	// -----------------------------
	// 3. 历史偏差层检测（优化版，降低误报）
	// -----------------------------
	if len(recent) >= 20 {
		historyPowers := make([]float64, 0, len(recent))
		for _, r := range recent {
			historyPowers = append(historyPowers, r.Power)
		}

		medPower := median(historyPowers)
		madPower := mad(historyPowers, medPower)

		relativeDeviation := 0.0
		if math.Abs(medPower) > 0.0001 {
			relativeDeviation = (current.Power - medPower) / medPower * 100
		}
		result.DeviationRate = round2(relativeDeviation)

		// MAD 下限，避免历史过于平稳导致轻微波动触发
		madFloor := math.Max(medPower*0.05, 3.0)
		adjustedMad := math.Max(madPower, madFloor)

		robustZ := math.Abs((current.Power - medPower) / (1.4826*adjustedMad + 0.0001))

		if robustZ > 3.5 && math.Abs(relativeDeviation) >= 10 {
			triggeredRules = append(triggeredRules, "历史偏差层-持续偏离")
			score += 30
			if result.ReferenceValue == 0 {
				result.ReferenceValue = round2(medPower)
			}
		}
	}

	// -----------------------------
	// 4. 融合判定
	// -----------------------------
	if len(triggeredRules) > 0 {
		result.IsAbnormal = true
		result.RuleTriggered = strings.Join(uniqueStrings(triggeredRules), " + ")
		result.AbnormalScore = score
		result.AbnormalType = result.RuleTriggered

		switch {
		case score >= 70:
			result.AlarmLevel = "严重"
		case score >= 40:
			result.AlarmLevel = "重要"
		default:
			result.AlarmLevel = "一般"
		}

		result.AlarmContent = fmt.Sprintf(
			"设备[%s]检测到异常：%s；当前功率 %.2f kW；参考值 %.2f；变化率 %.2f%%；偏差率 %.2f%%；综合得分 %.0f",
			device.DeviceName,
			result.RuleTriggered,
			current.Power,
			result.ReferenceValue,
			result.ChangeRate,
			result.DeviationRate,
			result.AbnormalScore,
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

	// 仅对“重要/严重”级别写报警表，降低报警噪声
	if detectResult.AbnormalScore < 40 {
		return nil
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

func median(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	cp := make([]float64, len(values))
	copy(cp, values)
	sort.Float64s(cp)

	n := len(cp)
	if n%2 == 1 {
		return cp[n/2]
	}
	return (cp[n/2-1] + cp[n/2]) / 2
}

func mad(values []float64, med float64) float64 {
	if len(values) == 0 {
		return 0
	}
	deviations := make([]float64, 0, len(values))
	for _, v := range values {
		deviations = append(deviations, math.Abs(v-med))
	}
	return median(deviations)
}

func uniqueStrings(items []string) []string {
	m := map[string]bool{}
	result := []string{}
	for _, item := range items {
		if item == "" {
			continue
		}
		if !m[item] {
			m[item] = true
			result = append(result, item)
		}
	}
	return result
}
