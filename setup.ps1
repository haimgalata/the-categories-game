$ErrorActionPreference = "Stop"

python -m venv venv

if (Test-Path ".\venv\Scripts\Activate.ps1") {
    . .\venv\Scripts\Activate.ps1
}

python -m pip install --upgrade pip
pip install -r requirements.txt

if ((-not (Test-Path ".env")) -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Fill in real secrets before running."
}

Write-Host "Setup complete."
