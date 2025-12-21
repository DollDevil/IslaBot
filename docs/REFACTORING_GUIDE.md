# Code Refactoring Guide

This document explains the new modular structure for IslaBot.

## New Structure

```
IslaBot/
├── main.py              # Bot entry point and initialization
├── config.py            # All configuration constants
├── data.py              # Data management (XP, coins, user stats)
├── utils.py             # Utility functions
├── events.py             # Event system (obedience events)
├── gambling.py          # Gambling system (gamble, dice, slots, etc.)
├── leaderboards.py      # Leaderboard system
├── tasks.py              # Scheduled tasks (auto-save, daily checks, etc.)
├── handlers.py           # Event handlers (on_message, on_ready, etc.)
└── commands/
    ├── __init__.py
    ├── user_commands.py  # User-facing slash commands
    └── admin_commands.py # Admin-only slash commands
```

## Module Responsibilities

### config.py
- All configuration constants (channel IDs, role IDs, XP thresholds, etc.)
- Event configuration
- Command permissions
- No functions, just constants

### data.py
- `xp_data` global variable
- `load_xp_data()` - Load from xp.json
- `save_xp_data()` - Save to xp.json
- User data getters: `get_xp()`, `get_level()`, `get_coins()`
- User data modifiers: `add_coins()`, `increment_event_participation()`, etc.
- `get_activity_quote()` - Activity-based quotes

### utils.py
- Helper functions: `next_level_requirement()`, `resolve_channel_id()`, etc.
- `get_reply_quote()` - Reply quote selection
- `update_roles_on_level()` - Role management

### events.py
- Event system functions
- `start_obedience_event()`, `end_obedience_event()`
- `handle_event_message()`, `handle_event_reaction()`
- Event prompts and embeds

### gambling.py
- All gambling commands and logic
- Cooldown management
- Streak tracking

### leaderboards.py
- Leaderboard building functions
- `LeaderboardView` class
- Leaderboard commands

### tasks.py
- Scheduled background tasks
- Auto-save
- Daily checks
- Event scheduler

### handlers.py
- Discord event handlers
- `on_message()`, `on_ready()`, `on_voice_state_update()`, etc.

### commands/user_commands.py
- User-facing slash commands:
  - `/level`, `/info`, `/balance`, `/daily`, `/give`
  - `/leaderboard`, `/leaderboards`
  - `/gamble`, `/dice`, `/slots`, `/coinflip`, `/store`

### commands/admin_commands.py
- Admin-only slash commands:
  - `/obedience`, `/config`, `/throne`, `/killevent`
  - `/sync`, `/stopevents`, `/levelrolecheck`, `/levelupdates`
  - `/setxp`, `/setlevel`, `/schedule`, `/testembeds`

## Migration Steps

1. ✅ Created `config.py` with all constants
2. ✅ Created `data.py` with data management
3. ✅ Created `utils.py` with utility functions
4. ⏳ Extract events to `events.py`
5. ⏳ Extract gambling to `gambling.py`
6. ⏳ Extract leaderboards to `leaderboards.py`
7. ⏳ Extract tasks to `tasks.py`
8. ⏳ Extract handlers to `handlers.py`
9. ⏳ Extract commands to `commands/` folder
10. ⏳ Update `main.py` to import and wire everything

## Import Pattern

Each module should import what it needs:
```python
# Example: events.py
import discord
from config import EVENT_REWARDS, EVENT_CHANNEL_ID, ...
from data import xp_data, increment_event_participation, add_xp, ...
from utils import resolve_channel_id, ...
```

## Global State

Some global state needs to be shared:
- `xp_data` - in `data.py`
- `active_event`, `events_enabled` - in `events.py` or `config.py`
- `gambling_cooldowns`, `daily_cooldowns` - in respective modules

## Next Steps

Continue extracting code from `main.py` into the appropriate modules following the structure above.

