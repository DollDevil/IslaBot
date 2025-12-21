# Automated Git Push Script
# This script automates the git workflow: add, commit, and push

param(
    [Parameter(Mandatory=$false)]
    [string]$Message = "Update code"
)

Write-Host "`n=== Automated Git Push ===" -ForegroundColor Cyan
Write-Host ""

# Check if we're in a git repository
if (-not (Test-Path ".git")) {
    Write-Host "Error: Not a git repository!" -ForegroundColor Red
    exit 1
}

# Check for changes
Write-Host "Checking for changes..." -ForegroundColor Yellow
$status = git status --porcelain

if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "No changes to commit." -ForegroundColor Yellow
    Write-Host "Do you want to push anyway? (y/n): " -NoNewline -ForegroundColor Yellow
    $response = Read-Host
    if ($response -ne "y" -and $response -ne "Y") {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "Found changes:" -ForegroundColor Green
    git status --short
    
    Write-Host "`nStaging all changes..." -ForegroundColor Yellow
    git add .
    
    Write-Host "Committing changes..." -ForegroundColor Yellow
    git commit -m $Message
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Commit failed!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✓ Committed: $Message" -ForegroundColor Green
}

# Push to GitHub
Write-Host "`nPushing to GitHub..." -ForegroundColor Yellow
git push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✓ Successfully pushed to GitHub!" -ForegroundColor Green
    Write-Host "Wispbyte should automatically deploy your changes." -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "`n✗ Push failed. Check the error above." -ForegroundColor Red
    exit 1
}

