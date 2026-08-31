@echo off
setlocal
set "APP_DIR=%~dp0dist"
set "APP_EXE=%APP_DIR%\FaceGridStamper.exe"
set "DOWNLOAD_URL=https://github.com/nicekriss/FaceGridStamper/releases/latest/download/FaceGridStamper-windows-x64.exe"

if exist "%APP_EXE%" goto run

echo Face Grid Stamper latest release is being downloaded...
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; New-Item -ItemType Directory -Force -Path '%APP_DIR%' | Out-Null; $tempFile='%APP_EXE%.download'; Invoke-WebRequest -UseBasicParsing -Uri '%DOWNLOAD_URL%' -OutFile $tempFile; Move-Item -LiteralPath $tempFile -Destination '%APP_EXE%' -Force"

if errorlevel 1 (
  echo.
  echo Download failed. Open the Releases page and download FaceGridStamper-windows-x64.exe.
  echo https://github.com/nicekriss/FaceGridStamper/releases/latest
  pause
  exit /b 1
)

:run
start "" "%APP_EXE%"
endlocal
