package router

import (
	"backend/controllers"

	"github.com/gin-gonic/gin"
)

func RegisterRoutes(r *gin.Engine) {
	api := r.Group("/api")
	{
		api.POST("/login", controllers.Login)

		api.POST("/energy/upload", controllers.UploadEnergyData)
		api.GET("/alarms", controllers.GetAlarmList)
		api.PUT("/alarms/:id/process", controllers.ProcessAlarm)
		api.GET("/energy/history", controllers.GetEnergyHistory)
		api.GET("/overview", controllers.GetOverviewData)
		api.GET("/energy/ranking", controllers.GetEnergyRanking)
		api.GET("/energy/yoy", controllers.GetYoYAnalysis)
		api.GET("/energy/mom", controllers.GetMoMAnalysis)

		api.GET("/devices", controllers.GetDeviceList)
		api.POST("/devices", controllers.CreateDevice)
		api.PUT("/devices/:id", controllers.UpdateDevice)
		api.DELETE("/devices/:id", controllers.DeleteDevice)

		api.GET("/roles", controllers.GetRoleList)
		api.GET("/users", controllers.GetUserList)
		api.POST("/users", controllers.CreateUser)
		api.PUT("/users/:id", controllers.UpdateUser)
		api.DELETE("/users/:id", controllers.DeleteUser)

		api.GET("/reports/daily", controllers.GetDailyReport)
		api.GET("/reports/monthly", controllers.GetMonthlyReport)
		api.GET("/reports/alarm-stats", controllers.GetAlarmStatReport)
	}
}
