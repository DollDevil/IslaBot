"""
Data management for user XP, levels, coins, and statistics
"""
import json
import random
import datetime

# Global XP data storage
xp_data = {}

def load_xp_data():
    """Load XP data from file"""
    global xp_data
    try:
        with open("data/xp.json", "r") as f:
            xp_data = json.load(f)
    except FileNotFoundError:
        xp_data = {}

def save_xp_data():
    """Save XP data to file"""
    try:
        with open("data/xp.json", "w") as f:
            json.dump(xp_data, f, indent=4)
    except Exception as e:
        print(f"Error saving XP data: {e}")

def get_xp(user_id):
    """Get user's XP"""
    return xp_data.get(str(user_id), {}).get("xp", 0)

def get_level(user_id):
    """Get user's level"""
    return xp_data.get(str(user_id), {}).get("level", 1)

def get_coins(user_id):
    """Get user's coin balance"""
    return xp_data.get(str(user_id), {}).get("coins", 0)

def add_coins(user_id, amount):
    """Add coins to user's balance"""
    uid = str(user_id)
    if uid not in xp_data:
        xp_data[uid] = {"xp": 0, "level": 1, "coins": 0}
    xp_data[uid]["coins"] = xp_data[uid].get("coins", 0) + amount
    if xp_data[uid]["coins"] < 0:
        xp_data[uid]["coins"] = 0  # Prevent negative coins

def has_coins(user_id, amount):
    """Check if user has enough coins"""
    return get_coins(user_id) >= amount

def increment_event_participation(user_id):
    """Increment event participation count for a user"""
    uid = str(user_id)
    if uid not in xp_data:
        xp_data[uid] = {
            "xp": 0, "level": 1, "coins": 0,
            "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
            "times_gambled": 0, "total_wins": 0, "total_spent": 0,
            "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
            "equipped_collar": None, "equipped_badge": None
        }
    if "event_participations" not in xp_data[uid]:
        xp_data[uid]["event_participations"] = 0
    xp_data[uid]["event_participations"] = xp_data[uid].get("event_participations", 0) + 1
    save_xp_data()

def increment_gambling_attempt(user_id):
    """Increment gambling attempt count for a user"""
    uid = str(user_id)
    if uid not in xp_data:
        xp_data[uid] = {
            "xp": 0, "level": 1, "coins": 0,
            "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
            "times_gambled": 0, "total_wins": 0, "total_spent": 0,
            "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
            "equipped_collar": None, "equipped_badge": None
        }
    if "times_gambled" not in xp_data[uid]:
        xp_data[uid]["times_gambled"] = 0
    if "total_spent" not in xp_data[uid]:
        xp_data[uid]["total_spent"] = 0
    xp_data[uid]["times_gambled"] = xp_data[uid].get("times_gambled", 0) + 1
    save_xp_data()

def add_gambling_spent(user_id, amount):
    """Add to total money spent on gambling"""
    uid = str(user_id)
    if uid not in xp_data:
        xp_data[uid] = {
            "xp": 0, "level": 1, "coins": 0,
            "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
            "times_gambled": 0, "total_wins": 0, "total_spent": 0,
            "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
            "equipped_collar": None, "equipped_badge": None
        }
    if "total_spent" not in xp_data[uid]:
        xp_data[uid]["total_spent"] = 0
    xp_data[uid]["total_spent"] = xp_data[uid].get("total_spent", 0) + amount
    save_xp_data()

def increment_gambling_win(user_id):
    """Increment gambling win count for a user"""
    uid = str(user_id)
    if uid not in xp_data:
        xp_data[uid] = {
            "xp": 0, "level": 1, "coins": 0,
            "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
            "times_gambled": 0, "total_wins": 0,
            "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
            "equipped_collar": None, "equipped_badge": None
        }
    if "total_wins" not in xp_data[uid]:
        xp_data[uid]["total_wins"] = 0
    xp_data[uid]["total_wins"] = xp_data[uid].get("total_wins", 0) + 1
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
    if user_id not in daily_cooldowns:
        return False, reset_timestamp
    last_claim = daily_cooldowns[user_id]
    now = datetime.datetime.now(datetime.UTC)
    if now >= last_claim + datetime.timedelta(days=1):
        uk_tz = datetime.timezone(datetime.timedelta(hours=0))
        uk_now = datetime.datetime.now(uk_tz)
        if uk_now.hour >= 18:
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

