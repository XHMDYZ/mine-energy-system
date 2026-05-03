package main

import (
	"backend/config"
	"backend/router"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
)

func main() {
	config.InitDB()

	r := gin.Default()
	r.Use(cors.Default())
	router.RegisterRoutes(r)

	r.Run(":8080")
}
