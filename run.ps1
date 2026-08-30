$ErrorActionPreference = "Stop"
$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ToolDir ".venv\Scripts\pythonw.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "먼저 setup.ps1을 실행하세요."
}

Start-Process -FilePath $VenvPython -ArgumentList (Join-Path $ToolDir "app.py") -WorkingDirectory $ToolDir

