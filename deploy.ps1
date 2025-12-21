# PowerShell deployment script for Wispbyte
# Creates a deployment package excluding unnecessary files

Write-Host "Creating deployment package..." -ForegroundColor Green

# Files to include
$filesToInclude = @(
    "*.py",
    "commands",
    "requirements.txt",
    "README.md",
    ".gitignore"
)

# Create temporary directory
$tempDir = "deploy_temp"
if (Test-Path $tempDir) {
    Remove-Item -Path $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

# Copy files
Write-Host "Copying files..." -ForegroundColor Yellow
foreach ($pattern in $filesToInclude) {
    if ($pattern -like "*.*") {
        # It's a file pattern
        Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination $tempDir -Force
        }
    } else {
        # It's a directory
        if (Test-Path $pattern) {
            Copy-Item -Path $pattern -Destination $tempDir -Recurse -Force
        }
    }
}

# Create data directory structure (empty, xp.json will be on server)
New-Item -ItemType Directory -Path "$tempDir\data" -Force | Out-Null
New-Item -ItemType Directory -Path "$tempDir\assets" -Force | Out-Null

# Create deployment zip
$zipFile = "deploy.zip"
if (Test-Path $zipFile) {
    Remove-Item -Path $zipFile -Force
}

Write-Host "Creating zip archive..." -ForegroundColor Yellow
Compress-Archive -Path "$tempDir\*" -DestinationPath $zipFile -Force

# Cleanup
Remove-Item -Path $tempDir -Recurse -Force

Write-Host "`nDeployment package created: $zipFile" -ForegroundColor Green
Write-Host "Upload this file to Wispbyte and extract it in your bot's directory." -ForegroundColor Cyan
Write-Host "`nDon't forget to:" -ForegroundColor Yellow
Write-Host "  1. Configure secret.env on Wispbyte with DISCORD_TOKEN" -ForegroundColor Yellow
Write-Host "  2. Run: pip install -r requirements.txt" -ForegroundColor Yellow
Write-Host "  3. Restart the bot" -ForegroundColor Yellow
