"""
Data management for user XP, levels, coins, and statistics - SQLite-backed V3 Progression System
"""
import random
import datetime
import json
from core.db import (
    init_db, close_db, upsert_user_profile, upsert_economy_balance,
    bump_message, add_vc_minutes, bump_event, get_activity_7d,
    get_inventory_items, get_equipped_items,
    fetchone, execute, _now_iso
)

# Legacy xp_data dict for backward compatibility during transition
xp_data = {}

# Track if DB is initialized
_db_initialized = False

async def initialize_database():
    """Initialize database (V3: JSON import removed)"""
    global _db_initialized
    if _db_initialized:
        return
    
    await init_db()
    # V3: import_json_to_db removed (XP/Level system deprecated)
    _db_initialized = True

async def shutdown_database():
    """Close database connection"""
    await close_db()

def load_xp_data():
    """Legacy function - now does nothing (data is in DB)"""
    # This is called at startup, but we'll do the DB init in on_ready instead
    pass

async def import_json_to_db_async():
    """Legacy function - V3: JSON import removed (XP/Level deprecated)"""
    pass

def save_xp_data(force=False):
    """Legacy function - now does nothing (data is in DB)"""
    pass

# Backward-compatible wrapper functions that default to guild_id=0
def _get_guild_id(guild_id=None, guild=None):
    """Get guild_id from parameter or guild object, default to 0"""
    if guild_id is not None:
        return int(guild_id)
    if guild is not None:
        return int(guild.id)
    return 0

async def get_xp(user_id, guild_id=None, guild=None):
    """Legacy function - V3: XP system removed, always returns 0"""
    # V3 Migration: XP/Level system deprecated
    return 0

async def get_level(user_id, guild_id=None, guild=None):
    """Legacy function - V3: Level system removed, always returns 1"""
    # V3 Migration: XP/Level system deprecated
    return 1

async def get_coins(user_id, guild_id=None, guild=None):
    """Get user's coin balance"""
    gid = _get_guild_id(guild_id, guild)
    row = await fetchone(
        "SELECT coins_balance FROM economy_balance WHERE guild_id = ? AND user_id = ?",
        (gid, int(user_id))
    )
    if row:
        return row["coins_balance"]
    
    # Fallback to user_profile.coins for legacy
    row = await fetchone(
        "SELECT coins FROM user_profile WHERE guild_id = ? AND user_id = ?",
        (gid, int(user_id))
    )
    return row["coins"] if row else 0

async def add_coins(user_id, amount, guild_id=None, guild=None, reason: str = "unknown", meta: dict = None):
    """Add coins to user's balance and log to ledger"""
    gid = _get_guild_id(guild_id, guild)
    user_id = int(user_id)
    
    # Update economy balance
    await upsert_economy_balance(gid, user_id, amount)
    
    # Log to ledger
    now = _now_iso()
    meta_json = json.dumps(meta) if meta else None
    await execute(
        "INSERT INTO economy_ledger (guild_id, user_id, ts, type, amount, meta_json) VALUES (?, ?, ?, ?, ?, ?)",
        (gid, user_id, now, reason, amount, meta_json)
    )
    
    # Also update user_profile.coins for backward compatibility
    current = await get_coins(user_id, gid)
    await upsert_user_profile(gid, user_id, coins=current)

async def has_coins(user_id, amount, guild_id=None, guild=None):
    """Check if user has enough coins"""
    coins = await get_coins(user_id, guild_id, guild)
    return coins >= amount

async def increment_event_participation(user_id, guild_id=None, guild=None):
    """Increment event participation count for a user"""
    gid = _get_guild_id(guild_id, guild)
    await bump_event(gid, int(user_id))
    
    # Update total in user_profile (for backward compatibility)
    row = await fetchone(
        "SELECT times_gambled, total_wins, total_spent FROM user_profile WHERE guild_id = ? AND user_id = ?",
        (gid, int(user_id))
    )
    # We track events in activity_daily, so this is mainly for compatibility

async def increment_gambling_attempt(user_id, guild_id=None, guild=None):
    """Increment gambling attempt count for a user"""
    gid = _get_guild_id(guild_id, guild)
    row = await fetchone(
        "SELECT times_gambled FROM user_profile WHERE guild_id = ? AND user_id = ?",
        (gid, int(user_id))
    )
    current = row["times_gambled"] if row else 0
    await upsert_user_profile(gid, int(user_id), times_gambled=current + 1)

async def add_gambling_spent(user_id, amount, guild_id=None, guild=None):
    """Add to total money spent on gambling"""
    gid = _get_guild_id(guild_id, guild)
    row = await fetchone(
        "SELECT total_spent FROM user_profile WHERE guild_id = ? AND user_id = ?",
        (gid, int(user_id))
    )
    current = row["total_spent"] if row else 0
    await upsert_user_profile(gid, int(user_id), total_spent=current + amount)

async def increment_gambling_win(user_id, guild_id=None, guild=None):
    """Increment gambling win count for a user"""
    gid = _get_guild_id(guild_id, guild)
    row = await fetchone(
        "SELECT total_wins FROM user_profile WHERE guild_id = ? AND user_id = ?",
        (gid, int(user_id))
    )
    current = row["total_wins"] if row else 0
    await upsert_user_profile(gid, int(user_id), total_wins=current + 1)

# ===== GAMBLING POLICY HELPERS (V3-STYLE) =====

async def get_user_economy(guild_id, user_id):
    """Get user economy stats (bal, lce, debt)"""
    from core.config import LCE_RANK_THRESHOLDS, RANK_MAX_BET
    
    gid = int(guild_id) if guild_id else 0
    uid = int(user_id)
    
    # Get balance and LCE
    balance_row = await fetchone(
        "SELECT coins_balance, coins_lifetime_earned FROM economy_balance WHERE guild_id = ? AND user_id = ?",
        (gid, uid)
    )
    bal = balance_row["coins_balance"] if balance_row else 0
    lce = balance_row["coins_lifetime_earned"] if balance_row else 0
    
    # Get debt
    debt_row = await fetchone(
        "SELECT debt FROM discipline_state WHERE guild_id = ? AND user_id = ?",
        (gid, uid)
    )
    debt = debt_row["debt"] if debt_row else 0
    
    # Compute rank from LCE
    rank = "Stray"
    for threshold, rank_name in sorted(LCE_RANK_THRESHOLDS.items(), reverse=True):
        if lce >= threshold:
            rank = rank_name
            break
    
    # Get rank bet cap
    rank_cap = RANK_MAX_BET.get(rank, 500)
    
    return {
        "bal": bal,
        "lce": lce,
        "debt": debt,
        "rank": rank,
        "rank_cap": rank_cap,
    }

async def take_bet(guild_id, user_id, bet):
    """Deduct bet from balance"""
    gid = int(guild_id) if guild_id else 0
    uid = int(user_id)
    await upsert_economy_balance(gid, uid, -bet)

async def payout_winnings(guild_id, user_id, amount):
    """Add winnings to balance AND lifetime earned (V3 invariant)"""
    gid = int(guild_id) if guild_id else 0
    uid = int(user_id)
    
    # Increase balance
    await upsert_economy_balance(gid, uid, amount)
    
    # CRITICAL: Also increase lifetime earned for winnings (V3 rule)
    # This is handled by upsert_economy_balance when coins_delta > 0

async def get_activity_quote(user_id, guild=None):
    """Get activity quote based on user stats with priority order"""
    guild_id = guild.id if guild else 0
    
    # Get 7-day activity
    activity = await get_activity_7d(guild_id, int(user_id))
    messages_sent = activity["messages"]
    vc_minutes = activity["vc_minutes"]
    event_participations = activity["events"]
    
    # Get coins
    coins = await get_coins(user_id, guild_id)
    
    # Get inventory counts
    badges = await get_inventory_items(guild_id, int(user_id), "badge")
    collars = await get_inventory_items(guild_id, int(user_id), "collar")
    interfaces = await get_inventory_items(guild_id, int(user_id), "interface")
    total_items = len(badges) + len(collars) + len(interfaces)
    
    # Calculate event participation rate
    event_participation_rate = 0
    if guild:
        try:
            member = guild.get_member(int(user_id))
            if member:
                days_since_join = (datetime.datetime.now(datetime.UTC) - member.joined_at.replace(tzinfo=datetime.UTC)).days
                estimated_events = max(1, days_since_join * 7)
                event_participation_rate = (event_participations / estimated_events) * 100 if estimated_events > 0 else 0
        except:
            pass
    
    # Priority order: Lurker > Follower > Collector > Rich > Chatty > Voice Chatter
    if messages_sent < 20 and vc_minutes < 30:
        quotes = [
            "So quiet… but you're still here <:Islaseductive:1451296572255109210>",
            "You haven't said much—but you haven't left either <:Islaseductive:1451296572255109210>",
            "Silence doesn't mean absence. It just means patience <:Islaseductive:1451296572255109210>"
        ]
        return random.choice(quotes)
    
    if event_participation_rate >= 95:
        quotes = [
            "You don't miss much. That kind of consistency stands out <:Islaseductive:1451297729417445560>",
            "You keep showing up. I reward patterns like that <a:A_yum:1450190542771191859>",
            "You follow every little command. Good dog <a:A_yum:1450190542771191859>"
        ]
        return random.choice(quotes)
    
    if total_items > 10:
        quotes = [
            "You like keeping things I give you <:Islaseductive:1451296572255109210>",
            "Such a careful collector. Nothing goes to waste with you <:Islaseductive:1451297729417445560>",
            "You've gathered quite a collection. That says a lot <:Islaseductive:1451297729417445560>"
        ]
        return random.choice(quotes)
    
    if coins > 50000:
        quotes = [
            "All those coins… you clearly know how to play <:Islaseductive:1451297729417445560>",
            "Wealth suits you. Or maybe you suit it <:Islaseductive:1451297729417445560>",
            "You're sitting on quite a pile. I wonder what you're saving it for <:Islaseductive:1451296572255109210>"
        ]
        return random.choice(quotes)
    
    text_points = messages_sent
    voice_points = vc_minutes / 3
    if text_points > voice_points:
        quotes = [
            "You talk a lot… I notice everything you say <:Islaseductive:1451296572255109210>",
            "So eager to be heard. Careful — attention is something I decide <:Islaconfident:1451296510481273065>",
            "All those messages… you really like filling the space around me <:Islahappy:1451296142477361327>",
            "You don't stay quiet for long, do you? Interesting <a:A_yum:1450190542771191859>"
        ]
        return random.choice(quotes)
    
    if voice_points > text_points:
        quotes = [
            "I see you prefer being heard instead of seen <:mouth:1449996812093231206>",
            "So much time talking… I wonder who you're trying to impress <:Islaconfidentlaugh:1451296233636368515>",
            "You linger in VC like you're waiting for something. Are you waiting for me? <:Islalips:1451296607760023652>"
        ]
        return random.choice(quotes)
    
    return "Keep working hard for me ~"

async def get_lce(guild_id: int, user_id: int) -> int:
    """Get Lifetime Coins Earned"""
    row = await fetchone(
        "SELECT coins_lifetime_earned FROM economy_balance WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    return row["coins_lifetime_earned"] if row else 0

async def get_rank(guild_id: int, user_id: int) -> dict:
    """Get rank information: coin_rank, eligible_rank, held_rank (from cache), readiness_pct, blocker"""
    from systems.progression import RANK_LADDER, compute_readiness_pct, compute_blocker
    
    # Get rank from cache (includes held_rank_idx)
    cache_row = await fetchone(
        """SELECT coin_rank, eligible_rank, final_rank, held_rank_idx, at_risk, at_risk_since,
                  readiness_pct, blocker_text FROM rank_cache 
           WHERE guild_id = ? AND user_id = ?""",
        (guild_id, user_id)
    )
    
    if cache_row:
        # Use cached data
        rank_names = [r["name"] for r in RANK_LADDER]
        held_rank_idx = cache_row.get("held_rank_idx") or 0
        held_rank = rank_names[held_rank_idx] if held_rank_idx < len(rank_names) else rank_names[0]
        
        # Find next rank
        next_idx = min(held_rank_idx + 1, len(rank_names) - 1)
        next_rank = rank_names[next_idx] if next_idx > held_rank_idx else held_rank
        
        return {
            "coin_rank": cache_row["coin_rank"],
            "eligible_rank": cache_row["eligible_rank"],
            "final_rank": cache_row["final_rank"],
            "held_rank": held_rank,
            "held_rank_idx": held_rank_idx,
            "at_risk": cache_row.get("at_risk", 0),
            "rank": held_rank,  # Display held_rank as the user's current rank
            "rank_prefix": held_rank,  # Prefix for formatting
            "next_rank": next_rank,
            "readiness_pct": cache_row.get("readiness_pct", 0) or 0,
            "blocker_text": cache_row.get("blocker_text", "🔓 Ready") or "🔓 Ready"
        }
    
    # Cache miss - compute and return (shouldn't happen often, but handle gracefully)
    from systems.progression import compute_final_rank
    lce = await get_lce(guild_id, user_id)
    rank_info = await compute_final_rank(guild_id, user_id, lce)
    
    rank_names = [r["name"] for r in RANK_LADDER]
    current_idx = rank_names.index(rank_info["final_rank"]) if rank_info["final_rank"] in rank_names else 0
    next_idx = min(current_idx + 1, len(rank_names) - 1)
    next_rank = rank_names[next_idx] if next_idx > current_idx else rank_info["final_rank"]
    
    readiness_pct = await compute_readiness_pct(guild_id, user_id, next_rank)
    blocker_text = await compute_blocker(guild_id, user_id, next_rank)
    
    return {
        "coin_rank": rank_info["coin_rank"],
        "eligible_rank": rank_info["eligible_rank"],
        "final_rank": rank_info["final_rank"],
        "held_rank": rank_info["final_rank"],  # Fallback to final_rank
        "held_rank_idx": current_idx,
        "at_risk": 0,
        "rank": rank_info["final_rank"],
        "rank_prefix": rank_info["final_rank"],
        "next_rank": next_rank,
        "readiness_pct": readiness_pct,
        "blocker_text": blocker_text
    }

async def get_obedience_14d(guild_id: int, user_id: int) -> dict:
    """Get Obedience14 stats: obedience_pct, streak_days, done/late/fail counts"""
    from systems.progression import compute_obedience14
    return await compute_obedience14(guild_id, user_id)

async def get_profile_stats(guild_id, user_id):
    """Get comprehensive profile stats for a user (V3 progression system)"""
    guild_id = int(guild_id)
    user_id = int(user_id)
    
    # Get economy balance
    economy = await fetchone(
        "SELECT coins_balance, coins_lifetime_earned, coins_lifetime_burned FROM economy_balance WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    
    coins_balance = economy["coins_balance"] if economy else 0
    coins_lifetime = economy["coins_lifetime_earned"] if economy else 0
    
    # Get discipline state
    discipline = await fetchone(
        "SELECT debt, inactive_days, last_taxed_at FROM discipline_state WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    debt = discipline["debt"] if discipline else 0
    inactive_days = discipline["inactive_days"] if discipline else 0
    last_taxed_at = discipline["last_taxed_at"] if discipline else None
    
    # Get 7-day activity (using new field name messages_count)
    activity = await get_activity_7d(guild_id, user_id)
    
    # Get WAS
    from systems.progression import compute_was
    was = await compute_was(guild_id, user_id)
    
    # Get Obedience14
    obedience = await get_obedience_14d(guild_id, user_id)
    
    # Get rank info
    rank_info = await get_rank(guild_id, user_id)
    
    # Get activity tier label
    total_activity = activity["messages"] + (activity["vc_minutes"] // 10)
    if total_activity < 50:
        activity_tier = "Low"
    elif total_activity < 200:
        activity_tier = "Medium"
    elif total_activity < 500:
        activity_tier = "High"
    else:
        activity_tier = "Obsessive"
    
    # Get inventory
    badges = await get_inventory_items(guild_id, user_id, "badge")
    collars = await get_inventory_items(guild_id, user_id, "collar")
    interfaces = await get_inventory_items(guild_id, user_id, "interface")
    equipped = await get_equipped_items(guild_id, user_id)
    
    # Calculate tax (placeholder - will be computed by tasks)
    tax = 0
    
    return {
        "rank": rank_info["final_rank"],
        "coin_rank": rank_info["coin_rank"],
        "eligible_rank": rank_info["eligible_rank"],
        "next_rank": rank_info["next_rank"],
        "readiness_pct": rank_info["readiness_pct"],
        "blocker_text": rank_info["blocker_text"],
        "coins": coins_balance,
        "lifetime": coins_lifetime,
        "tax": tax,
        "debt": debt,
        "inactive_days": inactive_days,
        "obedience_pct": obedience["obedience_pct"],
        "obedience_streak": obedience["streak_days"],
        "orders_done": obedience["done"],
        "orders_late": obedience["late"],
        "orders_failed": obedience["failed"],
        "messages_sent": activity["messages"],
        "vc_minutes": activity["vc_minutes"],
        "event_participations": activity["events"],
        "was": was,
        "activity_tier": activity_tier,
        "badges_owned": [item["item_id"] for item in badges],
        "collars_owned": [item["item_id"] for item in collars],
        "interfaces_owned": [item["item_id"] for item in interfaces],
        "equipped_collar": equipped["equipped_collar"],
        "equipped_badge": equipped["equipped_badge"],
    }

# Daily/Give cooldowns (resets at 6pm UK daily) - kept in memory for now
daily_cooldowns = {}
give_cooldowns = {}

def get_uk_6pm_timestamp():
    """Get next 6pm UK time as Unix timestamp."""
    uk_tz = datetime.timezone(datetime.timedelta(hours=0))
    now = datetime.datetime.now(uk_tz)
    target_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
    if now.hour >= 18:
        target_time += datetime.timedelta(days=1)
    return int(target_time.timestamp())

def check_daily_cooldown(user_id):
    """Check if user can claim daily. Returns (on_cooldown, reset_timestamp)."""
    reset_timestamp = get_uk_6pm_timestamp()
    
    if user_id not in daily_cooldowns:
        return False, reset_timestamp
    
    last_claim = daily_cooldowns[user_id]
    now = datetime.datetime.now(datetime.UTC)
    
    uk_tz = datetime.timezone(datetime.timedelta(hours=0))
    uk_now = datetime.datetime.now(uk_tz)
    
    last_claim_utc = last_claim.replace(tzinfo=datetime.timezone.utc)
    uk_last_claim = last_claim_utc.astimezone(uk_tz)
    
    def get_reset_day(dt):
        """Get the reset day for a datetime. Day resets at 6pm."""
        if dt.hour < 18:
            return (dt - datetime.timedelta(days=1)).date()
        else:
            return dt.date()
    
    last_reset_day = get_reset_day(uk_last_claim)
    current_reset_day = get_reset_day(uk_now)
    
    if current_reset_day > last_reset_day:
        return False, reset_timestamp
    
    return True, reset_timestamp

def update_daily_cooldown(user_id):
    """Update daily cooldown for user."""
    daily_cooldowns[user_id] = datetime.datetime.now(datetime.UTC)

def check_give_cooldown(user_id):
    """Check if user can use give command. Returns (on_cooldown, reset_timestamp)."""
    reset_timestamp = get_uk_6pm_timestamp()
    if user_id not in give_cooldowns:
        return False, reset_timestamp
    last_give = give_cooldowns[user_id]
    now = datetime.datetime.now(datetime.UTC)
    if now >= last_give + datetime.timedelta(days=1):
        uk_tz = datetime.timezone(datetime.timedelta(hours=0))
        uk_now = datetime.datetime.now(uk_tz)
        if uk_now.hour >= 18:
            return False, reset_timestamp
    return True, reset_timestamp

def update_give_cooldown(user_id):
    """Update give cooldown for user."""
    give_cooldowns[user_id] = datetime.datetime.now(datetime.UTC)

# Backward compatibility: synchronous wrappers that use asyncio
import asyncio
import functools

def _sync_wrapper(async_func):
    """Wrap async function to be callable synchronously"""
    @functools.wraps(async_func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we can't use run_until_complete
                # Create a task instead (but this won't wait for result)
                return asyncio.create_task(async_func(*args, **kwargs))
            else:
                return loop.run_until_complete(async_func(*args, **kwargs))
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(async_func(*args, **kwargs))
    return wrapper

# Export synchronous wrappers for backward compatibility (non-async callers)
_get_xp_sync = _sync_wrapper(get_xp)
_get_level_sync = _sync_wrapper(get_level)
_get_coins_sync = _sync_wrapper(get_coins)

# Keep legacy sync functions for now (they'll be updated gradually)
def get_xp_sync(user_id):
    """Synchronous wrapper - use get_xp() in async contexts"""
    return _get_xp_sync(user_id)

def get_level_sync(user_id):
    """Synchronous wrapper - use get_level() in async contexts"""
    return _get_level_sync(user_id)

def get_coins_sync(user_id):
    """Synchronous wrapper - use get_coins() in async contexts"""
    return _get_coins_sync(user_id)

# Order lifecycle functions
async def order_accept(guild_id: int, user_id: int, order_id: int, due_seconds: int, order_key: str = None, progress_json: str = None) -> int:
    """Accept an order, create a run, return run_id"""
    accepted_at = _now_iso()
    due_at_dt = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=due_seconds)
    due_at = due_at_dt.isoformat()
    
    # Store baseline VC minutes if needed for verification
    if progress_json is None:
        # Get current VC minutes baseline
        from core.db import get_activity_7d
        activity = await get_activity_7d(guild_id, user_id)
        vc_baseline = activity.get("vc_minutes", 0)
        import json
        progress_json = json.dumps({"vc_minutes_baseline": vc_baseline})
    
    await execute(
        """INSERT INTO order_runs (guild_id, user_id, order_id, order_key, accepted_at, due_at, status, progress_json)
           VALUES (?, ?, ?, ?, ?, ?, 'accepted', ?)""",
        (guild_id, user_id, order_id, order_key, accepted_at, due_at, progress_json)
    )
    
    # Get the run_id
    row = await fetchone(
        "SELECT run_id FROM order_runs WHERE guild_id = ? AND user_id = ? AND order_id = ? AND accepted_at = ? ORDER BY run_id DESC LIMIT 1",
        (guild_id, user_id, order_id, accepted_at)
    )
    return row["run_id"] if row else 0

async def order_complete(guild_id: int, user_id: int, run_id: int, late: bool = False):
    """Mark an order run as completed and record outcome"""
    completed_at = _now_iso()
    
    # Get order info for reward
    run = await fetchone(
        "SELECT order_id, due_at FROM order_runs WHERE run_id = ? AND guild_id = ? AND user_id = ?",
        (run_id, guild_id, user_id)
    )
    
    if not run:
        return False
    
    # Check if actually late
    due_at = datetime.datetime.fromisoformat(run["due_at"].replace('Z', '+00:00'))
    is_late = datetime.datetime.now(datetime.UTC) > due_at or late
    
    await execute(
        """UPDATE order_runs SET status = 'completed', completed_at = ?, completed_late = ?
           WHERE run_id = ? AND guild_id = ? AND user_id = ?""",
        (completed_at, 1 if is_late else 0, run_id, guild_id, user_id)
    )
    
    # Award coins if order exists
    order = await fetchone(
        "SELECT reward_coins FROM orders WHERE order_id = ?",
        (run["order_id"],)
    )
    
    if order:
        reward = order["reward_coins"]
        if reward > 0:
            await add_coins(user_id, reward, guild_id=guild_id, reason="order_completed", meta={"run_id": run_id, "order_id": run["order_id"]})
    
    # Record outcome in order_outcomes_daily
    from core.db import _today_str
    today = _today_str()
    outcome_type = "late" if is_late else "completed"
    if is_late:
        await execute(
            """INSERT INTO order_outcomes_daily (guild_id, user_id, day, late_count)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(guild_id, user_id, day) DO UPDATE SET late_count = late_count + 1""",
            (guild_id, user_id, today)
        )
    else:
        await execute(
            """INSERT INTO order_outcomes_daily (guild_id, user_id, day, done_count)
               VALUES (?, ?, ?, 1)
               ON CONFLICT(guild_id, user_id, day) DO UPDATE SET done_count = done_count + 1""",
            (guild_id, user_id, today)
        )
    
    # Update order streak and check for bonus
    from core.db import update_order_streak
    new_streak, bonus_awarded = await update_order_streak(guild_id, user_id, outcome_type)
    
    # Award streak bonus if applicable
    bonus_amount = 0
    if bonus_awarded:
        bonus_amount = 25
        await add_coins(user_id, bonus_amount, guild_id=guild_id, reason="order_streak_bonus", meta={"run_id": run_id, "streak_reached": 3})
    
    return {"success": True, "bonus_awarded": bonus_awarded, "streak_bonus": bonus_amount}

async def order_fail(guild_id: int, user_id: int, run_id: int):
    """Mark an order run as failed and record outcome"""
    await execute(
        """UPDATE order_runs SET status = 'failed' WHERE run_id = ? AND guild_id = ? AND user_id = ?""",
        (run_id, guild_id, user_id)
    )
    
    # Record failed outcome in order_outcomes_daily
    from core.db import _today_str
    today = _today_str()
    await execute(
        """INSERT INTO order_outcomes_daily (guild_id, user_id, day, failed_count)
           VALUES (?, ?, ?, 1)
           ON CONFLICT(guild_id, user_id, day) DO UPDATE SET failed_count = failed_count + 1""",
        (guild_id, user_id, today)
    )
    
    # Update order streak (reset on failure)
    from core.db import update_order_streak
    await update_order_streak(guild_id, user_id, "failed")
    
    return True

async def order_forfeit(guild_id: int, user_id: int, run_id: int):
    """Mark an order run as forfeited (same as failed for progression)"""
    await order_fail(guild_id, user_id, run_id)

# Debt and tax functions
async def get_debt(guild_id: int, user_id: int) -> int:
    """Get user's debt"""
    row = await fetchone(
        "SELECT debt FROM discipline_state WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    return row["debt"] if row else 0

async def update_debt(guild_id: int, user_id: int, debt_delta: int):
    """Update user's debt"""
    now = _now_iso()
    
    existing = await fetchone(
        "SELECT debt FROM discipline_state WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    
    new_debt = max(0, (existing["debt"] if existing else 0) + debt_delta)
    
    await execute(
        """INSERT OR REPLACE INTO discipline_state (guild_id, user_id, debt, updated_at)
           VALUES (?, ?, ?, ?)""",
        (guild_id, user_id, new_debt, now)
    )
    return new_debt

# Bank API - Unified economy functions
async def get_account(guild_id: int, user_id: int) -> dict:
    """
    Get user's bank account information.
    Returns: {bal, lce, tax_paid_total, debt, loan_active, loan_principal, loan_issued_ts, loan_due_ts}
    """
    # Get balance and LCE
    balance_row = await fetchone(
        "SELECT coins_balance, coins_lifetime_earned FROM economy_balance WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    bal = balance_row["coins_balance"] if balance_row else 0
    lce = balance_row["coins_lifetime_earned"] if balance_row else 0
    
    # Get debt
    debt_row = await fetchone(
        "SELECT debt FROM discipline_state WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    debt = debt_row["debt"] if debt_row else 0
    
    # Get loan status
    from core.db import get_loan_status
    loan = await get_loan_status(guild_id, user_id)
    loan_active = 1 if loan else 0
    loan_principal = loan["remaining_principal"] if loan else 0
    loan_issued_ts = loan["issued_at"] if loan else None
    loan_due_ts = loan["due_at"] if loan else None
    
    # Get tax_paid_total (sum of tax entries from ledger)
    tax_row = await fetchone(
        """SELECT SUM(amount) as total FROM economy_ledger 
           WHERE guild_id = ? AND user_id = ? AND type LIKE '%tax%'""",
        (guild_id, user_id)
    )
    tax_paid_total = abs(tax_row["total"]) if tax_row and tax_row["total"] else 0
    
    return {
        "bal": bal,
        "lce": lce,
        "tax_paid_total": tax_paid_total,
        "debt": debt,
        "loan_active": loan_active,
        "loan_principal": loan_principal,
        "loan_issued_ts": loan_issued_ts,
        "loan_due_ts": loan_due_ts
    }

async def deposit_earned(guild_id: int, user_id: int, amount: int, reason: str = "earned", meta: dict = None):
    """Deposit earned coins (adds to balance and LCE, logs to ledger)"""
    await add_coins(user_id, amount, guild_id=guild_id, reason=reason, meta=meta)

async def withdraw(guild_id: int, user_id: int, amount: int, reason: str = "withdrawal", meta: dict = None):
    """Withdraw coins (subtracts from balance, logs to ledger)"""
    await add_coins(user_id, -amount, guild_id=guild_id, reason=reason, meta=meta)

async def transfer(guild_id: int, from_user_id: int, to_user_id: int, amount: int, reason: str = "transfer", meta: dict = None):
    """Transfer coins between users"""
    # Withdraw from sender
    await withdraw(guild_id, from_user_id, amount, reason=f"{reason}_from", meta=meta)
    # Deposit to receiver
    await deposit_earned(guild_id, to_user_id, amount, reason=f"{reason}_to", meta=meta)

async def apply_tax(guild_id: int, user_id: int, tax_amount: int, reason: str = "tax"):
    """Apply tax (subtracts from balance, logs to ledger with tax type)"""
    await add_coins(user_id, -tax_amount, guild_id=guild_id, reason=reason, meta={"tax_amount": tax_amount})

async def pay_debt(guild_id: int, user_id: int, amount: int):
    """Pay off debt (subtracts from balance and debt, logs to ledger)"""
    # Check if user has enough balance
    current_balance = await get_coins(user_id, guild_id=guild_id)
    if current_balance < amount:
        return False
    
    # Withdraw from balance
    await withdraw(guild_id, user_id, amount, reason="debt_payment", meta={"debt_payment": amount})
    
    # Reduce debt
    await update_debt(guild_id, user_id, -amount)
    
    return True

async def add_debt(guild_id: int, user_id: int, amount: int, reason: str = "debt"):
    """Add to debt (logs to ledger)"""
    new_debt = await update_debt(guild_id, user_id, amount)
    
    # Log to ledger
    now = _now_iso()
    await execute(
        "INSERT INTO economy_ledger (guild_id, user_id, ts, type, amount, meta_json) VALUES (?, ?, ?, ?, ?, ?)",
        (guild_id, user_id, now, reason, amount, json.dumps({"debt_after": new_debt}))
    )
    
    return new_debt

# Loan API functions (wrappers around db functions)
async def issue_loan(guild_id: int, user_id: int, principal: int, due_at: str):
    """Issue a new loan to a user"""
    from core.db import issue_loan as _issue_loan
    await _issue_loan(guild_id, user_id, principal, due_at)

async def pay_loan(guild_id: int, user_id: int, amount: int):
    """Pay off part of a loan (subtracts from balance and loan, logs to ledger)"""
    from core.db import pay_loan as _pay_loan, get_loan_status
    
    # Check if user has enough balance
    current_balance = await get_coins(user_id, guild_id=guild_id)
    if current_balance < amount:
        return False
    
    # Pay the loan
    success = await _pay_loan(guild_id, user_id, amount)
    if not success:
        return False
    
    # Withdraw from balance
    await withdraw(guild_id, user_id, amount, reason="loan_payment", meta={"loan_payment": amount})
    
    return True

async def convert_overdue_loans():
    """Convert overdue loans to debt (called from scheduled tasks)"""
    from core.db import convert_overdue_loans as _convert_overdue_loans
    return await _convert_overdue_loans()

# Activity recording functions (wrappers for clarity)
async def record_message(guild_id: int, user_id: int):
    """Record a message (increments activity_daily.messages)"""
    await bump_message(guild_id, user_id)

async def record_vc_minutes(guild_id: int, user_id: int, minutes: int):
    """Record VC minutes"""
    await add_vc_minutes(guild_id, user_id, minutes)

async def record_event_participation(guild_id: int, user_id: int):
    """Record event participation"""
    await bump_event(guild_id, user_id)
