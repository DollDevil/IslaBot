# IslaBot

A modular Discord bot for Isla's server with leveling, events, gambling, and more.

## Project Structure

```
IslaBot/
├── core/                   # Core bot files
│   ├── main.py            # Entry point - wires all modules together
│   ├── config.py          # Configuration constants
│   ├── data.py            # Data management (XP, coins, cooldowns)
│   └── utils.py           # Utility functions
├── systems/                # Feature systems
│   ├── xp.py              # XP system
│   ├── events.py          # Event system
│   ├── leaderboards.py    # Leaderboard helpers
│   ├── gambling.py        # Gambling system
│   ├── tasks.py           # Scheduled tasks
│   └── handlers.py        # Event handlers
├── commands/               # Command modules
│   ├── __init__.py
│   ├── user_commands.py    # User-facing commands
│   └── admin_commands.py   # Admin commands
├── scripts/                # Deployment scripts
│   ├── deploy.ps1
│   ├── quick-deploy.ps1
│   └── git-push.ps1
├── docs/                   # Documentation
├── data/                   # Data files
│   └── xp.json            # User XP data
└── assets/                 # Media files
    └── IslaVoiceChat.mp3
```

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create `secret.env` with your Discord token:
   ```
   DISCORD_TOKEN=your_token_here
   ```

3. Run the bot:
   ```bash
   python core/main.py
   ```

## Features

- **XP System**: Level up by sending messages and participating in voice chat
- **Events**: Participate in obedience events for bonus rewards
- **Gambling**: Play slots, dice, and other games
- **Leaderboards**: View rankings for levels, coins, and activity
- **Daily Rewards**: Claim daily coins with weekend bonuses

## Module Overview

- **config.py**: All configuration constants (channels, roles, XP thresholds, etc.)
- **data.py**: Data loading/saving and user statistics
- **xp.py**: XP calculation, multipliers, and level-up logic
- **events.py**: Obedience event system with phases and rewards
- **gambling.py**: All gambling games and mechanics
- **leaderboards.py**: Leaderboard embeds and pagination
- **tasks.py**: Scheduled tasks (VC XP, auto-save, event scheduling, daily checks)
- **handlers.py**: Discord event handlers (messages, reactions, voice, etc.)
- **commands/**: All slash commands organized by user/admin

