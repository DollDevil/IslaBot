# Check Deployment Status Script
# Helps diagnose why Wispbyte isn't deploying

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Deployment Status Check" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check 1: Git status
Write-Host "[1] Checking Git status..." -ForegroundColor Yellow
$gitStatus = git status --porcelain
if ([string]::IsNullOrWhiteSpace($gitStatus)) {
    Write-Host "   OK: No uncommitted changes" -ForegroundColor Green
} else {
    Write-Host "   WARNING: You have uncommitted changes:" -ForegroundColor Yellow
    git status --short
}

# Check 2: Recent commits
Write-Host ""
Write-Host "[2] Recent commits (last 5):" -ForegroundColor Yellow
git log --oneline -5
Write-Host ""

# Check 3: Remote repository
Write-Host "[3] Remote repository:" -ForegroundColor Yellow
$remote = git remote get-url origin
Write-Host "   $remote" -ForegroundColor Cyan

# Check 4: Current branch
Write-Host ""
Write-Host "[4] Current branch:" -ForegroundColor Yellow
$branch = git branch --show-current
Write-Host "   $branch" -ForegroundColor Cyan

# Check 5: Last push
Write-Host ""
Write-Host "[5] Checking if branch is up to date..." -ForegroundColor Yellow
git fetch origin --quiet
$localCommit = git rev-parse HEAD
$remoteCommit = git rev-parse origin/$branch 2>$null

if ($LASTEXITCODE -eq 0) {
    if ($localCommit -eq $remoteCommit) {
        Write-Host "   OK: Local and remote are in sync" -ForegroundColor Green
    } else {
        Write-Host "   WARNING: Local and remote are different" -ForegroundColor Yellow
        Write-Host "   You may need to push: git push origin $branch" -ForegroundColor Gray
    }
} else {
    Write-Host "   ERROR: Could not check remote status" -ForegroundColor Red
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Next Steps:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Check Wispbyte dashboard:" -ForegroundColor Yellow
Write-Host "   - Is GitHub integration connected?" -ForegroundColor Gray
Write-Host "   - Is branch set to: $branch" -ForegroundColor Gray
Write-Host "   - Is auto-deploy enabled?" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Check Wispbyte deployment logs:" -ForegroundColor Yellow
Write-Host "   - Look for recent deployment attempts" -ForegroundColor Gray
Write-Host "   - Check for error messages" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Try manual deployment in Wispbyte:" -ForegroundColor Yellow
Write-Host "   - Look for 'Deploy' or 'Redeploy' button" -ForegroundColor Gray
Write-Host ""
Write-Host "4. If nothing works, check:" -ForegroundColor Yellow
Write-Host "   - docs/WISPBYTE_TROUBLESHOOTING.md" -ForegroundColor Gray
Write-Host ""

