package models

type Role struct {
	RoleID   uint   `gorm:"column:role_id;primaryKey" json:"role_id"`
	RoleName string `gorm:"column:role_name" json:"role_name"`
	RoleDesc string `gorm:"column:role_desc" json:"role_desc"`
}

func (Role) TableName() string {
	return "role"
}
