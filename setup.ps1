$ErrorActionPreference = "Stop"
$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ToolDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $PythonLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($PythonLauncher) {
        & $PythonLauncher.Source -3.11 -m venv (Join-Path $ToolDir ".venv")
    }
    else {
        $PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
        if (-not $PythonCommand) {
            throw "Python 3.11을 찾지 못했습니다. https://www.python.org/downloads/ 에서 설치하세요."
        }
        & $PythonCommand.Source -m venv (Join-Path $ToolDir ".venv")
    }
}

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r (Join-Path $ToolDir "requirements.txt")
Write-Host "설치 완료. run.ps1 또는 build.ps1을 실행하세요."
