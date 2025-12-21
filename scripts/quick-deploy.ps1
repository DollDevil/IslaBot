# Quick Deploy Script - One command to deploy everything
# Usage: .\quick-deploy.ps1 "Your commit message"

param(
    [Parameter(Mandatory=$false)]
    [string]$Message = "Auto-deploy: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
)

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Quick Deploy to Wispbyte" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check git status
Write-Host "[1/3] Checking Git status..." -ForegroundColor Yellow
$changes = git status --porcelain

if ([string]::IsNullOrWhiteSpace($changes)) {
    Write-Host "   No changes detected." -ForegroundColor Gray
    Write-Host "   Do you want to push anyway? (y/n): " -NoNewline -ForegroundColor Yellow
    $response = Read-Host
    if ($response -ne "y" -and $response -ne "Y") {
        Write-Host ""
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "   Changes found!" -ForegroundColor Green
    
    # Step 2: Add and commit
    Write-Host "[2/3] Staging and committing..." -ForegroundColor Yellow
    git add .
    git commit -m $Message
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   Commit failed!" -ForegroundColor Red
        exit 1
    }
    Write-Host "   Committed: $Message" -ForegroundColor Green
}

# Step 3: Push to GitHub
Write-Host "[3/3] Pushing to GitHub..." -ForegroundColor Yellow
git push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "   Pushed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "   Deployment Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Wispbyte should automatically deploy your changes." -ForegroundColor Cyan
    Write-Host "Check your Wispbyte dashboard for deployment status." -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "   Push failed!" -ForegroundColor Red
    Write-Host "   Check the error message above." -ForegroundColor Yellow
    exit 1
}
