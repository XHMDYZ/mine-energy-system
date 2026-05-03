package controllers

import (
	"backend/config"
	"backend/models"
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
)

type UserRequest struct {
	Username string `json:"username"`
	Password string `json:"password"`
	RealName string `json:"real_name"`
	RoleID   uint   `json:"role_id"`
	Status   int    `json:"status"`
}

type UserListItem struct {
	UserID     uint   `json:"user_id"`
	Username   string `json:"username"`
	Password   string `json:"password"`
	RealName   string `json:"real_name"`
	RoleID     uint   `json:"role_id"`
	RoleName   string `json:"role_name"`
	Status     int    `json:"status"`
	CreateTime string `json:"create_time"`
}

func GetRoleList(c *gin.Context) {
	var roles []models.Role

	if err := config.DB.Order("role_id asc").Find(&roles).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询角色列表失败",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data":    roles,
	})
}

func GetUserList(c *gin.Context) {
	var users []models.User
	if err := config.DB.Order("user_id asc").Find(&users).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "查询用户列表失败",
		})
		return
	}

	var result []UserListItem
	for _, user := range users {
		var role models.Role
		config.DB.Where("role_id = ?", user.RoleID).First(&role)

		result = append(result, UserListItem{
			UserID:     user.UserID,
			Username:   user.Username,
			Password:   user.Password,
			RealName:   user.RealName,
			RoleID:     user.RoleID,
			RoleName:   role.RoleName,
			Status:     user.Status,
			CreateTime: user.CreateTime.Format("2006-01-02 15:04:05"),
		})
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "查询成功",
		"data":    result,
	})
}

func CreateUser(c *gin.Context) {
	var req UserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "请求参数错误",
		})
		return
	}

	user := models.User{
		Username: req.Username,
		Password: req.Password,
		RealName: req.RealName,
		RoleID:   req.RoleID,
		Status:   req.Status,
	}

	if err := config.DB.Create(&user).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "新增用户失败，用户名可能重复",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "新增成功",
		"data":    user,
	})
}

func UpdateUser(c *gin.Context) {
	id := c.Param("id")
	userID, err := strconv.Atoi(id)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "用户ID错误",
		})
		return
	}

	var req UserRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "请求参数错误",
		})
		return
	}

	var user models.User
	if err := config.DB.Where("user_id = ?", userID).First(&user).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"message": "用户不存在",
		})
		return
	}

	user.Username = req.Username
	user.Password = req.Password
	user.RealName = req.RealName
	user.RoleID = req.RoleID
	user.Status = req.Status

	if err := config.DB.Save(&user).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "修改用户失败",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "修改成功",
		"data":    user,
	})
}

func DeleteUser(c *gin.Context) {
	id := c.Param("id")
	userID, err := strconv.Atoi(id)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{
			"message": "用户ID错误",
		})
		return
	}

	var user models.User
	if err := config.DB.Where("user_id = ?", userID).First(&user).Error; err != nil {
		c.JSON(http.StatusNotFound, gin.H{
			"message": "用户不存在",
		})
		return
	}

	if err := config.DB.Delete(&user).Error; err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{
			"message": "删除用户失败",
		})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"message": "删除成功",
	})
}
