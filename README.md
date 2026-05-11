# XSD Viewer Pro

Просмотрщик структуры XSD файлов Минстроя. Показывает дерево элементов с цветовой кодировкой по файлам-источникам.

## Скачать

[Releases](https://github.com/Varmelot/XsdViewerGo/releases) — бинарники для Linux, macOS, Windows.

## Запуск

```bash
# Открыть файл через диалог
./XsdViewerGo

# Открыть файл сразу
./XsdViewerGo path/to/schema.xsd
```

## Установка по платформам

### Linux (Ubuntu 24.04)
```bash
sudo apt install libwebkit2gtk-4.0-0
chmod +x XsdViewerGo
./XsdViewerGo
```

### Linux (Ubuntu 22.04)
Зависимости уже установлены, запускать напрямую.

### macOS
Приложение не подписано — при первом запуске Gatekeeper покажет предупреждение.  
Решение: **правой кнопкой на XsdViewerGo.app → Открыть → Открыть**.  
После этого приложение запускается как обычно.

### Windows
Запустить `XsdViewerGo.exe`. При первом запуске SmartScreen может показать предупреждение — нажать **Подробнее → Выполнить в любом случае**.

## Сборка из исходников

Требования: Go 1.23+, Node.js 20+, [Wails v2](https://wails.io)

```bash
# Linux
wails build -tags webkit2_41

# macOS / Windows
wails build
```
