$ErrorActionPreference = "Stop"
$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ToolDir ".venv\Scripts\pythonw.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "개발 환경이 없어 최초 설정을 진행합니다."
    & (Join-Path $ToolDir "setup.ps1")
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        throw "개발 환경 설정에 실패했습니다."
    }
}

Start-Process -FilePath $VenvPython -ArgumentList (Join-Path $ToolDir "app.py") -WorkingDirectory $ToolDir
