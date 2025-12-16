param(
  [int]$FrontendPort = 5500,
  [int]$BackendPort  = 8000
)

$ErrorActionPreference = "Stop"

# --- Config (repo-intern) ---
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvActivate = Join-Path $repo ".venv\Scripts\Activate.ps1"

# Keine manuellen $env:... nötig: Backend & Resizer laden .env automatisch (python-dotenv).

function Assert-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Command '$name' not found. Please install it / add to PATH."
  }
}

Assert-Command py
Assert-Command docker

# Helper: start a new PowerShell window running a command
function Start-Term($title, $workdir, $cmd) {
  $argList = @(
    "-NoExit",
    "-Command",
    "& { Set-Location -LiteralPath '$workdir'; if (Test-Path -LiteralPath '$venvActivate') { . '$venvActivate' }; $cmd }"
  )

  Start-Process powershell -ArgumentList $argList -WindowStyle Normal
}


Write-Host "Repo: $repo"
Write-Host "Using:"
Write-Host "  RabbitMQ: localhost:5672 (UI http://localhost:15672 guest/guest)"
Write-Host "  Backend : http://127.0.0.1:$BackendPort"
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort"
Write-Host ""

# --- 1) RabbitMQ (docker) ---
Start-Term "RabbitMQ" $repo "docker run --rm -it --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management"

# --- 2) Backend ---
# Passe den Start ggf. an: social-api ist dein entrypoint.
Start-Term "Backend" (Join-Path $repo "backend") "py -m uv run --active social-api"

# --- 3) Image-Resizer ---
Start-Term "Image-Resizer" $repo "social-resizer"

# --- 4) Frontend ---
Start-Term "Frontend" (Join-Path $repo "frontend") "py -m http.server $FrontendPort"

Write-Host "✅ Started all services in separate terminals."
