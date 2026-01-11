"""
SQLite database management for IslaBot V2
"""
import aiosqlite
import datetime
import json
import os

# Database connection
_db = None
# Use absolute path relative to repo root (fixes Wispbyte deployment issues)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_db_path = os.path.join(_REPO_ROOT, "data", "isla_bot.db")

async def init_db():
    """Initialize database and create tables if they don't exist"""
    global _db
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)
    
    _db = await aiosqlite.connect(_db_path)
    _db.row_factory = aiosqlite.Row
    
    # Create tables
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            coins INTEGER DEFAULT 0,
            times_gambled INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    # Migration: Drop xp/level columns if they exist (V3 migration)
    try:
        await _db.execute("ALTER TABLE user_profile DROP COLUMN xp")
    except Exception:
        pass  # Column doesn't exist
    try:
        await _db.execute("ALTER TABLE user_profile DROP COLUMN level")
    except Exception:
        pass  # Column doesn't exist
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS activity_daily (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            messages_count INTEGER DEFAULT 0,
            vc_minutes INTEGER DEFAULT 0,
            reactions_count INTEGER DEFAULT 0,
            commands_used_count INTEGER DEFAULT 0,
            events INTEGER DEFAULT 0,
            presence_ticks INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id, day)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS economy_balance (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            coins_balance INTEGER DEFAULT 0,
            coins_lifetime_earned INTEGER DEFAULT 0,
            coins_lifetime_burned INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS economy_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            meta_json TEXT
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS discipline_state (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            debt INTEGER DEFAULT 0,
            inactive_days INTEGER DEFAULT 0,
            last_qualifying_activity_at TEXT,
            last_taxed_at TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS inventory_items (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            item_id TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id, item_type, item_id)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS inventory_equipped (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            equipped_collar TEXT,
            equipped_badge TEXT,
            equipped_interface TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    # V3 Progression System Tables
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            reward_coins INTEGER DEFAULT 0,
            due_seconds INTEGER DEFAULT 604800,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS order_runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            order_id INTEGER NOT NULL,
            order_key TEXT,
            accepted_at TEXT NOT NULL,
            due_at TEXT NOT NULL,
            completed_at TEXT,
            status TEXT NOT NULL DEFAULT 'accepted',
            completed_late INTEGER DEFAULT 0,
            progress_json TEXT,
            meta_json TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        )
    """)
    
    # Short-term event tables (for order verification)
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS message_events (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            ts INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            is_reply INTEGER DEFAULT 0,
            replied_to_user_is_bot INTEGER DEFAULT 0
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS reaction_events (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            ts INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            emoji TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            is_forum INTEGER DEFAULT 0
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS command_events (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            ts INTEGER NOT NULL,
            command_name TEXT NOT NULL,
            channel_id INTEGER NOT NULL
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS voice_sessions (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            join_ts INTEGER NOT NULL,
            leave_ts INTEGER,
            minutes INTEGER DEFAULT 0
        )
    """)
    
    # Order outcomes daily aggregation
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS order_outcomes_daily (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            done_count INTEGER DEFAULT 0,
            late_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, day)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS rank_cache (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            coin_rank TEXT,
            eligible_rank TEXT,
            final_rank TEXT,
            held_rank_idx INTEGER DEFAULT 0,
            at_risk INTEGER DEFAULT 0,
            at_risk_since TEXT,
            readiness_pct INTEGER DEFAULT 0,
            blocker_text TEXT,
            computed_at TEXT NOT NULL,
            failed_weeks_count INTEGER DEFAULT 0,
            last_promotion_at TEXT,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS weekly_claims (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            last_claimed_at TEXT,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS vault (
            guild_id INTEGER PRIMARY KEY,
            coins_vault INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS loans (
            loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            principal INTEGER NOT NULL,
            remaining_principal INTEGER NOT NULL,
            issued_at TEXT NOT NULL,
            due_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            converted_to_debt_at TEXT
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS roles_config (
            guild_id INTEGER NOT NULL,
            message_type TEXT NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, message_type)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS preference_roles (
            guild_id INTEGER NOT NULL,
            preference_value TEXT NOT NULL,
            role_id INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, preference_value)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS introductions_config (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS introduction_replies (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            last_replied_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS gift_claims (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            claimed_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    # New tables for interactive features
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS order_user_state (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            order_key TEXT NOT NULL,
            postponed_until INTEGER,
            declined_until INTEGER,
            PRIMARY KEY (guild_id, user_id, order_key)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS user_notifications (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            enabled INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS orders_announcement_config (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS promo_rotation_state (
            guild_id INTEGER PRIMARY KEY,
            rotation_index INTEGER DEFAULT 0,
            last_run_day TEXT,
            updated_at TEXT NOT NULL
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS casino_channel_config (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS announcements_channel_config (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS order_streaks (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            streak_count INTEGER DEFAULT 0,
            last_outcome TEXT,
            last_completed_at TEXT,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS order_reminders (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            run_id INTEGER NOT NULL,
            reminder_sent_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id, run_id)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS keyword_ping_cooldowns (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            last_used_at INTEGER NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS reaction_bonus_claims (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            claimed_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id, day)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS first_message_bonus (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            claimed_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id, day)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS order_challenges (
            challenge_id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            challenger_id INTEGER NOT NULL,
            target_id INTEGER NOT NULL,
            order_key TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            winner_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS vc_overlap_sessions (
            guild_id INTEGER NOT NULL,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            start_ts INTEGER NOT NULL,
            end_ts INTEGER,
            duration_minutes INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user1_id, user2_id, channel_id, start_ts)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS buddy_boost_claims (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            claimed_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id, day)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS micro_interactions_opt_in (
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            enabled INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
    # Create indexes
    await _db.execute("""
        CREATE INDEX IF NOT EXISTS idx_economy_ledger_lookup 
        ON economy_ledger(guild_id, user_id, ts)
    """)
    
    await _db.execute("""
        CREATE INDEX IF NOT EXISTS idx_activity_daily_lookup 
        ON activity_daily(guild_id, user_id, day)
    """)
    
    await _db.execute("""
        CREATE INDEX IF NOT EXISTS idx_order_runs_lookup 
        ON order_runs(guild_id, user_id, accepted_at)
    """)
    
    # Indexes for event tables
    await _db.execute("""
        CREATE INDEX IF NOT EXISTS idx_message_events_user_ts 
        ON message_events(guild_id, user_id, ts)
    """)
    
    await _db.execute("""
        CREATE INDEX IF NOT EXISTS idx_message_events_channel_ts 
        ON message_events(guild_id, channel_id, ts)
    """)
    
    await _db.execute("""
        CREATE INDEX IF NOT EXISTS idx_reaction_events_user_ts 
        ON reaction_events(guild_id, user_id, ts)
    """)
    
    await _db.execute("""
        CREATE INDEX IF NOT EXISTS idx_reaction_events_channel_ts 
        ON reaction_events(guild_id, channel_id, ts)
    """)
    
    await _db.execute("""
        CREATE INDEX IF NOT EXISTS idx_reaction_events_channel_emoji_ts 
        ON reaction_events(guild_id, channel_id, emoji, ts)
    """)
    
    await _db.execute("""
        CREATE INDEX IF NOT EXISTS idx_command_events_user_ts 
        ON command_events(guild_id, user_id, ts)
    """)
    
    await _db.execute("""
        CREATE INDEX IF NOT EXISTS idx_command_events_command_ts 
        ON command_events(guild_id, command_name, ts)
    """)
    
    # Enable WAL mode for better concurrent performance
    await _db.execute("PRAGMA journal_mode=WAL")
    
    await _db.commit()
    print(f"[+] Database initialized at {_db_path}")

def get_db_path():
    """Get the database path (for diagnostics)"""
    return _db_path

async def close_db():
    """Close database connection"""
    global _db
    if _db:
        await _db.close()
        _db = None
        print("[+] Database connection closed")

async def execute(query: str, params: tuple = ()):
    """Execute a write query"""
    if not _db:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    await _db.execute(query, params)
    await _db.commit()

async def executemany(query: str, params_list: list):
    """Execute a write query multiple times"""
    if not _db:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    await _db.executemany(query, params_list)
    await _db.commit()

async def fetchone(query: str, params: tuple = ()):
    """Fetch one row"""
    if not _db:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _db.execute(query, params) as cursor:
        return await cursor.fetchone()

async def fetchall(query: str, params: tuple = ()):
    """Fetch all rows"""
    if not _db:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _db.execute(query, params) as cursor:
        return await cursor.fetchall()

def _now_iso():
    """Get current UTC time as ISO string"""
    return datetime.datetime.now(datetime.UTC).isoformat()

def _today_str():
    """Get today's date as YYYY-MM-DD string"""
    return datetime.datetime.now(datetime.UTC).date().isoformat()

async def upsert_user_profile(guild_id: int, user_id: int, coins: int = None, 
                               times_gambled: int = None, total_wins: int = None, total_spent: int = None):
    """Upsert user profile (V3: XP/Level removed)"""
    now = _now_iso()
    
    # Get existing values if not provided
    existing = await fetchone(
        "SELECT coins, times_gambled, total_wins, total_spent FROM user_profile WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    
    if existing:
        coins = coins if coins is not None else existing["coins"]
        times_gambled = times_gambled if times_gambled is not None else existing["times_gambled"]
        total_wins = total_wins if total_wins is not None else existing["total_wins"]
        total_spent = total_spent if total_spent is not None else existing["total_spent"]
        
        await execute(
            """UPDATE user_profile SET coins = ?, times_gambled = ?, total_wins = ?, total_spent = ?, updated_at = ?
               WHERE guild_id = ? AND user_id = ?""",
            (coins, times_gambled, total_wins, total_spent, now, guild_id, user_id)
        )
    else:
        coins = coins or 0
        times_gambled = times_gambled or 0
        total_wins = total_wins or 0
        total_spent = total_spent or 0
        
        await execute(
            """INSERT INTO user_profile (guild_id, user_id, coins, times_gambled, total_wins, total_spent, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (guild_id, user_id, coins, times_gambled, total_wins, total_spent, now)
        )

async def bump_message(guild_id: int, user_id: int):
    """Increment daily message count"""
    day = _today_str()
    now = _now_iso()
    
    await execute(
        """INSERT INTO activity_daily (guild_id, user_id, day, messages_count, vc_minutes, events, presence_ticks, updated_at)
           VALUES (?, ?, ?, 1, 0, 0, 0, ?)
           ON CONFLICT(guild_id, user_id, day) DO UPDATE SET messages_count = messages_count + 1, updated_at = ?""",
        (guild_id, user_id, day, now, now)
    )

async def add_vc_minutes(guild_id: int, user_id: int, minutes: int):
    """Add VC minutes to daily activity"""
    day = _today_str()
    now = _now_iso()
    
    await execute(
        """INSERT INTO activity_daily (guild_id, user_id, day, messages_count, vc_minutes, events, presence_ticks, updated_at)
           VALUES (?, ?, ?, 0, ?, 0, 0, ?)
           ON CONFLICT(guild_id, user_id, day) DO UPDATE SET vc_minutes = vc_minutes + ?, updated_at = ?""",
        (guild_id, user_id, day, minutes, now, minutes, now)
    )

async def bump_event(guild_id: int, user_id: int):
    """Increment daily event count"""
    day = _today_str()
    now = _now_iso()
    
    await execute(
        """INSERT INTO activity_daily (guild_id, user_id, day, messages_count, vc_minutes, events, presence_ticks, updated_at)
           VALUES (?, ?, ?, 0, 0, 1, 0, ?)
           ON CONFLICT(guild_id, user_id, day) DO UPDATE SET events = events + 1, updated_at = ?""",
        (guild_id, user_id, day, now, now)
    )

async def upsert_economy_balance(guild_id: int, user_id: int, coins_delta: int = 0):
    """Update economy balance and lifetime tracking"""
    now = _now_iso()
    
    existing = await fetchone(
        "SELECT coins_balance, coins_lifetime_earned, coins_lifetime_burned FROM economy_balance WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    
    if existing:
        new_balance = existing["coins_balance"] + coins_delta
        new_balance = max(0, new_balance)  # Prevent negative
        
        lifetime_earned = existing["coins_lifetime_earned"]
        lifetime_burned = existing["coins_lifetime_burned"]
        
        if coins_delta > 0:
            lifetime_earned += coins_delta
        elif coins_delta < 0:
            lifetime_burned += abs(coins_delta)
        
        await execute(
            """UPDATE economy_balance SET coins_balance = ?, coins_lifetime_earned = ?, coins_lifetime_burned = ?, updated_at = ?
               WHERE guild_id = ? AND user_id = ?""",
            (new_balance, lifetime_earned, lifetime_burned, now, guild_id, user_id)
        )
        return new_balance
    else:
        new_balance = max(0, coins_delta)
        lifetime_earned = max(0, coins_delta)
        lifetime_burned = 0 if coins_delta >= 0 else abs(coins_delta)
        
        await execute(
            """INSERT INTO economy_balance (guild_id, user_id, coins_balance, coins_lifetime_earned, coins_lifetime_burned, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (guild_id, user_id, new_balance, lifetime_earned, lifetime_burned, now)
        )
        return new_balance

async def get_activity_7d(guild_id: int, user_id: int):
    """Get activity stats for last 7 days"""
    seven_days_ago = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7)).date().isoformat()
    
    rows = await fetchall(
        """SELECT SUM(messages_count) as messages, SUM(vc_minutes) as vc_minutes, SUM(events) as events
           FROM activity_daily WHERE guild_id = ? AND user_id = ? AND day >= ?""",
        (guild_id, user_id, seven_days_ago)
    )
    
    if rows and rows[0][0] is not None:
        return {
            "messages": rows[0]["messages"] or 0,
            "vc_minutes": rows[0]["vc_minutes"] or 0,
            "events": rows[0]["events"] or 0
        }
    return {"messages": 0, "vc_minutes": 0, "events": 0}

async def get_inventory_items(guild_id: int, user_id: int, item_type: str = None):
    """Get inventory items, optionally filtered by type"""
    if item_type:
        rows = await fetchall(
            "SELECT item_id FROM inventory_items WHERE guild_id = ? AND user_id = ? AND item_type = ?",
            (guild_id, user_id, item_type)
        )
    else:
        rows = await fetchall(
            "SELECT item_type, item_id FROM inventory_items WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
    
    return [dict(row) for row in rows]

async def get_equipped_items(guild_id: int, user_id: int):
    """Get equipped items"""
    row = await fetchone(
        "SELECT equipped_collar, equipped_badge, equipped_interface FROM inventory_equipped WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    
    if row:
        return {
            "equipped_collar": row["equipped_collar"],
            "equipped_badge": row["equipped_badge"],
            "equipped_interface": row["equipped_interface"]
        }
    return {"equipped_collar": None, "equipped_badge": None, "equipped_interface": None}

# Event recording functions (for order verification)
async def record_message_event(guild_id: int, user_id: int, channel_id: int, is_reply: bool = False, replied_to_user_is_bot: bool = False):
    """Record a message event (short-term, expires in 48h)"""
    ts = int(datetime.datetime.now(datetime.UTC).timestamp())
    await execute(
        """INSERT INTO message_events (guild_id, user_id, ts, channel_id, is_reply, replied_to_user_is_bot)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (guild_id, user_id, ts, channel_id, 1 if is_reply else 0, 1 if replied_to_user_is_bot else 0)
    )

async def record_reaction_event(guild_id: int, user_id: int, channel_id: int, emoji: str, message_id: int, is_forum: bool = False):
    """Record a reaction event (short-term, expires in 7d)"""
    ts = int(datetime.datetime.now(datetime.UTC).timestamp())
    # Normalize emoji (store as string)
    emoji_str = str(emoji) if emoji else ""
    await execute(
        """INSERT INTO reaction_events (guild_id, user_id, ts, channel_id, emoji, message_id, is_forum)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (guild_id, user_id, ts, channel_id, emoji_str, message_id, 1 if is_forum else 0)
    )

async def record_command_event(guild_id: int, user_id: int, command_name: str, channel_id: int):
    """Record a command event (short-term, expires in 7d)"""
    ts = int(datetime.datetime.now(datetime.UTC).timestamp())
    await execute(
        """INSERT INTO command_events (guild_id, user_id, ts, command_name, channel_id)
           VALUES (?, ?, ?, ?, ?)""",
        (guild_id, user_id, ts, command_name, channel_id)
    )

async def bump_reaction(guild_id: int, user_id: int):
    """Increment reaction count in activity_daily for today"""
    today = _today_str()
    now = _now_iso()
    await execute(
        """INSERT INTO activity_daily (guild_id, user_id, day, reactions_count, updated_at)
           VALUES (?, ?, ?, 1, ?)
           ON CONFLICT(guild_id, user_id, day) DO UPDATE SET
           reactions_count = reactions_count + 1, updated_at = ?""",
        (guild_id, user_id, today, now, now)
    )

async def bump_command(guild_id: int, user_id: int):
    """Increment command count in activity_daily for today"""
    today = _today_str()
    now = _now_iso()
    await execute(
        """INSERT INTO activity_daily (guild_id, user_id, day, commands_used_count, updated_at)
           VALUES (?, ?, ?, 1, ?)
           ON CONFLICT(guild_id, user_id, day) DO UPDATE SET
           commands_used_count = commands_used_count + 1, updated_at = ?""",
        (guild_id, user_id, today, now, now)
    )

# Cleanup functions for expired events
# Order streak helpers
async def get_order_streak(guild_id: int, user_id: int):
    """Get current order streak for a user"""
    row = await fetchone(
        "SELECT streak_count, last_outcome, last_completed_at FROM order_streaks WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    if row:
        return {
            "streak_count": row["streak_count"],
            "last_outcome": row["last_outcome"],
            "last_completed_at": row["last_completed_at"]
        }
    return {"streak_count": 0, "last_outcome": None, "last_completed_at": None}

async def update_order_streak(guild_id: int, user_id: int, outcome: str):
    """
    Update order streak based on outcome.
    outcome: "completed", "late", or "failed"
    Returns (new_streak_count, bonus_awarded)
    """
    streak_data = await get_order_streak(guild_id, user_id)
    current_streak = streak_data["streak_count"]
    last_outcome = streak_data["last_outcome"]
    now = _now_iso()
    
    bonus_awarded = False
    new_streak = 0
    
    if outcome == "completed" or outcome == "late":
        # Success - increment streak
        if last_outcome != "failed":
            new_streak = current_streak + 1
        else:
            # Reset after a fail
            new_streak = 1
        
        # Award bonus if streak reaches 3
        if new_streak == 3:
            bonus_awarded = True
            new_streak = 0  # Reset after bonus (per spec: reset-to-0)
    elif outcome == "failed":
        # Failure - reset streak
        new_streak = 0
    
    await execute(
        """INSERT OR REPLACE INTO order_streaks (guild_id, user_id, streak_count, last_outcome, last_completed_at)
           VALUES (?, ?, ?, ?, ?)""",
        (guild_id, user_id, new_streak, outcome, now if outcome != "failed" else streak_data["last_completed_at"])
    )
    
    return new_streak, bonus_awarded

# Promo rotation helpers
async def get_promo_rotation_state(guild_id: int):
    """Get promo rotation state for a guild"""
    row = await fetchone(
        "SELECT rotation_index, last_run_day FROM promo_rotation_state WHERE guild_id = ?",
        (guild_id,)
    )
    if row:
        return {
            "rotation_index": row["rotation_index"],
            "last_run_day": row["last_run_day"]
        }
    return {"rotation_index": 0, "last_run_day": None}

async def update_promo_rotation_state(guild_id: int, rotation_index: int, last_run_day: str):
    """Update promo rotation state for a guild"""
    now = _now_iso()
    await execute(
        """INSERT OR REPLACE INTO promo_rotation_state (guild_id, rotation_index, last_run_day, updated_at)
           VALUES (?, ?, ?, ?)""",
        (guild_id, rotation_index, last_run_day, now)
    )

async def get_announcements_channel_id(guild_id: int):
    """Get announcements channel ID for a guild (falls back to EVENT_CHANNEL_ID if not configured)"""
    from core.config import EVENT_CHANNEL_ID
    row = await fetchone(
        "SELECT channel_id FROM announcements_channel_config WHERE guild_id = ?",
        (guild_id,)
    )
    return row["channel_id"] if row else EVENT_CHANNEL_ID

async def get_casino_channel_id(guild_id: int):
    """Get casino channel ID for a guild (falls back to CASINO_CHANNEL_ID if not configured)"""
    from core.config import CASINO_CHANNEL_ID
    row = await fetchone(
        "SELECT channel_id FROM casino_channel_config WHERE guild_id = ?",
        (guild_id,)
    )
    return row["channel_id"] if row else CASINO_CHANNEL_ID

async def cleanup_expired_events():
    """Delete expired event data based on retention windows"""
    now_ts = int(datetime.datetime.now(datetime.UTC).timestamp())
    
    # Delete message_events older than 48 hours
    expire_48h = now_ts - (48 * 3600)
    await execute("DELETE FROM message_events WHERE ts < ?", (expire_48h,))
    
    # Delete reaction_events older than 7 days
    expire_7d = now_ts - (7 * 24 * 3600)
    await execute("DELETE FROM reaction_events WHERE ts < ?", (expire_7d,))
    await execute("DELETE FROM command_events WHERE ts < ?", (expire_7d,))
    
    # Delete voice_sessions older than 14 days
    expire_14d = now_ts - (14 * 24 * 3600)
    await execute("DELETE FROM voice_sessions WHERE join_ts < ?", (expire_14d,))
    
    print(f"[+] Cleaned up expired event data (older than retention windows)")

async def import_json_to_db(json_path: str = "data/xp.json"):
    """Legacy JSON import - V3: XP/Level removed, this function is now a no-op"""
    # V3 Migration: XP/Level system removed, JSON import no longer needed
    # Coins and other data should already be in the database from previous migrations
    print("[!] import_json_to_db is deprecated (V3: XP/Level removed). Skipping JSON import.")
    return

# Loan helper functions
async def get_loan_status(guild_id: int, user_id: int):
    """Get active loan status for a user"""
    return await fetchone(
        """SELECT loan_id, principal, remaining_principal, issued_at, due_at, status
           FROM loans WHERE guild_id = ? AND user_id = ? AND status = 'active'
           ORDER BY issued_at DESC LIMIT 1""",
        (guild_id, user_id)
    )

async def issue_loan(guild_id: int, user_id: int, principal: int, due_at: str):
    """Issue a new loan to a user"""
    now = _now_iso()
    await execute(
        """INSERT INTO loans (guild_id, user_id, principal, remaining_principal, issued_at, due_at, status)
           VALUES (?, ?, ?, ?, ?, ?, 'active')""",
        (guild_id, user_id, principal, principal, now, due_at)
    )

async def pay_loan(guild_id: int, user_id: int, amount: int):
    """Pay off part of a loan"""
    loan = await get_loan_status(guild_id, user_id)
    if not loan:
        return False
    
    loan_id = loan["loan_id"]
    remaining = loan["remaining_principal"]
    new_remaining = max(0, remaining - amount)
    
    if new_remaining == 0:
        # Loan fully paid
        await execute(
            "UPDATE loans SET remaining_principal = 0, status = 'paid' WHERE loan_id = ?",
            (loan_id,)
        )
    else:
        await execute(
            "UPDATE loans SET remaining_principal = ? WHERE loan_id = ?",
            (new_remaining, loan_id)
        )
    
    return True

async def convert_overdue_loans():
    """Convert overdue loans to debt"""
    now = _now_iso()
    now_dt = datetime.datetime.fromisoformat(now.replace('Z', '+00:00'))
    
    # Get all overdue active loans
    overdue_loans = await fetchall(
        """SELECT loan_id, guild_id, user_id, remaining_principal 
           FROM loans WHERE status = 'active' AND due_at < ?""",
        (now,)
    )
    
    converted_count = 0
    for loan in overdue_loans:
        loan_id = loan["loan_id"]
        guild_id = loan["guild_id"]
        user_id = loan["user_id"]
        remaining = loan["remaining_principal"]
        
        # Add to debt
        from core.data import update_debt
        await update_debt(guild_id, user_id, remaining)
        
        # Mark loan as converted
        await execute(
            """UPDATE loans SET status = 'converted', converted_to_debt_at = ?
               WHERE loan_id = ?""",
            (now, loan_id)
        )
        
        # Log to ledger
        await execute(
            """INSERT INTO economy_ledger (guild_id, user_id, ts, type, amount, meta_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (guild_id, user_id, now, "loan_converted_to_debt", remaining,
             json.dumps({"loan_id": loan_id}))
        )
        
        converted_count += 1
    
    return converted_count

