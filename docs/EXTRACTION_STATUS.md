# Extraction Status

## ✅ Completed Modules

1. **config.py** - All configuration constants (263 lines)
2. **data.py** - Data management (210 lines)
3. **utils.py** - Utility functions
4. **xp.py** - XP system (add_xp, level-up messages)

## ⏳ Remaining Extraction

### events.py (Lines ~637-1962 in main.py)
**Functions to extract:**
- `clear_event_roles()`
- `build_event_embed()`
- `event_prompt()`
- `event_6_prompt()`
- `choose_collective_question()`
- `check_event7_phase1_threshold()`
- `end_event4_phase1()`
- `start_event4_phase2()`
- `end_event7_phase2()`
- `end_event7_phase3()`
- `start_obedience_event()` (very large, ~420 lines)
- `end_obedience_event()` (large)
- `handle_event7_phase3()`
- `send_event7_phase3_failed()`
- `send_event7_phase3_success()`
- `handle_event_message()` (large, ~230 lines)
- `handle_event_reaction()`
- `escalate_collective_event()`

**Global state:**
- `active_event = None`
- `event_cooldown_until = None`
- `events_enabled = True`
- `last_event_times_today = set()`
- `event_scheduler_task = None`

### gambling.py (Lines ~3636-4426 in main.py)
**Functions to extract:**
- `balance()` command
- `daily()` command
- `give()` command
- `gamble()` command
- `gambleinfo()` command
- `dice()` command
- `diceinfo()` command
- `spin_slots_reels()`
- `calculate_slots_payout()`
- `slots_bet()` command
- `slots_free()` command
- `slotspaytable()` command
- `slotsinfo()` command
- `casinoinfo()` command
- `coinflip()` command
- `coinflipinfo()` command
- `allin()` command
- `store()` command

**Global state:**
- `gambling_cooldowns = {}`
- `gambling_streaks = {}`
- `slots_free_spins = {}`

### leaderboards.py (Lines ~2896-3331 in main.py)
**Functions to extract:**
- `format_placement()`
- `build_levels_leaderboard_embed()`
- `build_coins_leaderboard_embed()`
- `build_activity_leaderboard_embed()`
- `LeaderboardView` class
- `leaderboards_menu()` command
- `leaderboard()` command

### tasks.py (Lines ~4841-4970 in main.py)
**Functions to extract:**
- `award_vc_xp()` task
- `auto_save()` task
- `send_tier3_pre_announcement()`
- `daily_check_scheduler()` task
- `event_scheduler()` task

**Global state:**
- `daily_cooldowns = {}`
- `give_cooldowns = {}`
- `vc_members_time = {}`
- `message_cooldowns = {}`

### handlers.py (Lines ~4416-4944 in main.py)
**Functions to extract:**
- `on_message()` handler
- `on_voice_state_update()` handler
- `on_ready()` handler
- `on_command_error()` handler
- `on_raw_reaction_add()` handler
- `on_guild_join()` handler
- `on_member_remove()` handler

### commands/user_commands.py
**Commands to extract:**
- `equip()` - `/equip`
- `level_check()` - `/level check`
- `info()` - `/info`
- `balance()` - `/balance`
- `daily()` - `/daily`
- `give()` - `/give`
- `leaderboards_menu()` - `/leaderboards`
- `leaderboard()` - `/leaderboard`

### commands/admin_commands.py
**Commands to extract:**
- `config()` - `/config`
- `obedience()` - `/obedience`
- `testembeds()` - `/testembeds`
- `throne()` - `/throne`
- `killevent()` - `/killevent`
- `sync_commands()` - `/sync`
- `stopevents()` - `/stopevents`
- `levelrolecheck()` - `/levelrolecheck`
- `levelupdates()` - `/levelupdates`
- `setxp()` - `/setxp`
- `setlevel()` - `/setlevel`
- `schedule()` - `/schedule`

## Import Dependencies

Each module needs:
- `events.py`: config, data, xp, utils, bot instance
- `gambling.py`: config, data, xp, bot instance
- `leaderboards.py`: config, data, bot instance
- `tasks.py`: config, data, events, bot instance
- `handlers.py`: config, data, xp, events, utils, bot instance
- `commands/user_commands.py`: config, data, xp, utils, bot instance
- `commands/admin_commands.py`: config, data, events, utils, bot instance

## Next Steps

1. Create events.py with all event functions
2. Create gambling.py with all gambling commands
3. Create leaderboards.py with leaderboard system
4. Create tasks.py with scheduled tasks
5. Create handlers.py with event handlers
6. Extract commands to commands/ folder
7. Update main.py to import and wire everything

