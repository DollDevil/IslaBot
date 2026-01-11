"""
Scheduled tasks for the bot - VC XP, auto-save, event scheduling, daily checks, V3 progression jobs
"""
import discord
from discord.ext import tasks
import datetime
import random

from core.config import (
    NON_XP_CATEGORY_IDS, NON_XP_CHANNEL_IDS,
    EXCLUDED_ROLE_SET
)
# Legacy XP/Level system removed - V3 progression only
from core.utils import resolve_category_id, get_channel_multiplier, get_timezone, USE_PYTZ
# Legacy event system removed
from core.db import fetchall, fetchone, execute, _today_str, _now_iso, get_announcements_channel_id, get_promo_rotation_state, update_promo_rotation_state
from systems.progression import compute_final_rank, compute_readiness_pct, compute_blocker, compute_held_rank, RANK_LADDER, GATES

# Global flag to stop all automated messages (legacy, kept for compatibility)
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

async def send_throne_announcement(guild):
    """Send Throne announcement message."""
    channel_id = await get_announcements_channel_id(guild.id)
    channel = guild.get_channel(channel_id)
    if not channel:
        print(f"Announcements channel not found (ID: {channel_id})")
        return False
    
    quote_variations = [
        "A good puppy knows where to show appreciation. Throne's waiting.",
        "I wonder who's going to surprise me next.",
        "You already know what to do. My Throne is there.",
        "I don't need to ask twice. Check my Throne.",
        "If you're here, you should already be on Throne.",
    ]
    
    from core.utils import impact_icon
    embed = discord.Embed(
        description=f"*{random.choice(quote_variations)}*\n\n[Go to Throne](https://throne.com/lsla/item/1230a476-4752-4409-9583-9313e60686fe)",
        color=0xff000d,
    )
    embed.set_image(url="https://i.imgur.com/Q6HAYBP.png")
    embed.set_author(name="Throne", icon_url=impact_icon("positive"))
    
    try:
        await channel.send("@everyone", embed=embed)
        print(f"✅ Throne announcement sent to {channel.name}")
        return True
    except Exception as e:
        print(f"Failed to send Throne announcement: {e}")
        return False

async def send_coffee_announcement(guild):
    """Send Coffee announcement message."""
    channel_id = await get_announcements_channel_id(guild.id)
    channel = guild.get_channel(channel_id)
    if not channel:
        print(f"Announcements channel not found (ID: {channel_id})")
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
    
    from core.utils import impact_icon
    embed = discord.Embed(
        title="Coffee Check ☕",
        description=f"{random.choice(description_variants)}\n\n[Buy Coffee](https://throne.com/lsla/item/1230a476-4752-4409-9583-9313e60686fe)",
        color=0xa0b964,
    )
    embed.set_thumbnail(url="https://i.imgur.com/gSoHGEN.png")
    embed.set_footer(text="I remember who takes care of me.")
    embed.set_author(name="Coffee", icon_url=impact_icon("positive"))
    
    try:
        await channel.send("@everyone", embed=embed)
        print(f"✅ Coffee announcement sent to {channel.name}")
        return True
    except Exception as e:
        print(f"Failed to send Coffee announcement: {e}")
        return False

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
        # Convert overdue loans to debt (run once, processes all guilds)
        from core.data import convert_overdue_loans
        converted = await convert_overdue_loans()
        if converted > 0:
            print(f"Converted {converted} overdue loans to debt")
        
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
    """Recompute and cache rank information for a user (with held rank system)"""
    from core.data import get_lce, get_debt
    
    # Get current held rank from cache
    current_cache = await fetchone(
        "SELECT held_rank_idx, at_risk, at_risk_since FROM rank_cache WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    current_held_rank_idx = current_cache["held_rank_idx"] if current_cache and current_cache.get("held_rank_idx") is not None else 0
    current_at_risk = current_cache["at_risk"] if current_cache and current_cache.get("at_risk") else 0
    at_risk_since = current_cache["at_risk_since"] if current_cache else None
    
    lce = await get_lce(guild_id, user_id)
    debt = await get_debt(guild_id, user_id)
    rank_data = await compute_final_rank(guild_id, user_id, lce)
    
    # Compute held rank with promotion/demotion logic
    held_rank_data = await compute_held_rank(
        guild_id, user_id, 
        rank_data["coin_rank"], 
        rank_data["eligible_rank"],
        current_held_rank_idx,
        debt
    )
    
    held_rank = held_rank_data["held_rank"]
    held_rank_idx = held_rank_data["held_rank_idx"]
    at_risk = held_rank_data["at_risk"]
    
    # Handle at-risk persistence (72h)
    now_iso = _now_iso()
    if at_risk == 1:
        if not at_risk_since:
            at_risk_since = now_iso  # Set timestamp when first marked at-risk
        else:
            # Check if 72h has passed
            at_risk_dt = datetime.datetime.fromisoformat(at_risk_since.replace('Z', '+00:00'))
            now_dt = datetime.datetime.fromisoformat(now_iso.replace('Z', '+00:00'))
            if (now_dt - at_risk_dt).total_seconds() >= 72 * 3600:
                # 72h passed, clear at-risk if gates pass
                if at_risk == 0:  # This should be re-computed, but for safety
                    at_risk = 0
                    at_risk_since = None
    else:
        # Not at-risk, clear timestamp
        at_risk_since = None
    
    # Get next rank for readiness calculation (use held_rank, not final_rank)
    rank_names = [r["name"] for r in RANK_LADDER]
    next_idx = min(held_rank_idx + 1, len(rank_names) - 1)
    next_rank = rank_names[next_idx] if next_idx > held_rank_idx else held_rank
    
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
    
    # Track promotions
    last_promotion_at = None
    if held_rank_data.get("promoted"):
        last_promotion_at = now_iso
    
    # Update or insert rank cache (include held rank fields)
    await execute(
        """INSERT OR REPLACE INTO rank_cache 
           (guild_id, user_id, coin_rank, eligible_rank, final_rank, held_rank_idx, at_risk, at_risk_since,
            readiness_pct, blocker_text, computed_at, last_promotion_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (guild_id, user_id, rank_data["coin_rank"], rank_data["eligible_rank"], 
         rank_data["final_rank"], held_rank_idx, at_risk, at_risk_since,
         readiness_pct, blocker_text, now_iso, last_promotion_at)
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


@tasks.loop(hours=1)
async def promo_rotation_scheduler():
    """4-day rotation scheduler for Throne and Coffee announcements"""
    uk_tz = _get_uk_timezone()
    if uk_tz is None:
        return
    
    now_uk = datetime.datetime.now(uk_tz)
    today_str = now_uk.strftime("%Y-%m-%d")
    
    # Run once per day at 12:00 UK time (noon)
    if now_uk.hour != 12 or now_uk.minute > 5:
        return
    
    for guild in bot.guilds:
        try:
            guild_id = guild.id
            
            # Get current rotation state
            state = await get_promo_rotation_state(guild_id)
            rotation_index = state["rotation_index"]
            last_run_day = state["last_run_day"]
            
            # Check if already ran today
            if last_run_day == today_str:
                continue
            
            # Rotation mapping: 0=Throne, 1=nothing, 2=Coffee, 3=nothing
            if rotation_index == 0:
                # Send Throne
                success = await send_throne_announcement(guild)
                if success:
                    new_index = (rotation_index + 1) % 4
                    await update_promo_rotation_state(guild_id, new_index, today_str)
                    print(f"✅ Promo rotation: Sent Throne (index {rotation_index} -> {new_index})")
            
            elif rotation_index == 2:
                # Send Coffee
                success = await send_coffee_announcement(guild)
                if success:
                    new_index = (rotation_index + 1) % 4
                    await update_promo_rotation_state(guild_id, new_index, today_str)
                    print(f"✅ Promo rotation: Sent Coffee (index {rotation_index} -> {new_index})")
            
            else:
                # Index 1 or 3: nothing to send, just update
                new_index = (rotation_index + 1) % 4
                await update_promo_rotation_state(guild_id, new_index, today_str)
                print(f"✅ Promo rotation: No announcement (index {rotation_index} -> {new_index})")
        
        except Exception as e:
            print(f"Error in promo rotation scheduler for guild {guild.id}: {e}")

# Optimization: Cache timezone object to avoid repeated lookups
_cached_uk_tz = None

def _get_uk_timezone():
    """Get UK timezone with caching"""
    global _cached_uk_tz
    if _cached_uk_tz is None:
        _cached_uk_tz = get_timezone("Europe/London")
    return _cached_uk_tz

# Legacy event scheduler removed - replaced with promo rotation scheduler

_last_orders_drop_run = None

@tasks.loop(hours=1)
async def daily_orders_drop_task():
    """Daily orders drop: update available orders and send announcement at reset time"""
    global _last_orders_drop_run
    
    uk_tz = _get_uk_timezone()
    if uk_tz is None:
        return
    
    now_uk = datetime.datetime.now(uk_tz)
    today_str = now_uk.strftime("%Y-%m-%d")
    
    # Run at reset time (00:00 UK, or configurable)
    if now_uk.hour != 0 or now_uk.minute > 5:
        return
    
    if _last_orders_drop_run == today_str:
        return
    
    _last_orders_drop_run = today_str
    print(f"Running daily orders drop at {now_uk.strftime('%Y-%m-%d %H:%M:%S')} UK time")
    
    try:
        for guild in bot.guilds:
            guild_id = guild.id if guild else 0
            
            # Get announcement channel
            config_row = await fetchone(
                "SELECT channel_id FROM orders_announcement_config WHERE guild_id = ?",
                (guild_id,)
            )
            
            if not config_row:
                continue  # No channel configured
            
            channel_id = config_row["channel_id"]
            channel = guild.get_channel(channel_id)
            
            if not channel:
                continue
            
            # Clear today's orders cache (forces refresh on next /orders call)
            # The cache is in user_commands module, so orders will refresh naturally
            
            # Send announcement embed
            from core.utils import impact_icon
            embed = discord.Embed(
                title="Orders",
                description="New orders available, complete them to gain my favor. \n\nRemember, I reward good pups who get their orders done, and those who don't.. well..",
            )
            embed.set_thumbnail(url="https://i.imgur.com/sGDoIDA.png")
            embed.set_footer(text="Type /orders in #commands channel")
            embed.set_author(name="Orders", icon_url=impact_icon("neutral"))
            
            try:
                await channel.send(embed=embed)
                print(f"Sent daily orders drop announcement to {channel.name} in {guild.name}")
            except Exception as e:
                print(f"Failed to send orders announcement in {guild.name}: {e}")
    
    except Exception as e:
        print(f"Error in daily_orders_drop_task: {e}")

@tasks.loop(minutes=15)
async def personal_order_reminders_task():
    """Send personal DM reminders for active orders with <= 2h left (for opted-in users)"""
    try:
        for guild in bot.guilds:
            guild_id = guild.id if guild else 0
            
            # Get all opted-in users
            opted_in_users = await fetchall(
                "SELECT user_id FROM user_notifications WHERE guild_id = ? AND enabled = 1",
                (guild_id,)
            )
            
            for row in opted_in_users:
                user_id = row["user_id"]
                
                try:
                    # Get active orders for this user
                    active_runs = await fetchall(
                        """SELECT run_id, order_id, due_at FROM order_runs 
                           WHERE guild_id = ? AND user_id = ? AND status = 'accepted'
                           ORDER BY due_at""",
                        (guild_id, user_id)
                    )
                    
                    now = datetime.datetime.now(datetime.UTC)
                    
                    for run in active_runs:
                        due_at = datetime.datetime.fromisoformat(run["due_at"].replace('Z', '+00:00'))
                        time_left = (due_at - now).total_seconds()
                        
                        # Check if <= 2 hours left (7200 seconds)
                        if 0 < time_left <= 7200:
                            # Check if reminder already sent for this run
                            reminder_sent = await fetchone(
                                "SELECT reminder_sent_at FROM order_reminders WHERE guild_id = ? AND user_id = ? AND run_id = ?",
                                (guild_id, user_id, run["run_id"])
                            )
                            
                            if reminder_sent:
                                continue  # Already sent
                            
                            # Get order name
                            order_row = await fetchone(
                                "SELECT name FROM orders WHERE order_id = ?",
                                (run["order_id"],)
                            )
                            
                            if not order_row:
                                continue
                            
                            order_name = order_row["name"]
                            hours_left = int(time_left / 3600)
                            minutes_left = int((time_left % 3600) / 60)
                            
                            # Send DM reminder
                            try:
                                user = await bot.fetch_user(user_id)
                                from core.utils import impact_icon
                                
                                embed = discord.Embed(
                                    title="Order Reminder",
                                    description=f"Your order **{order_name}** is due in {hours_left}h {minutes_left}min.\n\nComplete it on time to earn your reward.",
                                )
                                embed.set_author(name="Orders", icon_url=impact_icon("neutral"))
                                
                                await user.send(embed=embed)
                                
                                # Mark reminder as sent
                                await execute(
                                    "INSERT INTO order_reminders (guild_id, user_id, run_id, reminder_sent_at) VALUES (?, ?, ?, ?)",
                                    (guild_id, user_id, run["run_id"], _now_iso())
                                )
                                
                            except discord.Forbidden:
                                # User has DMs disabled, skip
                                pass
                            except Exception as e:
                                print(f"Failed to send reminder to user {user_id}: {e}")
                
                except Exception as e:
                    print(f"Error processing reminders for user {user_id}: {e}")
    
    except Exception as e:
        print(f"Error in personal_order_reminders_task: {e}")

