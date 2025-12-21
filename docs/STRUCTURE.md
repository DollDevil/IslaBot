# IslaBot Modular Structure

## Current Status

✅ **Completed:**
- `config.py` - All configuration constants
- `data.py` - Data management (XP data, user stats)
- `utils.py` - Utility functions
- `xp.py` - XP system (add_xp, level-up messages)
- `commands/` folder created

⏳ **In Progress:**
- `events.py` - Event system (needs extraction from main.py)
- `gambling.py` - Gambling commands
- `leaderboards.py` - Leaderboard system
- `tasks.py` - Scheduled tasks
- `handlers.py` - Event handlers
- `commands/user_commands.py` - User commands
- `commands/admin_commands.py` - Admin commands

## File Structure

```
IslaBot/
├── main.py                 # Entry point - bot initialization
├── config.py               # Configuration constants
├── data.py                 # Data management
├── utils.py                # Utility functions
├── xp.py                   # XP system
├── events.py               # Event system (to be created)
├── gambling.py             # Gambling system (to be created)
├── leaderboards.py         # Leaderboard system (to be created)
├── tasks.py                # Scheduled tasks (to be created)
├── handlers.py             # Event handlers (to be created)
└── commands/
    ├── __init__.py
    ├── user_commands.py     # User-facing commands (to be created)
    └── admin_commands.py   # Admin commands (to be created)
```

## Import Dependencies

```
main.py
  ├── config.py
  ├── data.py
  ├── utils.py
  ├── xp.py
  ├── events.py
  ├── gambling.py
  ├── leaderboards.py
  ├── tasks.py
  ├── handlers.py
  └── commands/
      ├── user_commands.py
      └── admin_commands.py

events.py
  ├── config.py
  ├── data.py
  ├── xp.py
  └── utils.py

gambling.py
  ├── config.py
  ├── data.py
  └── xp.py

leaderboards.py
  ├── config.py
  └── data.py

tasks.py
  ├── config.py
  ├── data.py
  └── events.py

handlers.py
  ├── config.py
  ├── data.py
  ├── xp.py
  └── events.py

commands/user_commands.py
  ├── config.py
  ├── data.py
  ├── xp.py
  └── utils.py

commands/admin_commands.py
  ├── config.py
  ├── data.py
  ├── events.py
  └── utils.py
```

## Global State Management

Some modules need to share global state:

- **data.py**: `xp_data` (global dict)
- **events.py**: `active_event`, `event_cooldown_until`, `events_enabled`, `last_event_times_today`, `event_scheduler_task`
- **gambling.py**: `gambling_cooldowns`, `gambling_streaks`, `slots_free_spins`
- **tasks.py**: `daily_cooldowns`, `give_cooldowns`

## Bot Instance

The bot instance needs to be accessible in:
- `xp.py` (for send_level_up_message)
- `events.py` (for event handling)
- `handlers.py` (for event handlers)
- `tasks.py` (for scheduled tasks)

Solution: Use a `set_bot()` function in each module that needs it, called from `main.py`.

## Next Steps

1. Extract events.py from main.py (lines ~658-1962)
2. Extract gambling.py (gambling commands)
3. Extract leaderboards.py (leaderboard system)
4. Extract tasks.py (scheduled tasks)
5. Extract handlers.py (on_message, on_ready, etc.)
6. Extract commands to commands/ folder
7. Update main.py to import and wire everything

