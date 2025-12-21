# Setting Up Environment Variables in Wispbyte

There are two ways to provide environment variables (like `DISCORD_TOKEN`) to your bot on Wispbyte:

## Method 1: Upload `secret.env` File (Recommended for Multiple Variables)

### Steps:
1. **Create your `secret.env` file locally** with your variables:
   ```
   DISCORD_TOKEN=your_bot_token_here
   COMMAND_PREFIX=!
   EVENT_2_AUDIO=https://your-audio-url.com
   ```

2. **Upload to Wispbyte via File Manager:**
   - Go to your Wispbyte server dashboard
   - Click on **"File Manager"** or **"Files"**
   - Navigate to the root directory (where `core/main.py` is located)
   - Click **"Upload"** or **"Upload File"**
   - Select your `secret.env` file
   - Wait for upload to complete

3. **Verify the file exists:**
   - In File Manager, you should see `secret.env` in the root directory
   - The file should NOT be deleted when GitHub updates run (since it's gitignored)

### ⚠️ Important Notes:
- **`secret.env` is in `.gitignore`**, so it won't be pushed to GitHub
- **GitHub updates won't overwrite it** (since it's not in the repo)
- However, if Wispbyte does a **full clean clone**, the file might be deleted
- If the file disappears after updates, use Method 2 instead

---

## Method 2: Wispbyte Environment Variables (More Reliable)

This is the **most reliable method** and won't be affected by Git operations.

### Steps:
1. **Go to your Wispbyte server dashboard**
2. **Navigate to Settings/Configuration**
3. **Find "Environment Variables" section** (may be under Startup, Advanced, or Server Config)
4. **Add each variable:**
   - Click **"Add Variable"** or **"New Environment Variable"**
   - **Name:** `DISCORD_TOKEN`
   - **Value:** `your_actual_bot_token_here`
   - Click **Save** or **Add**
5. **Repeat for other variables** (COMMAND_PREFIX, EVENT_2_AUDIO, etc.)
6. **Restart your bot**

### Example Variables to Add:
```
DISCORD_TOKEN=your_bot_token_here
COMMAND_PREFIX=!
EVENT_2_AUDIO=https://drive.google.com/uc?export=download&id=...
```

---

## Which Method Should You Use?

### Use Method 1 (`secret.env` file) if:
- ✅ You have many environment variables
- ✅ You want to manage them in one file
- ✅ You're comfortable with file uploads

### Use Method 2 (Wispbyte Environment Variables) if:
- ✅ You want the most reliable setup
- ✅ You only have a few variables
- ✅ You want to avoid file management issues
- ✅ Wispbyte's file manager is unreliable

---

## Troubleshooting

### File disappears after GitHub update:
- **Solution:** Use Method 2 (Environment Variables) instead
- Or re-upload the file after each update

### Bot still can't find DISCORD_TOKEN:
1. Check that the variable name is exactly `DISCORD_TOKEN` (case-sensitive)
2. Verify there are no extra spaces: `DISCORD_TOKEN=token` (not `DISCORD_TOKEN = token`)
3. Restart the bot after adding variables
4. Check the console logs for error messages

### How to verify it's working:
- After setting up, restart your bot
- Check the console output - you should see:
  - `✓ Loaded environment variables from secret.env` (if using Method 1)
  - Or no error about missing DISCORD_TOKEN (if using Method 2)

---

## Security Notes

⚠️ **Never commit `secret.env` to GitHub!**
- It's already in `.gitignore`, so it won't be pushed
- Double-check that your token isn't in any committed files
- If you accidentally commit it, regenerate your Discord bot token immediately

