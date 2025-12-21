# Wispbyte Deployment Guide

Complete guide for deploying IslaBot to Wispbyte hosting.

## Quick Setup

### Method 1: Manual Upload (Recommended - Most Reliable)

1. **Create deployment package:**
   ```powershell
   .\deploy.ps1
   ```

2. **Upload to Wispbyte:**
   - Open Wispbyte File Manager
   - Upload `deploy.zip`
   - Extract it
   - Delete zip file

3. **Configure Wispbyte:**
   - Git repo address: Leave EMPTY
   - Git branch: Leave EMPTY
   - Auto update: OFF
   - App py file: `core/main.py`
   - Requirements file: `requirements.txt`

4. **Start bot** - Dependencies install automatically

### Method 2: GitHub Integration

1. **In Wispbyte Server Configuration:**
   - Git repo: `https://github.com/DollDevil/IslaBot.git`
   - Branch: `main`
   - Auto update: ON
   - App py file: `core/main.py`
   - Requirements file: `requirements.txt`

2. **If you get "already a git repository" error:**
   - Delete `.git` folder in File Manager (enable "Show hidden files")
   - Or delete all files and let it clone fresh

## Startup Command

Your startup command should be (Wispbyte usually sets this automatically):

```
if [[ -d .git ]] && [[ "1" == "1" ]]; then git pull; fi; 
if [[ -f /home/container/${REQUIREMENTS_FILE} ]]; then pip install -U --prefix .local -r ${REQUIREMENTS_FILE}; fi; 
/usr/local/bin/python /home/container/core/main.py
```

**Don't change this** - it's correct for Wispbyte.

## Updating Your Bot

### If Using Manual Upload:

1. Make code changes locally
2. Run: `.\quick-deploy.ps1 "Your changes"` (pushes to GitHub)
3. Run: `.\deploy.ps1` (creates deploy.zip)
4. Upload new `deploy.zip` to Wispbyte
5. Extract (overwrites files)
6. Restart bot in Wispbyte

### If Using GitHub Integration:

1. Make code changes locally
2. Run: `.\quick-deploy.ps1 "Your changes"`
3. Restart bot in Wispbyte (auto-update pulls code on startup)

## Important Notes

- **`data/xp.json`** is NOT uploaded (protected by `.gitignore`)
- **`secret.env`** is NOT uploaded (protected by `.gitignore`)
- Your bot data on Wispbyte is safe and won't be overwritten

## Troubleshooting

### "Already a git repository" error:
- Delete `.git` folder in File Manager (show hidden files)
- Or use manual upload method instead

### Changes not appearing:
- Restart bot after deployment
- Bot needs restart to load new code

### Console commands don't work:
- Use File Manager instead
- Or use manual upload method

## Environment Variables

Set these in Wispbyte (not in code):
- `DISCORD_TOKEN` - Your bot token
- `COMMAND_PREFIX` - (Optional) Command prefix

