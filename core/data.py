"""
Data management for user XP, levels, coins, and statistics
"""
import json
import random
import datetime
import asyncio

# Global XP data storage
xp_data = {}

# Default user data template for new users
_DEFAULT_USER_DATA = {
    "xp": 0,
    "level": 1,
    "coins": 0,
    "messages_sent": 0,
    "vc_minutes": 0,
    "event_participations": 0,
    "times_gambled": 0,
    "total_wins": 0,
    "badges_owned": [],
    "collars_owned": [],
    "interfaces_owned": [],
    "equipped_collar": None,
    "equipped_badge": None
}

# Optimization: Debouncing for file saves
_save_pending = False
_save_task = None

def load_xp_data():
    """Load XP data from file"""
    global xp_data
    try:
        with open("data/xp.json", "r") as f:
            xp_data = json.load(f)
    except FileNotFoundError:
        xp_data = {}

# Optimization: Debouncing for file saves to reduce I/O
_save_pending = False
_save_task = None
_last_save_time = None

def save_xp_data(force=False):
    """Save XP data to file with debouncing to prevent excessive writes"""
    global _save_pending, _save_task, _last_save_time
    
    if force:
        # Force immediate save (for shutdown, critical operations)
        try:
            with open("data/xp.json", "w") as f:
                json.dump(xp_data, f, indent=4)
            _last_save_time = datetime.datetime.now(datetime.UTC)
        except Exception as e:
            print(f"Error saving XP data: {e}")
        _save_pending = False
        if _save_task:
            _save_task.cancel()
            _save_task = None
        return
    
    # Debounce: Only save if not already pending and enough time has passed
    current_time = datetime.datetime.now(datetime.UTC)
    if _last_save_time:
        time_since_save = (current_time - _last_save_time).total_seconds()
        if time_since_save < 2:  # Don't save more than once every 2 seconds
            return
    
    if not _save_pending:
        _save_pending = True
        # Schedule save after 2 seconds (batches multiple rapid saves)
        async def delayed_save():
            await asyncio.sleep(2)
            try:
                with open("data/xp.json", "w") as f:
                    json.dump(xp_data, f, indent=4)
                global _last_save_time
                _last_save_time = datetime.datetime.now(datetime.UTC)
            except Exception as e:
                print(f"Error saving XP data: {e}")
            finally:
                global _save_pending, _save_task
                _save_pending = False
                _save_task = None
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                if _save_task:
                    _save_task.cancel()
                _save_task = asyncio.create_task(delayed_save())
            else:
                loop.run_until_complete(delayed_save())
        except RuntimeError:
            # No event loop, save immediately
            try:
                with open("data/xp.json", "w") as f:
                    json.dump(xp_data, f, indent=4)
                _last_save_time = datetime.datetime.now(datetime.UTC)
            except Exception as e:
                print(f"Error saving XP data: {e}")
            _save_pending = False

# Optimization: Cache user data lookups to avoid repeated string conversions
_user_data_cache = {}

def _get_user_data(user_id):
    """Get user data with caching"""
    uid = str(user_id)
    if uid not in _user_data_cache or uid not in xp_data:
        _user_data_cache[uid] = xp_data.get(uid, {})
    elif uid in xp_data:
        _user_data_cache[uid] = xp_data[uid]
    return _user_data_cache[uid]

def get_xp(user_id):
    """Get user's XP"""
    return _get_user_data(user_id).get("xp", 0)

def get_level(user_id):
    """Get user's level"""
    return _get_user_data(user_id).get("level", 1)

def get_coins(user_id):
    """Get user's coin balance"""
    return _get_user_data(user_id).get("coins", 0)

def add_coins(user_id, amount):
    """Add coins to user's balance"""
    uid = str(user_id)
    user_data = _get_user_data(user_id)
    if uid not in xp_data:
        xp_data[uid] = {"xp": 0, "level": 1, "coins": 0}
        _user_data_cache[uid] = xp_data[uid]
    coins = user_data.get("coins", 0) + amount
    xp_data[uid]["coins"] = max(0, coins)  # Prevent negative coins
    _user_data_cache[uid] = xp_data[uid]

def has_coins(user_id, amount):
    """Check if user has enough coins"""
    return get_coins(user_id) >= amount

def increment_event_participation(user_id):
    """Increment event participation count for a user"""
    uid = str(user_id)
    if uid not in xp_data:
        xp_data[uid] = _DEFAULT_USER_DATA.copy()
        _user_data_cache[uid] = xp_data[uid]
    user_data = xp_data[uid]
    user_data["event_participations"] = user_data.get("event_participations", 0) + 1
    _user_data_cache[uid] = user_data
    save_xp_data()

def increment_gambling_attempt(user_id):
    """Increment gambling attempt count for a user"""
    uid = str(user_id)
    if uid not in xp_data:
        xp_data[uid] = _DEFAULT_USER_DATA.copy()
        _user_data_cache[uid] = xp_data[uid]
    user_data = xp_data[uid]
    user_data.setdefault("times_gambled", 0)
    user_data.setdefault("total_spent", 0)
    user_data["times_gambled"] += 1
    _user_data_cache[uid] = user_data
    save_xp_data()

def add_gambling_spent(user_id, amount):
    """Add to total money spent on gambling"""
    uid = str(user_id)
    if uid not in xp_data:
        xp_data[uid] = _DEFAULT_USER_DATA.copy()
        _user_data_cache[uid] = xp_data[uid]
    user_data = xp_data[uid]
    user_data["total_spent"] = user_data.get("total_spent", 0) + amount
    _user_data_cache[uid] = user_data
    save_xp_data()

def increment_gambling_win(user_id):
    """Increment gambling win count for a user"""
    uid = str(user_id)
    if uid not in xp_data:
        xp_data[uid] = _DEFAULT_USER_DATA.copy()
        _user_data_cache[uid] = xp_data[uid]
    user_data = xp_data[uid]
    user_data["total_wins"] = user_data.get("total_wins", 0) + 1
    _user_data_cache[uid] = user_data
    save_xp_data()

def get_activity_quote(user_id, guild=None):
    """Get activity quote based on user stats with priority order"""
    uid = str(user_id)
    if uid not in xp_data:
        return "Keep working hard for me ~"
    
    user_data = xp_data[uid]
    messages_sent = user_data.get("messages_sent", 0)
    vc_minutes = user_data.get("vc_minutes", 0)
    event_participations = user_data.get("event_participations", 0)
    coins = user_data.get("coins", 0)
    badges = len(user_data.get("badges_owned", []))
    collars = len(user_data.get("collars_owned", []))
    interfaces = len(user_data.get("interfaces_owned", []))
    total_items = badges + collars + interfaces
    
    # Calculate event participation rate (if we have guild and member joined date)
    event_participation_rate = 0
    if guild:
        try:
            member = guild.get_member(int(user_id))
            if member:
                # Estimate events since join (rough calculation)
                days_since_join = (datetime.datetime.now(datetime.UTC) - member.joined_at.replace(tzinfo=datetime.UTC)).days
                # Assume ~7 events per day (Tier 1: 4, Tier 2: 2, Tier 3: 1)
                estimated_events = max(1, days_since_join * 7)
                event_participation_rate = (event_participations / estimated_events) * 100 if estimated_events > 0 else 0
        except:
            pass
    
    # Priority order: Lurker > Follower > Collector > Rich > Chatty > Voice Chatter
    # 1. Lurker (lowest activity, overrides everything)
    if messages_sent < 20 and vc_minutes < 30:
        quotes = [
            "So quiet… but you're still here <:Islaseductive:1451296572255109210>",
            "You haven't said much—but you haven't left either <:Islaseductive:1451296572255109210>",
            "Silence doesn't mean absence. It just means patience <:Islaseductive:1451296572255109210>"
        ]
        return random.choice(quotes)
    
    # 2. Follower (event loyalist)
    if event_participation_rate >= 95:
        quotes = [
            "You don't miss much. That kind of consistency stands out <:Islaseductive:1451297729417445560>",
            "You keep showing up. I reward patterns like that <a:A_yum:1450190542771191859>",
            "You follow every little command. Good dog <a:A_yum:1450190542771191859>"
        ]
        return random.choice(quotes)
    
    # 3. Collector
    if total_items > 10:
        quotes = [
            "You like keeping things I give you <:Islaseductive:1451296572255109210>",
            "Such a careful collector. Nothing goes to waste with you <:Islaseductive:1451297729417445560>",
            "You've gathered quite a collection. That says a lot <:Islaseductive:1451297729417445560>"
        ]
        return random.choice(quotes)
    
    # 4. Rich
    if coins > 50000:
        quotes = [
            "All those coins… you clearly know how to play <:Islaseductive:1451297729417445560>",
            "Wealth suits you. Or maybe you suit it <:Islaseductive:1451297729417445560>",
            "You're sitting on quite a pile. I wonder what you're saving it for <:Islaseductive:1451296572255109210>"
        ]
        return random.choice(quotes)
    
    # 5. Chatty (text messages > voice messages)
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
    
    # 6. Voice Chatter (voice messages > text messages)
    if voice_points > text_points:
        quotes = [
            "I see you prefer being heard instead of seen <:mouth:1449996812093231206>",
            "So much time talking… I wonder who you're trying to impress <:Islaconfidentlaugh:1451296233636368515>",
            "You linger in VC like you're waiting for something. Are you waiting for me? <:Islalips:1451296607760023652>"
        ]
        return random.choice(quotes)
    
    # Default
    return "Keep working hard for me ~"

# Daily/Give cooldowns (resets at 6pm UK daily)
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
    
    # If user has never claimed, they can claim
    if user_id not in daily_cooldowns:
        return False, reset_timestamp
    
    last_claim = daily_cooldowns[user_id]
    now = datetime.datetime.now(datetime.UTC)
    
    # Get UK timezone for proper day checking
    uk_tz = datetime.timezone(datetime.timedelta(hours=0))
    uk_now = datetime.datetime.now(uk_tz)
    
    # Convert last_claim to UK time (it's stored in UTC)
    last_claim_utc = last_claim.replace(tzinfo=datetime.timezone.utc)
    uk_last_claim = last_claim_utc.astimezone(uk_tz)
    
    # Calculate which "day" each claim is on (day starts at 6pm)
    # If time is before 6pm, it's still the previous day for reset purposes
    def get_reset_day(dt):
        """Get the reset day for a datetime. Day resets at 6pm."""
        if dt.hour < 18:
            # Before 6pm, this is still the previous reset day
            return (dt - datetime.timedelta(days=1)).date()
        else:
            # After 6pm, this is the current reset day
            return dt.date()
    
    last_reset_day = get_reset_day(uk_last_claim)
    current_reset_day = get_reset_day(uk_now)
    
    # If it's a different reset day, can claim
    if current_reset_day > last_reset_day:
        return False, reset_timestamp
    
    # Otherwise, still on cooldown
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

