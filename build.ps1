$ErrorActionPreference = "Stop"
$ToolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ToolDir ".venv\Scripts\python.exe"
$ModelPath = Join-Path $ToolDir "models\face_detection_yunet_2023mar.onnx"
$BuildWorkPath = Join-Path $env:LOCALAPPDATA "Temp\FaceGridStamper-build"
$PackageDistPath = Join-Path $env:LOCALAPPDATA "Temp\FaceGridStamper-dist"
$FinalDistPath = Join-Path $ToolDir "dist\FaceGridStamper"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "먼저 setup.ps1을 실행하세요."
}
if (-not (Test-Path -LiteralPath $ModelPath)) {
    throw "YuNet 모델 파일이 없습니다: $ModelPath"
}

Push-Location $ToolDir
try {
    & $VenvPython -m PyInstaller --noconfirm --clean --windowed --name FaceGridStamper --workpath $BuildWorkPath --distpath $PackageDistPath --specpath $ToolDir --add-data "models\face_detection_yunet_2023mar.onnx;models" app.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller 빌드가 종료 코드 $LASTEXITCODE 로 실패했습니다."
    }

    $BuiltAppPath = Join-Path $PackageDistPath "FaceGridStamper"
    New-Item -ItemType Directory -Force -Path $FinalDistPath | Out-Null
    Copy-Item -Path (Join-Path $BuiltAppPath "*") -Destination $FinalDistPath -Recurse -Force
}
finally {
    Pop-Location
}
Write-Host "빌드 완료: $ToolDir\dist\FaceGridStamper\FaceGridStamper.exe"
