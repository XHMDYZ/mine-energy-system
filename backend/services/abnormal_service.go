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

// DetectResult 表示一次异常检测的结果。
// 后端在接收到一条新的能耗历史数据后，会调用 DetectAbnormal 进行检测，
// 并把检测结果封装到该结构体中。
type DetectResult struct {
	IsAbnormal     bool    // 是否异常
	AbnormalType   string  // 异常类型，例如“规则层-功率超限 + 变化率层-功率突变”
	AlarmLevel     string  // 报警等级：一般、重要、严重
	AbnormalScore  float64 // 异常综合得分
	RuleTriggered  string  // 被触发的检测规则
	CurrentPower   float64 // 当前功率
	ReferenceValue float64 // 参考值，例如额定功率阈值或历史中位功率
	ChangeRate     float64 // 当前功率相对上一时刻的变化率
	DeviationRate  float64 // 当前功率相对历史基准的偏差率
	AlarmContent   string  // 报警内容，用于写入报警记录表并展示到前端
}

// DetectAbnormal 执行融合异常检测。
// 该函数是本文规则融合异常检测方法的核心实现。
//
// 检测流程：
// 1. 查询当前数据之前的历史记录；
// 2. 规则层检测：判断功率超限、非法负值、累计能耗回跳；
// 3. 变化率层检测：判断当前功率是否发生短时突变；
// 4. 历史偏差层检测：判断当前功率是否明显偏离近期历史水平；
// 5. 融合判定：根据触发规则和综合得分生成异常等级与报警内容。
func DetectAbnormal(device models.DeviceInfo, current models.EnergyHistory) DetectResult {
	// 初始化检测结果，默认认为当前数据正常。
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

	// triggeredRules 用于保存本次检测触发的规则名称。
	var triggeredRules []string

	// score 为异常综合得分。
	// 不同检测层触发后会累加不同分值。
	score := 0.0

	// ============================================================
	// 查询当前记录之前的历史记录
	// ============================================================
	// 注意这里使用 history_id < current.HistoryID，
	// 目的是避免把当前数据本身混入历史基准中。
	//
	// recent 按 history_id 倒序排列：
	// recent[0] 是当前记录之前最近的一条历史数据。
	var recent []models.EnergyHistory
	_ = config.DB.
		Where("device_id = ? AND history_id < ?", current.DeviceID, current.HistoryID).
		Order("history_id desc").
		Limit(20).
		Find(&recent).Error

	// ============================================================
	// 1. 规则层检测
	// ============================================================
	// 规则层主要用于识别非常明确、解释性强的异常，
	// 例如功率超过设备额定范围、采集值出现非法负数、累计能耗回跳等。
	//
	// 这一层的优点是简单、直观、便于解释，
	// 适合作为异常检测的第一层初筛。

	// 1.1 功率超限检测。
	// 如果设备配置了额定功率，则将额定功率的1.2倍作为功率超限阈值。
	// 当前功率超过该阈值时，认为设备可能存在明显异常运行状态。
	if device.RatedPower > 0 {
		threshold := round2(device.RatedPower * 1.2)
		if current.Power > threshold {
			triggeredRules = append(triggeredRules, "规则层-功率超限")
			score += 40
			result.ReferenceValue = threshold
		}
	}

	// 1.2 非法负值检测。
	// 电压、电流、功率在正常采集情况下不应该为负。
	// 如果出现负值，通常说明数据采集或传输存在问题。
	if current.Power < 0 || current.Voltage < 0 || current.Current < 0 {
		triggeredRules = append(triggeredRules, "规则层-非法负值")
		score += 40
	}

	// 1.3 累计能耗回跳检测。
	// 正常情况下，同一设备的累计能耗应随时间递增或保持不变。
	// 如果当前累计能耗小于上一条历史记录的累计能耗，
	// 则说明可能存在采集异常或计量值重置问题。
	//
	// 注意：
	// Python 数据清洗端已经对累计能耗回跳进行过拦截，
	// 这里属于后端的二次保护。
	if len(recent) > 0 && current.EnergyTotal < recent[0].EnergyTotal {
		triggeredRules = append(triggeredRules, "规则层-累计能耗回跳")
		score += 40
	}

	// ============================================================
	// 2. 变化率层检测
	// ============================================================
	// 变化率层用于识别短时间内功率突增或突降。
	// 有些异常不一定超过额定功率阈值，
	// 但如果当前功率相对上一时刻变化过大，也可能反映设备运行状态异常。
	if len(recent) >= 1 && recent[0].Power > 0 {
		// 当前功率相对上一条历史功率的变化率，单位为百分比。
		currentRate := (current.Power - recent[0].Power) / (recent[0].Power + 0.0001) * 100
		result.ChangeRate = round2(currentRate)

		// historyRates 用于保存近期历史相邻点之间的变化率。
		// 后续用这些历史变化率计算中位数和 MAD，
		// 从而判断当前变化率是否明显偏离历史变化水平。
		historyRates := make([]float64, 0)
		for i := 0; i < len(recent)-1; i++ {
			base := recent[i+1].Power
			if math.Abs(base) < 0.0001 {
				continue
			}

			r := (recent[i].Power - base) / (base + 0.0001) * 100
			historyRates = append(historyRates, r)
		}

		// 如果历史变化率数量足够，则使用中位数和 MAD 进行稳健判断。
		if len(historyRates) >= 3 {
			medRate := median(historyRates)
			madRate := mad(historyRates, medRate)

			// band 表示允许波动范围。
			// 取 3*MAD 和 30 中较大的值，
			// 是为了避免历史数据过于平稳时，轻微变化也被误判为突变。
			band := math.Max(3*madRate, 30)

			if math.Abs(currentRate-medRate) > band {
				triggeredRules = append(triggeredRules, "变化率层-功率突变")
				score += 30

				// 如果前面还没有设置参考值，则使用上一时刻功率作为参考值。
				if result.ReferenceValue == 0 {
					result.ReferenceValue = round2(recent[0].Power)
				}
			}
		} else {
			// 如果历史记录太少，无法计算稳定的历史变化率，
			// 则使用固定变化率阈值作为兜底规则。
			if math.Abs(currentRate) > 50 {
				triggeredRules = append(triggeredRules, "变化率层-功率突变")
				score += 30

				if result.ReferenceValue == 0 {
					result.ReferenceValue = round2(recent[0].Power)
				}
			}
		}
	}

	// ============================================================
	// 3. 历史偏差层检测
	// ============================================================
	// 历史偏差层用于识别“当前功率虽然没有明显超限，
	// 但相对该设备近期历史运行水平明显偏高或偏低”的情况。
	//
	// 这一层可以弥补固定阈值法只关注额定功率上限的不足。
	// 例如设备长期处于偏高功率运行，可能还没有超过额定阈值，
	// 但已经偏离自身历史正常水平。
	if len(recent) >= 20 {
		historyPowers := make([]float64, 0, len(recent))
		for _, r := range recent {
			historyPowers = append(historyPowers, r.Power)
		}

		// 使用历史功率中位数作为基准值。
		// 中位数比平均值更不容易受到少量异常值影响。
		medPower := median(historyPowers)

		// 计算历史功率的 MAD，用于衡量历史波动程度。
		madPower := mad(historyPowers, medPower)

		// 计算当前功率相对历史中位数的偏差率。
		relativeDeviation := 0.0
		if math.Abs(medPower) > 0.0001 {
			relativeDeviation = (current.Power - medPower) / medPower * 100
		}
		result.DeviationRate = round2(relativeDeviation)

		// MAD 下限设置。
		// 如果历史功率过于平稳，MAD可能非常小，
		// 这会导致一点点正常波动都产生很大的 robustZ。
		// 因此设置一个下限，降低误报。
		madFloor := math.Max(medPower*0.05, 3.0)
		adjustedMad := math.Max(madPower, madFloor)

		// robustZ 是基于中位数和 MAD 的稳健异常程度指标。
		// 1.4826 是将 MAD 近似转换为标准差尺度时常用的系数。
		robustZ := math.Abs((current.Power - medPower) / (1.4826*adjustedMad + 0.0001))

		// 同时满足 robustZ 较大且相对偏差率超过10%，才触发历史偏差异常。
		// 这样可以减少轻微波动造成的误报。
		if robustZ > 3.5 && math.Abs(relativeDeviation) >= 10 {
			triggeredRules = append(triggeredRules, "历史偏差层-持续偏离")
			score += 30

			if result.ReferenceValue == 0 {
				result.ReferenceValue = round2(medPower)
			}
		}
	}

	// ============================================================
	// 4. 融合判定
	// ============================================================
	// 如果至少有一个检测规则被触发，则认为当前数据存在异常。
	// 最终异常类型由多个触发规则组合而成。
	if len(triggeredRules) > 0 {
		result.IsAbnormal = true

		// 去重后拼接规则名称，避免重复规则出现在结果中。
		result.RuleTriggered = strings.Join(uniqueStrings(triggeredRules), " + ")
		result.AbnormalScore = score
		result.AbnormalType = result.RuleTriggered

		// 根据综合得分划分报警等级。
		// score >= 70：说明可能同时触发多个异常规则，判定为严重；
		// score >= 40：说明至少触发较明确的规则异常，判定为重要；
		// score < 40：一般异常，后续会只进入异常结果表，不一定进入报警表。
		switch {
		case score >= 70:
			result.AlarmLevel = "严重"
		case score >= 40:
			result.AlarmLevel = "重要"
		default:
			result.AlarmLevel = "一般"
		}

		// 生成报警内容。
		// 前端报警列表中可以直接展示这段文字，
		// 帮助用户了解异常设备、触发规则、当前功率、参考值和变化率等信息。
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

// SaveAbnormalAndAlarm 保存异常检测结果和报警记录。
//
// 设计思路：
// 1. 所有检测到的异常都会写入 energy_abnormal_record 表，便于后续分析；
// 2. 只有达到一定分值的异常才写入 alarm_record 表，避免低风险波动造成报警页面噪声；
// 3. 这对应论文中的“异常评分机制”和“分级报警策略”。
func SaveAbnormalAndAlarm(device models.DeviceInfo, current models.EnergyHistory, detectResult DetectResult) error {
	// 如果没有异常，则不需要保存。
	if !detectResult.IsAbnormal {
		return nil
	}

	// ============================================================
	// 1. 保存异常检测结果
	// ============================================================
	// energy_abnormal_record 用于记录所有被检测出的异常结果，
	// 包括一般异常、重要异常和严重异常。
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

	// ============================================================
	// 2. 根据分值决定是否写入报警表
	// ============================================================
	// 这里体现“报警降噪”思想：
	// 低风险异常可以保留在异常结果表中，供后续分析；
	// 但不一定进入 alarm_record 报警表，避免报警页面被轻微波动刷屏。
	//
	// 当前逻辑：异常得分 < 40 时，不生成报警记录。
	if detectResult.AbnormalScore < 40 {
		return nil
	}

	// 重要或严重异常写入报警表。
	// 前端报警列表页面会读取 alarm_record 表并展示。
	alarm := models.AlarmRecord{
		DeviceID:      current.DeviceID,
		AlarmType:     detectResult.AbnormalType,
		AlarmLevel:    detectResult.AlarmLevel,
		AlarmContent:  detectResult.AlarmContent,
		AlarmTime:     time.Now(),
		ProcessStatus: 0, // 0表示未处理，前端处理后可更新状态
	}

	return config.DB.Create(&alarm).Error
}

// round2 保留两位小数。
// 用于变化率、参考值等结果展示，使前端显示更加整洁。
func round2(v float64) float64 {
	return math.Round(v*100) / 100
}

// median 计算中位数。
// 在历史偏差检测和变化率检测中，中位数比平均值更稳健，
// 不容易被少量异常点影响。
func median(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}

	// 拷贝一份数据，避免排序时修改原始切片。
	cp := make([]float64, len(values))
	copy(cp, values)

	sort.Float64s(cp)

	n := len(cp)
	if n%2 == 1 {
		return cp[n/2]
	}

	return (cp[n/2-1] + cp[n/2]) / 2
}

// mad 计算 Median Absolute Deviation，中文常称为中位数绝对偏差。
// 计算方式：
// 1. 先计算每个值与中位数 med 的绝对差；
// 2. 再对这些绝对差取中位数。
//
// MAD 用于衡量历史数据的波动程度。
// 相比标准差，MAD 对异常值更不敏感。
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

// uniqueStrings 对字符串切片去重。
// 用于避免同一检测规则重复出现在 RuleTriggered 中。
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
//这个 services 文件是后端规则融合异常检测的核心。
// DetectAbnormal 会在新数据写入 energy_history 后被调用，它先查询当前设备最近20条历史数据，然后依次进行三层检测：
// 第一层是设备约束规则，比如功率超限、非法负值、累计能耗回跳；
// 第二层是变化率检测，用于识别短时间内功率突增或突降；
// 第三层是历史偏差检测，用中位数和MAD判断当前功率是否明显偏离近期历史水平。
// 最后系统把触发规则转换成异常得分，并根据得分分为一般、重要和严重。SaveAbnormalAndAlarm 会把所有异常写入异常结果表，
// 但只有重要和严重异常才写入报警表，这样可以减少低风险异常对报警页面的干扰。