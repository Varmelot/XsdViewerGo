package main

import (
	"embed"
	"os"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

//go:embed all:frontend/dist
var assets embed.FS

func main() {
	var initialFile string
	if len(os.Args) > 1 {
		initialFile = os.Args[1]
	}

	app := NewApp(initialFile)

	err := wails.Run(&options.App{
		Title:  "XSD Viewer Pro",
		Width:  1500,
		Height: 900,
		AssetServer: &assetserver.Options{
			Assets: assets,
		},
		BackgroundColour: &options.RGBA{R: 255, G: 255, B: 255, A: 1},
		OnStartup:        app.startup,
		OnDomReady:       app.domReady,
		Bind: []interface{}{
			app,
		},
	})
	if err != nil {
		println("Error:", err.Error())
	}
}
