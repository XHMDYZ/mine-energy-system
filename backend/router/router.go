package router

import (
	// controllers 包中存放具体接口处理函数。
	// 路由层只负责“接口路径和处理函数的绑定”，
	// 真正的业务逻辑在 controllers 中完成。
	"backend/controllers"

	"github.com/gin-gonic/gin"
)

// RegisterRoutes 用于统一注册系统后端接口。
// main.go 中创建 Gin 服务后，会调用该函数完成全部接口配置。
func RegisterRoutes(r *gin.Engine) {
	// ============================================================
	// 1. 创建统一接口分组 /api
	// ============================================================
	// 所有后端接口都以 /api 开头，便于前端统一管理请求地址。
	// 例如：
	//   http://localhost:8080/api/login
	//   http://localhost:8080/api/energy/history
	api := r.Group("/api")
	{
		// ========================================================
		// 2. 登录接口
		// ========================================================
		// 前端登录页面调用该接口进行用户身份验证。
		// 登录成功后，前端根据返回的用户信息和角色信息展示对应菜单。
		api.POST("/login", controllers.Login)

		// ========================================================
		// 3. 能耗数据接入接口
		// ========================================================
		// Python 采集端 prosys_collector.py 清洗通过数据后，
		// 会调用该接口上传电压、电流、功率、累计能耗等数据。
		// 后端接收后写入 energy_history 表，并可触发异常检测逻辑。
		api.POST("/energy/upload", controllers.UploadEnergyData)

		// ========================================================
		// 4. 报警管理接口
		// ========================================================

		// 获取报警列表。
		// 前端报警页面通过该接口展示报警时间、设备、异常类型、处理状态等信息。
		api.GET("/alarms", controllers.GetAlarmList)

		// 处理报警接口。
		// 前端点击“处理”按钮后调用该接口，将报警记录更新为已处理状态。
		api.PUT("/alarms/:id/process", controllers.ProcessAlarm)

		// ========================================================
		// 5. 历史数据与首页概览接口
		// ========================================================

		// 查询设备历史能耗数据。
		// 前端历史趋势图通过该接口获取某台设备在指定时间范围内的电压、电流、功率等数据。
		api.GET("/energy/history", controllers.GetEnergyHistory)

		// 获取首页概览数据。
		// 例如设备数量、报警数量、历史数据总数等统计信息。
		api.GET("/overview", controllers.GetOverviewData)

		// ========================================================
		// 6. 能耗统计分析接口
		// ========================================================

		// 查询设备能耗排行。
		// 前端能耗排行图通过该接口比较不同设备的累计能耗或阶段能耗。
		api.GET("/energy/ranking", controllers.GetEnergyRanking)

		// 查询同比分析结果。
		// 用于比较当前周期与去年同期的能耗变化。
		api.GET("/energy/yoy", controllers.GetYoYAnalysis)

		// 查询环比分析结果。
		// 用于比较当前周期与上一周期的能耗变化。
		api.GET("/energy/mom", controllers.GetMoMAnalysis)

		// ========================================================
		// 7. 设备管理接口
		// ========================================================

		// 获取设备列表。
		api.GET("/devices", controllers.GetDeviceList)

		// 新增设备信息。
		api.POST("/devices", controllers.CreateDevice)

		// 修改设备信息。
		api.PUT("/devices/:id", controllers.UpdateDevice)

		// 删除设备信息。
		api.DELETE("/devices/:id", controllers.DeleteDevice)

		// ========================================================
		// 8. 用户与角色管理接口
		// ========================================================

		// 获取角色列表。
		// 前端用户管理页面可以根据角色信息分配用户权限。
		api.GET("/roles", controllers.GetRoleList)

		// 获取用户列表。
		api.GET("/users", controllers.GetUserList)

		// 新增用户。
		api.POST("/users", controllers.CreateUser)

		// 修改用户信息。
		api.PUT("/users/:id", controllers.UpdateUser)

		// 删除用户。
		api.DELETE("/users/:id", controllers.DeleteUser)

		// ========================================================
		// 9. 报表接口
		// ========================================================

		// 获取日报数据。
		// 用于展示某一天各设备能耗统计结果。
		api.GET("/reports/daily", controllers.GetDailyReport)

		// 获取月报数据。
		// 用于展示某个月各设备能耗统计结果。
		api.GET("/reports/monthly", controllers.GetMonthlyReport)

		// 获取报警统计报表。
		// 用于统计不同设备或不同类型异常报警数量。
		api.GET("/reports/alarm-stats", controllers.GetAlarmStatReport)
	}
}
//router 文件负责统一注册后端接口。所有接口都放在 /api 分组下，
// 包括登录、能耗数据上传、历史数据查询、报警管理、设备管理、用户管理和报表统计等。
// 这样前端和采集端调用接口时路径比较统一，后端代码结构也更清晰。