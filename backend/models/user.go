package models

import "time"

type User struct {
	UserID     uint      `gorm:"column:user_id;primaryKey" json:"user_id"`
	Username   string    `gorm:"column:username" json:"username"`
	Password   string    `gorm:"column:password" json:"password"`
	RealName   string    `gorm:"column:real_name" json:"real_name"`
	RoleID     uint      `gorm:"column:role_id" json:"role_id"`
	Status     int       `gorm:"column:status" json:"status"`
	CreateTime time.Time `gorm:"column:create_time" json:"create_time"`
}

func (User) TableName() string {
	return "user"
}
