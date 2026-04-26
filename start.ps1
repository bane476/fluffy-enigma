$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$engineDir = Join-Path $projectRoot "backend\engine"
$engineBuildDir = Join-Path $engineDir "build"
$apiDir = Join-Path $projectRoot "backend\api"
$frontendDir = Join-Path $projectRoot "frontend"

# 1. Build C++ Engine
Write-Host "Building C++ Engine..." -ForegroundColor Cyan
Push-Location $engineDir
if (-not (Test-Path $engineBuildDir)) {
    New-Item -ItemType Directory -Path $engineBuildDir | Out-Null
}
Push-Location $engineBuildDir
cmake .. -G "MinGW Makefiles"
cmake --build .
Pop-Location
Pop-Location

# 2. Setup Python Environment
Write-Host "Setting up Python Environment..." -ForegroundColor Cyan

# Kill any existing process on port 8000
$portProcess = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($portProcess) {
    Write-Host "Cleaning up existing backend on port 8000..."
    Stop-Process -Id $portProcess.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Push-Location $apiDir
if (-not (Test-Path ".\venv")) {
    Write-Host "Creating Virtual Environment..."
    python -m venv venv
}
Write-Host "Installing/Updating Python Dependencies..."
& .\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item ..\engine\build\logistics_engine.*.pyd . -ErrorAction SilentlyContinue

Write-Host "Starting FastAPI Backend in a new window..." -ForegroundColor Green
Start-Process powershell `
    -WorkingDirectory $apiDir `
    -ArgumentList "-NoExit", "-Command", ".\venv\Scripts\python.exe -m uvicorn main:app --port 8000"
Pop-Location

# 3. Setup Frontend
Write-Host "Setting up Frontend..." -ForegroundColor Cyan
Push-Location $frontendDir
Write-Host "Installing Frontend Dependencies..."
npm install
Write-Host "Starting React Frontend... Check your browser at http://localhost:5173" -ForegroundColor Green
npm run dev
