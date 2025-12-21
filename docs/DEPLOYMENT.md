# Deployment Guide for Wispbyte

This guide covers automated deployment options for IslaBot to Wispbyte hosting.

## Option 1: Git-Based Deployment (Recommended)

Most modern hosting platforms (including Wispbyte) support automatic deployment from Git repositories.

### Setup Steps:

1. **Initialize Git Repository** (if not already done):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   ```

2. **Create GitHub/GitLab Repository**:
   - Create a new repository on GitHub or GitLab
   - Push your code:
     ```bash
     git remote add origin https://github.com/yourusername/IslaBot.git
     git branch -M main
     git push -u origin main
     ```

3. **Configure Wispbyte**:
   - Log into your Wispbyte dashboard
   - Navigate to your bot's application settings
   - Look for "Deployment" or "Git" settings
   - Connect your GitHub/GitLab repository
   - Enable "Auto Deploy" on push to main branch
   - Set the branch to deploy (usually `main` or `master`)

4. **Automatic Deployment**:
   - Every time you push to the main branch, Wispbyte will automatically:
     - Pull the latest code
     - Install dependencies (`pip install -r requirements.txt`)
     - Restart the bot

### Workflow:
```bash
# Make changes locally
# Commit changes
git add .
git commit -m "Description of changes"
git push origin main

# Wispbyte automatically deploys!
```

## Option 2: GitHub Actions (Advanced)

If Wispbyte supports SSH or API deployment, you can use GitHub Actions:

1. **Create `.github/workflows/deploy.yml`**:
   ```yaml
   name: Deploy to Wispbyte
   
   on:
     push:
       branches: [ main ]
   
   jobs:
     deploy:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v2
         
         - name: Deploy to Wispbyte
           uses: appleboy/ssh-action@master
           with:
             host: ${{ secrets.WISPBYTE_HOST }}
             username: ${{ secrets.WISPBYTE_USER }}
             key: ${{ secrets.WISPBYTE_SSH_KEY }}
             script: |
               cd /path/to/bot
               git pull origin main
               pip install -r requirements.txt
               # Restart bot command (depends on Wispbyte setup)
   ```

2. **Add Secrets to GitHub**:
   - Go to repository Settings → Secrets
   - Add: `WISPBYTE_HOST`, `WISPBYTE_USER`, `WISPBYTE_SSH_KEY`

## Option 3: Manual Deployment (Current Method)

If automated deployment isn't available:

1. **Create deployment script** (`deploy.sh` or `deploy.ps1`):
   ```powershell
   # deploy.ps1 for Windows
   # Compress files for upload
   Compress-Archive -Path *.py,commands,data,assets -DestinationPath deploy.zip -Force
   Write-Host "Created deploy.zip - Upload this to Wispbyte"
   ```

2. **Upload via Wispbyte Dashboard**:
   - Compress your files
   - Upload via Wispbyte file manager
   - Run `pip install -r requirements.txt` in terminal
   - Restart the bot

## Environment Variables

**Important**: Make sure `secret.env` is configured on Wispbyte:
- `DISCORD_TOKEN` - Your bot token
- `COMMAND_PREFIX` - (Optional) Command prefix

**Note**: Never commit `secret.env` to Git! It's already in `.gitignore`.

## Pre-Deployment Checklist

- [ ] All code changes committed
- [ ] `requirements.txt` is up to date
- [ ] `secret.env` configured on Wispbyte
- [ ] Tested locally
- [ ] Data files (`data/xp.json`) backed up (if needed)

## Post-Deployment

1. Check bot logs on Wispbyte
2. Verify bot is online in Discord
3. Test a few commands
4. Monitor for any errors

## Troubleshooting

### Bot doesn't start after deployment:
- Check Wispbyte logs
- Verify `DISCORD_TOKEN` is set
- Ensure all dependencies are installed
- Check Python version compatibility

### Changes not appearing:
- Clear Wispbyte cache (if applicable)
- Restart the bot manually
- Check if auto-deploy is enabled
- Verify you pushed to the correct branch

## Wispbyte-Specific Notes

Check Wispbyte's documentation for:
- Supported Git providers (GitHub, GitLab, Bitbucket)
- Auto-deploy configuration
- SSH access (for GitHub Actions)
- File upload limits
- Python version requirements

