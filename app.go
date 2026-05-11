package main

import (
	"context"
	"os"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

type App struct {
	ctx         context.Context
	initialFile string
}

func NewApp(initialFile string) *App {
	return &App{initialFile: initialFile}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
}

func (a *App) domReady(ctx context.Context) {
	if a.initialFile != "" {
		runtime.EventsEmit(ctx, "load-file", a.initialFile)
	}
}

func (a *App) OpenFileDialog() string {
	path, err := runtime.OpenFileDialog(a.ctx, runtime.OpenDialogOptions{
		Title: "Выберите XSD файл",
		Filters: []runtime.FileFilter{
			{DisplayName: "XSD Files (*.xsd)", Pattern: "*.xsd"},
		},
	})
	if err != nil || path == "" {
		return ""
	}
	return path
}

func (a *App) LoadXSD(path string) LoadResult {
	if _, err := os.Stat(path); err != nil {
		return LoadResult{Error: "Файл не найден: " + path}
	}
	return parseXSD(path)
}
