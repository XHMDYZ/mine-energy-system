package controllers

import (
	"backend/config"
	"backend/models"
	"net/http"

	"github.com/gin-gonic/gin"
)

type LoginRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
}

func Login(c *gin.Context) {
	var req LoginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "请求参数错误",
		})
		return
	}

	var user models.User
	err := config.DB.Where("username = ? AND password = ? AND status = 1", req.Username, req.Password).First(&user).Error
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{
			"message": "用户名或密码错误",
		})
		return
	}

	var role models.Role
	config.DB.Where("role_id = ?", user.RoleID).First(&role)

	c.JSON(http.StatusOK, gin.H{
		"message": "登录成功",
		"data": gin.H{
			"user_id":   user.UserID,
			"username":  user.Username,
			"real_name": user.RealName,
			"role_id":   user.RoleID,
			"role_name": role.RoleName,
		},
	})
}
