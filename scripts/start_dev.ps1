# Start development servers
# Backend (Python FastAPI)
Write-Host "Starting API server on http://localhost:8765 ..." -ForegroundColor Green
$apiProcess = Start-Process -FilePath "python" -ArgumentList "-m uvicorn api.server:app --reload --host 0.0.0.0 --port 8765" -PassThru -WorkingDirectory $PSScriptRoot

# Frontend (Vite)
Write-Host "Starting frontend on http://localhost:5173 ..." -ForegroundColor Green
$frontendProcess = Start-Process -FilePath "pnpm" -ArgumentList "dev" -PassThru -WorkingDirectory "$PSScriptRoot\frontend"

Write-Host ""
Write-Host "Backend:  http://localhost:8765" -ForegroundColor Cyan
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers" -ForegroundColor Yellow

try {
    $apiProcess.WaitForExit()
} finally {
    $apiProcess.Kill()
    $frontendProcess.Kill()
}
