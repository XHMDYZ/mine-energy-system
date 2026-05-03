package config

import (
	"fmt"
	"os"

	"gorm.io/driver/mysql"
	"gorm.io/gorm"
)

var DB *gorm.DB

func InitDB() {
	dsn := os.Getenv("MYSQL_DSN")
	if dsn == "" {
		panic("未设置环境变量 MYSQL_DSN")
	}

	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		panic("数据库连接失败")
	}

	sqlDB, err := db.DB()
	if err != nil {
		panic("获取底层数据库连接失败")
	}

	if _, err := sqlDB.Exec("SET time_zone = '+08:00'"); err != nil {
		panic("设置数据库时区失败")
	}

	DB = db
	fmt.Println("数据库连接成功")
}
