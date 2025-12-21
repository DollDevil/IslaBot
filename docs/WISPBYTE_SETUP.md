# Wispbyte Auto-Deployment Setup

## ✅ Current Status
- GitHub repository connected: `DollDevil/IslaBot`
- Branch: `main`
- Auto-deploy: Enabled (when configured)

## How Auto-Deployment Works

### Workflow:
1. **Make changes locally** in your code
2. **Commit changes**:
   ```powershell
   git add .
   git commit -m "Description of your changes"
   ```
3. **Push to GitHub**:
   ```powershell
   git push origin main
   ```
4. **Wispbyte automatically**:
   - Detects the push
   - Pulls the latest code
   - Installs dependencies (`pip install -r requirements.txt`)
   - Restarts your bot

## Testing Auto-Deployment

### Test 1: Make a small change
1. Edit any file (e.g., add a comment to `main.py`)
2. Commit and push:
   ```powershell
   git add .
   git commit -m "Test auto-deployment"
   git push origin main
   ```
3. Check Wispbyte dashboard/logs to see if it deployed

### Test 2: Check deployment logs
- In Wispbyte dashboard, look for:
  - "Deployment" or "Build Logs"
  - "Activity" or "Recent Deployments"
  - Check if it shows the latest commit

## Important Notes

### Environment Variables
Make sure these are set in Wispbyte:
- `DISCORD_TOKEN` - Your bot token
- `COMMAND_PREFIX` - (Optional) Command prefix

**Note**: `secret.env` is NOT uploaded to GitHub (it's in `.gitignore`), so you must configure these in Wispbyte's environment variables section.

### Data Files
- `data/xp.json` is also in `.gitignore` (not uploaded)
- Your bot will create a new `data/xp.json` on Wispbyte when it runs
- If you need to migrate existing data, upload it manually via Wispbyte file manager

### Dependencies
Wispbyte should automatically run `pip install -r requirements.txt` on each deployment. Verify this in the deployment logs.

## Troubleshooting

### Bot doesn't restart after push:
- Check Wispbyte deployment logs
- Verify `DISCORD_TOKEN` is set
- Check if there are any errors in the build process

### Changes not appearing:
- Check deployment status in Wispbyte
- Verify the push was successful: `git log --oneline -5`
- Check Wispbyte logs for errors
- Manually restart the bot if needed

### Deployment fails:
- Check `requirements.txt` is up to date
- Verify Python version compatibility
- Check Wispbyte logs for specific error messages

## Manual Deployment (If Auto-Deploy Fails)

If auto-deployment isn't working, you can use the manual script:

```powershell
.\deploy.ps1
```

Then upload `deploy.zip` via Wispbyte file manager.

## Current Configuration

- **Repository**: https://github.com/DollDevil/IslaBot
- **Branch**: `main`
- **Auto-Deploy**: Enabled (verify in Wispbyte dashboard)

