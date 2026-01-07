"""
SQLite database management for IslaBot V2
"""
import aiosqlite
import datetime
import json
import os

# Database connection
_db = None
_db_path = "data/isla_bot.db"

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
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            coins INTEGER DEFAULT 0,
            times_gambled INTEGER DEFAULT 0,
            total_wins INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        )
    """)
    
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
            readiness_pct INTEGER DEFAULT 0,
            blocker_text TEXT,
            computed_at TEXT NOT NULL,
            failed_weeks_count INTEGER DEFAULT 0,
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

async def upsert_user_profile(guild_id: int, user_id: int, xp: int = None, level: int = None, coins: int = None, 
                               times_gambled: int = None, total_wins: int = None, total_spent: int = None):
    """Upsert user profile"""
    now = _now_iso()
    
    # Get existing values if not provided
    existing = await fetchone(
        "SELECT xp, level, coins, times_gambled, total_wins, total_spent FROM user_profile WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    
    if existing:
        xp = xp if xp is not None else existing["xp"]
        level = level if level is not None else existing["level"]
        coins = coins if coins is not None else existing["coins"]
        times_gambled = times_gambled if times_gambled is not None else existing["times_gambled"]
        total_wins = total_wins if total_wins is not None else existing["total_wins"]
        total_spent = total_spent if total_spent is not None else existing["total_spent"]
        
        await execute(
            """UPDATE user_profile SET xp = ?, level = ?, coins = ?, times_gambled = ?, total_wins = ?, total_spent = ?, updated_at = ?
               WHERE guild_id = ? AND user_id = ?""",
            (xp, level, coins, times_gambled, total_wins, total_spent, now, guild_id, user_id)
        )
    else:
        xp = xp or 0
        level = level or 1
        coins = coins or 0
        times_gambled = times_gambled or 0
        total_wins = total_wins or 0
        total_spent = total_spent or 0
        
        await execute(
            """INSERT INTO user_profile (guild_id, user_id, xp, level, coins, times_gambled, total_wins, total_spent, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (guild_id, user_id, xp, level, coins, times_gambled, total_wins, total_spent, now)
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
        """INSERT INTO activity_daily (guild_id, user_id, day, messages, vc_minutes, events, presence_ticks, updated_at)
           VALUES (?, ?, ?, 0, ?, 0, 0, ?)
           ON CONFLICT(guild_id, user_id, day) DO UPDATE SET vc_minutes = vc_minutes + ?, updated_at = ?""",
        (guild_id, user_id, day, minutes, now, minutes, now)
    )

async def bump_event(guild_id: int, user_id: int):
    """Increment daily event count"""
    day = _today_str()
    now = _now_iso()
    
    await execute(
        """INSERT INTO activity_daily (guild_id, user_id, day, messages, vc_minutes, events, presence_ticks, updated_at)
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
    """Import existing JSON data into database (one-time migration)"""
    if not os.path.exists(json_path):
        print(f"[!] JSON file not found: {json_path}, skipping import")
        return
    
    try:
        with open(json_path, "r") as f:
            xp_data = json.load(f)
    except Exception as e:
        print(f"[!] Error reading JSON file: {e}")
        return
    
    if not xp_data:
        print("[!] JSON file is empty, skipping import")
        return
    
    print(f"[*] Importing {len(xp_data)} users from JSON to database...")
    
    # Use guild_id = 0 for legacy data (not guild-aware)
    guild_id = 0
    
    imported = 0
    for user_id_str, user_data in xp_data.items():
        try:
            user_id = int(user_id_str)
            
            # Import profile
            xp = user_data.get("xp", 0)
            level = user_data.get("level", 1)
            coins = user_data.get("coins", 0)
            times_gambled = user_data.get("times_gambled", 0)
            total_wins = user_data.get("total_wins", 0)
            total_spent = user_data.get("total_spent", 0)
            
            await upsert_user_profile(guild_id, user_id, xp, level, coins, times_gambled, total_wins, total_spent)
            
            # Import economy balance
            coins_lifetime = user_data.get("coins_lifetime", coins)
            if coins_lifetime != coins:
                await upsert_economy_balance(guild_id, user_id, coins_lifetime - coins)
            
            # Import inventory items
            for badge in user_data.get("badges_owned", []):
                await execute(
                    """INSERT OR IGNORE INTO inventory_items (guild_id, user_id, item_type, item_id, acquired_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (guild_id, user_id, "badge", badge, _now_iso())
                )
            
            for collar in user_data.get("collars_owned", []):
                await execute(
                    """INSERT OR IGNORE INTO inventory_items (guild_id, user_id, item_type, item_id, acquired_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (guild_id, user_id, "collar", collar, _now_iso())
                )
            
            for interface in user_data.get("interfaces_owned", []):
                await execute(
                    """INSERT OR IGNORE INTO inventory_items (guild_id, user_id, item_type, item_id, acquired_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (guild_id, user_id, "interface", interface, _now_iso())
                )
            
            # Import equipped items
            equipped_collar = user_data.get("equipped_collar")
            equipped_badge = user_data.get("equipped_badge")
            if equipped_collar or equipped_badge:
                await execute(
                    """INSERT OR REPLACE INTO inventory_equipped (guild_id, user_id, equipped_collar, equipped_badge, equipped_interface, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (guild_id, user_id, equipped_collar, equipped_badge, None, _now_iso())
                )
            
            # Import activity totals (create a single daily row with totals)
            messages_sent = user_data.get("messages_sent", 0)
            vc_minutes = user_data.get("vc_minutes", 0)
            event_participations = user_data.get("event_participations", 0)
            
            if messages_sent > 0 or vc_minutes > 0 or event_participations > 0:
                day = _today_str()
                await execute(
                    """INSERT OR REPLACE INTO activity_daily (guild_id, user_id, day, messages, vc_minutes, events, presence_ticks, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
                    (guild_id, user_id, day, messages_sent, vc_minutes, event_participations, _now_iso())
                )
            
            imported += 1
            
        except Exception as e:
            print(f"[!] Error importing user {user_id_str}: {e}")
            continue
    
    print(f"[+] Successfully imported {imported} users from JSON to database")

