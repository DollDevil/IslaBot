"""
Scheduled tasks for the bot - VC XP, auto-save, event scheduling, daily checks, V3 progression jobs
"""
import discord
from discord.ext import tasks
import datetime
import random

from core.config import (
    EVENT_CHANNEL_ID, EVENT_SCHEDULE, EVENT_TIER_MAP, VC_XP,
    VC_XP_TRACK_CHANNELS, NON_XP_CATEGORY_IDS, NON_XP_CHANNEL_IDS,
    EXCLUDED_ROLE_SET, USER_COMMAND_CHANNEL_ID
)
from core.data import xp_data, save_xp_data
from systems.xp import add_xp
from core.utils import resolve_category_id, get_channel_multiplier, get_timezone, USE_PYTZ
from systems.events import active_event, start_obedience_event, events_enabled
from core.db import fetchall, execute, _today_str, _now_iso
from systems.progression import compute_final_rank, compute_readiness_pct, compute_blocker, RANK_LADDER, GATES

# Global state for tracking
last_event_times_today = set()
last_daily_check_times_today = set()

# Global flag to stop all automated messages
automated_messages_enabled = True

# Bot instance (set by main.py)
bot = None

def set_bot(bot_instance):
    """Set the bot instance for this module"""
    global bot
    bot = bot_instance

def set_automated_messages_enabled(enabled: bool):
    """Enable or disable all automated messages (events, daily checks, etc.)"""
    global automated_messages_enabled
    automated_messages_enabled = enabled
    return automated_messages_enabled

def get_automated_messages_enabled():
    """Get the current state of automated messages"""
    return automated_messages_enabled

def get_next_scheduled_time(hour: int, minute: int) -> int:
    """Get next occurrence of a scheduled time in UK timezone as Unix timestamp."""
    uk_tz = get_timezone("Europe/London")
    if uk_tz is None:
        uk_tz = datetime.timezone.utc
    
    if USE_PYTZ:
        now_uk = datetime.datetime.now(uk_tz)
    else:
        now_uk = datetime.datetime.now(uk_tz)
    
    target_time = now_uk.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if target_time <= now_uk:
        target_time += datetime.timedelta(days=1)
    
    if USE_PYTZ:
        target_utc = target_time.astimezone(datetime.timezone.utc)
    else:
        target_utc = target_time.astimezone(datetime.timezone.utc)
    
    return int(target_utc.timestamp())

async def send_tier3_pre_announcement(guild):
    """Send pre-announcement for Tier 3 events 5 minutes before they start."""
    channel = guild.get_channel(EVENT_CHANNEL_ID)
    if not channel:
        return
    
    embed = discord.Embed(
        description="\nS̵̛̳̜͕͓͎͚̹̯̟͔̃͌̉͠ȯ̵͕̣͊͛̓̅̆̊̉͌̚͘͝m̶̢̨͍̺͔͖̩̼͇̪̰̮͐͋̑̆̓͐̀ͅè̸̡̢̤̺̩̠̼̲̖̰̫̼̜̊̽͗̉̇̑ṭ̷̨̛̦̘̻̙̼̪̩̫̖̘͋́̎̄͌̓̕͝h̸̩̪͚̘̯͉̮̩̼̬͕͂̂͂̄i̷̡̨̨̫̳̟͍͎̟̯͉̳̞̩̓̄͆͛̕n̴̲͔͎̊̅̈́͂̀͒̔̈́̆͂̾͠g̸̨̢̩̳̣͔̹͇̩͚̺̳͕̣͕͋̍̈́̾̓͊̄̿̓͝ ̸͔͚̟̪̺̝̳̻͍̺̟͛̀́̀̍́̋͜͜͜͝ï̵̪̘̦̬͎̗͊̊͊̍̂̊s̷̤̰̳͇̰̥̹͖̤̼͌̃͑̾̒͗͑̓̅́͑̚̚͜ ̷̡̡̼̻̳̻̠̯̜̘͇̟̠̱̖̎́̀̔̍͂̇̄̏̈́ơ̵̧̘̮̊̽̑̆̎̿̂̍̋͑̈́͘n̶̘̞̮̺̫̭̩̜̜͎̈́̓̋̓̾͊̇̆́͂̍̐͠ ̵̱̊̂̕͠t̷̛͙̗͍̩̞̥̹͂̾͋̅̀̄̉̐͐̈́̂͘͠h̴̼͍̙̬͖̍̄̓̀e̴̢̛̅͒͊̽͐̚͝ ̴̨̛̭̱̖̜̣̝̝̓̅̓̀̈́̉̿͂̆̂͂͜͝͝ẃ̴̭̗̳̳̳͂͗̇̍̿͑a̶͚͚͕̠̳̭̘͐̍ÿ̷̛̫͕̘͍́̽̿̚͠.̶̳͍̩̇̊͜.̷̜̼̌͐̔.̶̧̨̩̳̮̟̖͈̘͕̻̣̱̎͒̀̈́͘\n\n◊ ¿°ᵛ˘ æ¢ɲæ ˘ɲ±æ≤ ┍ææ≥, \"˘æ\"¿˘, Әɲ≥",
        color=0xff000d,
    )
    embed.set_image(url="https://i.imgur.com/gvhIpAG.gif")
    
    try:
        await channel.send(embed=embed)
        print("Sent Tier 3 pre-announcement")
    except Exception as e:
        print(f"Failed to send Tier 3 pre-announcement: {e}")

async def send_daily_check_dailycommand(guild):
    """Send Daily Check message for /daily command."""
    daily_channel = guild.get_channel(USER_COMMAND_CHANNEL_ID)
    if not daily_channel:
        print(f"Daily check channel not found (ID: {USER_COMMAND_CHANNEL_ID})")
        return False
    
    embed = discord.Embed(
        title="Daily Check <:kisses:1449998044446593125>",
        description="Have you checked in today?\nYour coins are waiting.\n\nType `/daily` in <#1450107538019192832> to claim your allocation.",
        color=0xcdb623,
    )
    embed.set_thumbnail(url="https://i.imgur.com/zMiZC5b.png")
    embed.set_footer(text="Resets daily at 6:00 PM GMT")
    
    try:
        await daily_channel.send(embed=embed)
        print(f"✅ Daily Check (/daily) sent to {daily_channel.name}")
        return True
    except Exception as e:
        print(f"Failed to send Daily Check (/daily): {e}")
        return False

async def send_daily_check_throne(guild):
    """Send Daily Check message for Throne coffee."""
    throne_channel = guild.get_channel(EVENT_CHANNEL_ID)
    if not throne_channel:
        print(f"Throne check channel not found (ID: {EVENT_CHANNEL_ID})")
        return False
    
    description_variants = [
        "I haven't had my coffee yet.\nYou wouldn't want me disappointed today, would you?",
        "I woke up craving something warm…\nCoffee would be a very good start.",
        "My focus is slipping.\nA coffee would fix that.",
        "I expect to be taken care of.\nCoffee sounds like the correct choice right now.",
        "I'm watching the day unfold.\nCoffee would improve my mood significantly.",
        "You know what I like.\nCoffee. Warm. Thoughtful. Timely.",
        "I could handle the day without coffee…\nBut I'd rather not have to.",
    ]
    
    embed = discord.Embed(
        title="Coffee Check ☕",
        description=f"{random.choice(description_variants)}\n\n[Buy Coffee](https://throne.com/lsla/item/1230a476-4752-4409-9583-9313e60686fe)",
        color=0xa0b964,
    )
    embed.set_thumbnail(url="https://i.imgur.com/gSoHGEN.png")
    embed.set_footer(text="I remember who takes care of me.")
    
    try:
        await throne_channel.send("@everyone", embed=embed)
        print(f"✅ Daily Check (Throne) sent to {throne_channel.name}")
        return True
    except Exception as e:
        print(f"Failed to send Daily Check (Throne): {e}")
        return False

async def send_daily_check_slots(guild):
    """Send Daily Check message for Slots."""
    slots_channel = guild.get_channel(EVENT_CHANNEL_ID)
    if not slots_channel:
        print(f"Slots check channel not found (ID: {EVENT_CHANNEL_ID})")
        return False
    
    description_variants = [
        "I'm in the mood to watch you try your luck.\nGo play my slots.",
        "I enjoy seeing effort turn into results.\nSlots would be a good use of your time right now.",
        "I wonder how lucky you're feeling today.\nWhy don't you find out for me?",
        "Luck favors the attentive.\nYou should give my slots a try.",
        "I'm watching.\nThis would be a good moment to play.",
        "Sometimes obedience looks like initiative.\nSlots. Now.",
        "I like it when you make the right choice on your own.\nMy slots are waiting.",
    ]
    
    embed = discord.Embed(
        title="Slots Check 🎲",
        description=f"{random.choice(description_variants)}\n\n[Buy Slots](https://islaexe.itch.io/islas-slots)",
        color=0xcd6032,
    )
    embed.set_thumbnail(url="https://i.imgur.com/KEnVDdy.png")
    embed.set_footer(text="This is part of your role.")
    
    try:
        await slots_channel.send("@everyone", embed=embed)
        print(f"✅ Daily Check (Slots) sent to {slots_channel.name}")
        return True
    except Exception as e:
        print(f"Failed to send Daily Check (Slots): {e}")
        return False

@tasks.loop(minutes=1)
async def award_vc_xp():
    """Award XP every minute to users in tracked voice channels"""
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            if vc.id not in VC_XP_TRACK_CHANNELS:
                continue
            
            for member in vc.members:
                if member.bot:
                    continue
                if any(int(role.id) in EXCLUDED_ROLE_SET for role in member.roles):
                    print(f"Skipped VC XP for {member.name} (has excluded role)")
                    continue
                category_id = resolve_category_id(vc)
                if category_id in NON_XP_CATEGORY_IDS or vc.id in NON_XP_CHANNEL_IDS:
                    print(f"Skipped VC XP for {member.name} (excluded VC/channel/category)")
                    continue
                
                xp_to_award = VC_XP
                if active_event and active_event.get("type") == 2:
                    event_start = active_event.get("started_at")
                    if event_start:
                        elapsed = (datetime.datetime.now(datetime.UTC) - event_start).total_seconds()
                        if elapsed <= 300:
                            xp_to_award = VC_XP * 2
                
                guild_id = guild.id if guild else 0
                from core.db import add_vc_minutes
                await add_vc_minutes(guild_id, member.id, 1)
                
                base_mult = get_channel_multiplier(vc.id)
                await add_xp(member.id, xp_to_award, member=member, base_multiplier=base_mult, guild_id=guild_id)
                event_bonus = " (Event 2 double XP)" if xp_to_award > VC_XP else ""
                print(f"Awarded {xp_to_award} VC XP to {member.name} in {vc.name} (channel mult {base_mult}x){event_bonus}")

@tasks.loop(minutes=5)
async def auto_save():
    """Periodically save XP data as backup (force save to ensure data persistence)"""
    # Data is now in SQLite, no periodic JSON save needed
    print(f"Auto-save check completed at {datetime.datetime.now(datetime.UTC)} (using SQLite)")

# V3 Progression: Daily and Weekly Jobs
_last_daily_job_run = None
_last_weekly_job_run = None

@tasks.loop(hours=1)
async def v3_daily_job():
    """V3 Progression daily job: inactivity tax, obedience decay, rank cache, role assignment"""
    global _last_daily_job_run
    
    uk_tz = _get_uk_timezone()
    if uk_tz is None:
        return
    
    now_uk = datetime.datetime.now(uk_tz)
    today_str = now_uk.strftime("%Y-%m-%d")
    
    # Run once per day at 00:00 UK time
    if now_uk.hour != 0 or now_uk.minute > 5:
        return
    
    if _last_daily_job_run == today_str:
        return
    
    _last_daily_job_run = today_str
    print(f"Running V3 daily job at {now_uk.strftime('%Y-%m-%d %H:%M:%S')} UK time")
    
    try:
        # Get all active users (users with activity in last 30 days)
        thirty_days_ago = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=30)).date().isoformat()
        
        for guild in bot.guilds:
            guild_id = guild.id if guild else 0
            
            # Get users with recent activity
            active_users = await fetchall(
                """SELECT DISTINCT user_id FROM activity_daily 
                   WHERE guild_id = ? AND day >= ?""",
                (guild_id, thirty_days_ago)
            )
            
            processed_count = 0
            for row in active_users:
                user_id = row["user_id"]
                
                try:
                            # 1. Apply inactivity tax
                    await _apply_inactivity_tax(guild_id, user_id)
                    
                    # 2. Obedience decay is already handled in compute_obedience14
                    # (it checks if no orders completed today and reduces by 1%)
                    
                    # 3. Recompute rank cache
                    await _recompute_rank_cache(guild_id, user_id)
                    
                    processed_count += 1
                except Exception as e:
                    print(f"Error processing user {user_id} in daily job: {e}")
            
            # 4. Role assignment by rank (process all users with rank_cache entries)
            await _assign_ranks_roles(guild_id)
            
            print(f"V3 daily job completed for guild {guild_id}: {processed_count} users processed")
    
    except Exception as e:
        print(f"Error in V3 daily job: {e}")

async def _apply_inactivity_tax(guild_id: int, user_id: int):
    """Apply inactivity tax if user hasn't been active"""
    # Check if user had qualifying activity today
    today = _today_str()
    activity = await fetchall(
        """SELECT messages, vc_minutes FROM activity_daily 
           WHERE guild_id = ? AND user_id = ? AND day = ?""",
        (guild_id, user_id, today)
    )
    
    has_activity = False
    if activity:
        for row in activity:
            if (row["messages"] or 0) > 0 or (row["vc_minutes"] or 0) > 0:
                has_activity = True
                break
    
    if not has_activity:
        # Get balance and apply tax (5% of balance, minimum 10 coins)
        from core.db import fetchone
        balance_row = await fetchone(
            "SELECT coins_balance FROM economy_balance WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        
        if balance_row and balance_row["coins_balance"] > 0:
            balance = balance_row["coins_balance"]
            tax_amount = max(10, int(balance * 0.05))
            
            # Deduct tax
            from core.data import add_coins
            await add_coins(guild_id, user_id, -tax_amount, "inactivity_tax", {"tax_amount": tax_amount})
            
            # Update discipline state
            await execute(
                """UPDATE discipline_state 
                   SET inactive_days = inactive_days + 1, last_taxed_at = ?, updated_at = ?
                   WHERE guild_id = ? AND user_id = ?""",
                (_now_iso(), _now_iso(), guild_id, user_id)
            )

async def _recompute_rank_cache(guild_id: int, user_id: int):
    """Recompute and cache rank information for a user"""
    from core.data import get_lce
    
    lce = await get_lce(guild_id, user_id)
    rank_data = await compute_final_rank(guild_id, user_id, lce)
    
    # Get next rank for readiness calculation
    rank_names = [r["name"] for r in RANK_LADDER]
    current_rank = rank_data["final_rank"]
    current_idx = rank_names.index(current_rank) if current_rank in rank_names else 0
    next_idx = min(current_idx + 1, len(rank_names) - 1)
    next_rank = rank_names[next_idx] if next_idx > current_idx else current_rank
    
    readiness_pct = await compute_readiness_pct(guild_id, user_id, next_rank)
    blocker_text = await compute_blocker(guild_id, user_id, next_rank)
    
    # Check for failed gates (for soft demotion tracking)
    failed_gates_count = 0
    if next_rank != "Max Rank" and next_rank in GATES:
        from core.data import get_profile_stats
        stats = await get_profile_stats(guild_id, user_id)
        gates = GATES[next_rank]
        
        for gate in gates:
            gate_type = gate["type"]
            gate_min = gate["min"]
            
            if gate_type == "messages_7d" and stats.get("messages_sent", 0) < gate_min:
                failed_gates_count += 1
            elif gate_type == "was" and stats.get("was", 0) < gate_min:
                failed_gates_count += 1
            elif gate_type == "obedience14" and stats.get("obedience_pct", 0) < gate_min:
                failed_gates_count += 1
        
        if stats.get("orders_failed", 0) > 4:
            failed_gates_count += 1
        if stats.get("orders_late", 0) > 2:
            failed_gates_count += 1
    
    # Update or insert rank cache
    await execute(
        """INSERT OR REPLACE INTO rank_cache 
           (guild_id, user_id, coin_rank, eligible_rank, final_rank, readiness_pct, blocker_text, computed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (guild_id, user_id, rank_data["coin_rank"], rank_data["eligible_rank"], 
         rank_data["final_rank"], readiness_pct, blocker_text, _now_iso())
    )

async def _assign_ranks_roles(guild_id: int):
    """Assign Discord roles based on user ranks (placeholder - implement role IDs mapping)"""
    # This is a placeholder - implement role assignment logic based on your server's role setup
    # You'll need to map ranks to role IDs in config.py
    pass

@tasks.loop(hours=12)
async def v3_weekly_job():
    """V3 Progression weekly job: debt interest, weekly claim reset, soft demotion"""
    global _last_weekly_job_run
    
    uk_tz = _get_uk_timezone()
    if uk_tz is None:
        return
    
    now_uk = datetime.datetime.now(uk_tz)
    
    # Run once per week on Monday at 00:00 UK time
    if now_uk.weekday() != 0 or now_uk.hour != 0 or now_uk.minute > 5:
        return
    
    week_str = now_uk.strftime("%Y-W%W")
    if _last_weekly_job_run == week_str:
        return
    
    _last_weekly_job_run = week_str
    print(f"Running V3 weekly job at {now_uk.strftime('%Y-%m-%d %H:%M:%S')} UK time")
    
    try:
        for guild in bot.guilds:
            guild_id = guild.id if guild else 0
            
            # Get all users with debt or discipline state
            users = await fetchall(
                """SELECT DISTINCT user_id FROM discipline_state WHERE guild_id = ? AND debt > 0
                   UNION
                   SELECT DISTINCT user_id FROM weekly_claims WHERE guild_id = ?""",
                (guild_id, guild_id)
            )
            
            processed_count = 0
            for row in users:
                user_id = row["user_id"]
                
                try:
                    # 1. Apply debt interest (3%)
                    await _apply_debt_interest(guild_id, user_id)
                    
                    # 2. Reset weekly claim (allow users to claim again)
                    # Weekly claim reset happens automatically when they use /coins weekly
                    # But we can clear old entries older than 7 days
                    seven_days_ago = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7)).isoformat()
                    await execute(
                        """DELETE FROM weekly_claims 
                           WHERE guild_id = ? AND user_id = ? AND last_claimed_at < ?""",
                        (guild_id, user_id, seven_days_ago)
                    )
                    
                    # 3. Evaluate soft demotion (2 consecutive weeks failing gates)
                    await _evaluate_soft_demotion(guild_id, user_id)
                    
                    processed_count += 1
                except Exception as e:
                    print(f"Error processing user {user_id} in weekly job: {e}")
            
            print(f"V3 weekly job completed for guild {guild_id}: {processed_count} users processed")
    
    except Exception as e:
        print(f"Error in V3 weekly job: {e}")

@tasks.loop(hours=6)
async def cleanup_expired_events_task():
    """Cleanup expired event data (runs every 6 hours)"""
    try:
        from core.db import cleanup_expired_events
        await cleanup_expired_events()
    except Exception as e:
        print(f"Error in cleanup_expired_events_task: {e}")

async def _apply_debt_interest(guild_id: int, user_id: int):
    """Apply 3% interest to debt"""
    from core.db import fetchone
    debt_row = await fetchone(
        "SELECT debt FROM discipline_state WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    
    if debt_row and debt_row["debt"] > 0:
        current_debt = debt_row["debt"]
        interest = int(current_debt * 0.03)
        
        await execute(
            """UPDATE discipline_state 
               SET debt = debt + ?, updated_at = ?
               WHERE guild_id = ? AND user_id = ?""",
            (interest, _now_iso(), guild_id, user_id)
        )

async def _evaluate_soft_demotion(guild_id: int, user_id: int):
    """Evaluate if user should be soft demoted (2 consecutive weeks failing gates)"""
    from core.db import fetchone
    rank_cache = await fetchone(
        "SELECT failed_weeks_count, final_rank FROM rank_cache WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    
    if not rank_cache:
        return
    
    current_rank = rank_cache["final_rank"]
    failed_weeks = rank_cache.get("failed_weeks_count", 0) or 0
    
    # Check if user is failing gates for their current rank
    if current_rank in GATES:
        from core.data import get_profile_stats
        stats = await get_profile_stats(guild_id, user_id)
        gates = GATES[current_rank]
        
        failing_gates = 0
        for gate in gates:
            gate_type = gate["type"]
            gate_min = gate["min"]
            
            if gate_type == "messages_7d" and stats.get("messages_sent", 0) < gate_min:
                failing_gates += 1
            elif gate_type == "was" and stats.get("was", 0) < gate_min:
                failing_gates += 1
            elif gate_type == "obedience14" and stats.get("obedience_pct", 0) < gate_min:
                failing_gates += 1
        
        if stats.get("orders_failed", 0) > 4:
            failing_gates += 1
        if stats.get("orders_late", 0) > 2:
            failing_gates += 1
        
        if failing_gates > 0:
            # Increment failed weeks count
            new_count = failed_weeks + 1
            await execute(
                """UPDATE rank_cache 
                   SET failed_weeks_count = ?, computed_at = ?
                   WHERE guild_id = ? AND user_id = ?""",
                (new_count, _now_iso(), guild_id, user_id)
            )
            
            # If 2 consecutive weeks failing, soft demote by 1 rank
            if new_count >= 2:
                rank_names = [r["name"] for r in RANK_LADDER]
                current_idx = rank_names.index(current_rank) if current_rank in rank_names else 0
                if current_idx > 0:
                    demoted_rank = rank_names[current_idx - 1]
                    await execute(
                        """UPDATE rank_cache 
                           SET final_rank = ?, failed_weeks_count = 0, computed_at = ?
                           WHERE guild_id = ? AND user_id = ?""",
                        (demoted_rank, _now_iso(), guild_id, user_id)
                    )
                    print(f"Soft demoted user {user_id} from {current_rank} to {demoted_rank}")
        else:
            # Reset failed weeks count if all gates passed
            if failed_weeks > 0:
                await execute(
                    """UPDATE rank_cache 
                       SET failed_weeks_count = 0, computed_at = ?
                       WHERE guild_id = ? AND user_id = ?""",
                    (_now_iso(), guild_id, user_id)
                )


@tasks.loop(minutes=1)
async def daily_check_scheduler():
    """Automatically send Daily Check messages at scheduled times."""
    global last_daily_check_times_today
    
    # Check if automated messages are disabled
    if not automated_messages_enabled:
        return
    
    uk_tz = _get_uk_timezone()
    if uk_tz is None:
        return
    
    now_uk = datetime.datetime.now(uk_tz)
    
    today_str = now_uk.strftime("%Y-%m-%d")
    current_time = (now_uk.hour, now_uk.minute)
    
    last_daily_check_times_today = {entry for entry in last_daily_check_times_today if entry.startswith(today_str)}
    
    daily_check_times = [
        (19, 0, "throne"),
        (20, 0, "slots"),
        (22, 0, "daily"),
    ]
    
    for hour, minute, check_type in daily_check_times:
        time_diff = abs((now_uk.hour * 60 + now_uk.minute) - (hour * 60 + minute))
        
        if time_diff <= 1:
            check_key = f"{today_str}_DAILY_CHECK_{check_type}_{hour:02d}:{minute:02d}"
            
            if check_key in last_daily_check_times_today:
                continue
            
            for guild in bot.guilds:
                if check_type == "throne":
                    success = await send_daily_check_throne(guild)
                elif check_type == "slots":
                    success = await send_daily_check_slots(guild)
                elif check_type == "daily":
                    success = await send_daily_check_dailycommand(guild)
                else:
                    success = False
                
                if success:
                    last_daily_check_times_today.add(check_key)
                    print(f"Auto-sent Daily Check ({check_type}) at {now_uk.strftime('%H:%M:%S')} UK time")
                    break

# Optimization: Cache timezone object to avoid repeated lookups
_cached_uk_tz = None

def _get_uk_timezone():
    """Get UK timezone with caching"""
    global _cached_uk_tz
    if _cached_uk_tz is None:
        _cached_uk_tz = get_timezone("Europe/London")
    return _cached_uk_tz

@tasks.loop(minutes=1)
async def event_scheduler():
    """Automatically schedule events based on UK timezone schedule"""
    global active_event, last_event_times_today
    from systems.events import event_cooldown_until
    
    # Check if automated messages are disabled
    if not automated_messages_enabled:
        return
    
    if not events_enabled:
        return
    
    if active_event:
        return
    if event_cooldown_until and datetime.datetime.now(datetime.UTC) < event_cooldown_until:
        return
    
    uk_tz = _get_uk_timezone()
    if uk_tz is None:
        print("ERROR: Timezone support not available. Cannot schedule events. Install pytz: pip install pytz")
        return
    
    now_uk = datetime.datetime.now(uk_tz)
    today_str = now_uk.strftime("%Y-%m-%d")
    current_time = (now_uk.hour, now_uk.minute)
    
    last_event_times_today = {entry for entry in last_event_times_today if entry.startswith(today_str)}
    
    if current_time == (23, 55):
        tomorrow = (now_uk + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        pre_announce_key = f"{tomorrow}_TIER_3_00:00_pre_announced"
        if pre_announce_key not in last_event_times_today:
            for guild in bot.guilds:
                await send_tier3_pre_announcement(guild)
            last_event_times_today.add(pre_announce_key)
            print(f"Sent Tier 3 pre-announcement at {now_uk.strftime('%H:%M:%S')} UK time (for event at 00:00)")
    
    for tier, scheduled_times in EVENT_SCHEDULE.items():
        for hour, minute in scheduled_times:
            time_diff = abs((now_uk.hour * 60 + now_uk.minute) - (hour * 60 + minute))
            
            if time_diff <= 1:
                event_key = f"{today_str}_TIER_{tier}_{hour:02d}:{minute:02d}"
                
                if event_key in last_event_times_today:
                    continue
                
                # Optimization: Pre-filter events by tier (more efficient than list comprehension)
                available_events = [et for et, t in EVENT_TIER_MAP.items() if t == tier]
                if not available_events:
                    continue
                
                event_type = random.choice(available_events)
                
                for guild in bot.guilds:
                    event_channel = guild.get_channel(EVENT_CHANNEL_ID)
                    if event_channel:
                        try:
                            await start_obedience_event(guild, event_type, channel=event_channel)
                            last_event_times_today.add(event_key)
                            if tier == 3 and hour == 0 and minute == 0:
                                last_event_times_today.discard(f"{today_str}_TIER_3_00:00_pre_announced")
                            print(f"Auto-started Event {event_type} (Tier {tier}) at {now_uk.strftime('%H:%M:%S')} UK time")
                            return
                        except Exception as e:
                            print(f"Failed to auto-start event {event_type}: {e}")
                        break

