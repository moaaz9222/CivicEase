# CivicEase AI — Quick Start (Windows PowerShell)
# Run this script once after cloning the repo.
# Usage: .\setup.ps1

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CivicEase AI - Setup Script (Windows)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Python
Write-Host "[1/5] Checking Python version..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python is not installed. Download it from https://python.org" -ForegroundColor Red
    exit 1
}
Write-Host "      Found: $pythonVersion" -ForegroundColor Green

# Step 2: Create virtual environment
Write-Host "[2/5] Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path "venv") {
    Write-Host "      venv/ already exists, skipping." -ForegroundColor Gray
} else {
    python -m venv venv
    Write-Host "      venv/ created." -ForegroundColor Green
}

# Step 3: Activate and install dependencies
Write-Host "[3/5] Installing dependencies..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"
pip install -r requirements.txt --quiet
Write-Host "      Dependencies installed." -ForegroundColor Green

# Step 4: Set up .env
Write-Host "[4/5] Setting up environment file..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "      .env already exists, skipping." -ForegroundColor Gray
} else {
    Copy-Item ".env.example" ".env"
    Write-Host "      .env created from template." -ForegroundColor Green
    Write-Host ""
    Write-Host "  ACTION REQUIRED: Open .env and set your GROQ_API_KEY" -ForegroundColor Magenta
    Write-Host "  Get a free key at: https://console.groq.com" -ForegroundColor Magenta
    Write-Host ""
}

# Step 5: Build vector database
Write-Host "[5/5] Building RAG vector database..." -ForegroundColor Yellow
python core/rag_engine.py
Write-Host "      Vector database built at chroma_db/" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "  To start the app:" -ForegroundColor White
Write-Host "    .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "    python app.py" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Then open: http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
