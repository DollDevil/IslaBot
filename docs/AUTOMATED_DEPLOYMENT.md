# Automated Git Deployment Guide

## Quick Start

Instead of typing multiple git commands, use these automated scripts:

### Option 1: Quick Deploy Script (Recommended)

**One command to deploy everything:**

```powershell
.\quick-deploy.ps1 "Your commit message here"
```

**Or without a message (uses timestamp):**
```powershell
.\quick-deploy.ps1
```

**What it does:**
1. Checks for changes
2. Stages all files (`git add .`)
3. Commits with your message (`git commit`)
4. Pushes to GitHub (`git push`)
5. Wispbyte automatically deploys!

### Option 2: Git Push Script

**More control over the process:**

```powershell
.\git-push.ps1 "Your commit message"
```

### Option 3: Manual (Original Method)

If you prefer manual control:

```powershell
git add .
git commit -m "Your message"
git push origin main
```

## Setting Up Aliases (Optional)

You can create shortcuts for even faster deployment:

### PowerShell Profile Alias

1. Open your PowerShell profile:
   ```powershell
   notepad $PROFILE
   ```

2. Add this line:
   ```powershell
   function Deploy { & "C:\Users\Yuu\Documents\IslaBot\quick-deploy.ps1" $args }
   ```

3. Save and reload:
   ```powershell
   . $PROFILE
   ```

4. Now you can just type:
   ```powershell
   Deploy "My changes"
   ```

## Workflow Examples

### Daily Development Workflow:

```powershell
# Make your code changes in VS Code/Cursor

# Then deploy with one command:
.\quick-deploy.ps1 "Added new feature X"

# Done! Wispbyte deploys automatically
```

### Quick Fix:

```powershell
.\quick-deploy.ps1 "Fixed bug in gambling system"
```

### Multiple Changes:

```powershell
.\quick-deploy.ps1 "Updated events, fixed leaderboards, added new command"
```

## What Gets Deployed

✅ **Included:**
- All `.py` files
- `commands/` folder
- `requirements.txt`
- `README.md`
- `.gitignore`
- `data/` folder structure (but NOT `xp.json`)

❌ **Excluded (Protected):**
- `data/xp.json` - Your user data (never overwritten)
- `secret.env` - Your bot token (never uploaded)
- `__pycache__/` - Python cache files
- `*.log` - Log files

## Troubleshooting

### Script won't run:
```powershell
# Allow script execution (one-time)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### "Not a git repository" error:
- Make sure you're in the `IslaBot` folder
- Run: `cd C:\Users\Yuu\Documents\IslaBot`

### Push fails:
- Check your GitHub token is still valid
- Clear credentials: See `docs/DEPLOYMENT.md`

## Tips

1. **Use descriptive commit messages:**
   ```powershell
   .\quick-deploy.ps1 "Fixed daily command cooldown bug"
   ```
   Not:
   ```powershell
   .\quick-deploy.ps1 "fix"
   ```

2. **Check Wispbyte after deploying:**
   - Look for deployment status
   - Check bot logs
   - Verify bot is online

3. **Test locally first:**
   - Make sure your code works before deploying
   - Test commands locally if possible

## Summary

**Before:** 3 commands to deploy
```powershell
git add .
git commit -m "message"
git push origin main
```

**Now:** 1 command to deploy
```powershell
.\quick-deploy.ps1 "message"
```

**Result:** Same outcome, much faster! 🚀

