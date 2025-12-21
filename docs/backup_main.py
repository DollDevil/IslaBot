import discord
from discord.ext import commands, tasks
from discord import FFmpegPCMAudio
from discord import app_commands
import json
import random
import secrets
import os
import datetime
import asyncio
import re
from dotenv import load_dotenv

# Timezone support
# Try zoneinfo first (Python 3.9+), then backports, then pytz
USE_PYTZ = False
try:
    from zoneinfo import ZoneInfo
    def get_timezone(name):
        return ZoneInfo(name)
except ImportError:
    try:
        from backports.zoneinfo import ZoneInfo
        def get_timezone(name):
            return ZoneInfo(name)
    except ImportError:
        # Fallback to pytz
        try:
            import pytz
            USE_PYTZ = True
            def get_timezone(name):
                return pytz.timezone(name)
        except ImportError:
            print("WARNING: No timezone support available. Install pytz: pip install pytz")
            def get_timezone(name):
                return None

# Load environment variables from secret.env file (if it exists)
# On Wispbyte, use environment variables directly instead of secret.env
try:
    load_dotenv('secret.env')
except Exception as e:
    print(f"Note: Could not load secret.env file: {e}. Using system environment variables instead.")

# -----------------------------
# Bot setup
# -----------------------------
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True
intents.voice_states = True

COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(COMMAND_PREFIX),
    intents=intents,
    case_insensitive=True,
    strip_after_prefix=True,
)

# -----------------------------
# Channels configuration
# -----------------------------
ALLOWED_SEND_CHANNELS = [
    1450107538019192832,  # Level up messages
    1407164453094686762,  # Logs channel
    1450628852345868369,  # Event 7 Phase 2 channel
    1450329944549752884,  # Event 7 Phase 3 failed channel
    1450329916146057266,  # Event 7 Phase 3 success channel
]
XP_TRACK_CHANNELS = [
    # Text channels where XP is tracked
    1407167717022109796,
    1412583527332974622,
    1407167072361910292,
    1407164449126617110,
    1450147031745040516,
    1450145080034857031,
    1407166856455913562,
    1450147097524306021,
    1450962305092423760,
    1450628852345868369,
    1450329916146057266,
    1450329944549752884,
    1450693708465967174,  # Event 4 Phase 2 - Woof channel
    1450693722512818196,  # Event 4 Phase 2 - Meow channel
    1451697334034497728,
    1451708265703669822,
]
# Voice channels where XP is tracked
VC_XP_TRACK_CHANNELS = {
    1450201595575795866,
    1450203538352246976,
    1451254356841332808,
}
VC_XP = 5  # XP per minute in voice
MESSAGE_COOLDOWN = 10  # seconds
EXCLUDED_ROLE_IDS = {
    1407164448132698221,  # Admin/Bot role
    1407164448132698220,  # Admin/Bot role
    1411294634843439134,  # Admin/Bot role
    1407164448132698215,  # Admin/Bot role
}  # Users with these roles don't gain XP

# XP Multiplier roles - each adds 0.2x (20%) bonus
MULTIPLIER_ROLES = [1450182197310132365, 1407164448132698218, 1449945175412707460]

# Categories excluded from XP gain
NON_XP_CATEGORY_IDS = {1407164448707313750}

# Channels excluded from XP gain
NON_XP_CHANNEL_IDS = {1449946515882774630, 1411436063842635816, 1449922902760882307, 1450188229734043770}

# Channel multipliers
CHANNEL_MULTIPLIERS = {
    1407167072361910292: 1.2,
    1412583527332974622: 1.2,
    1450145080034857031: 1.1,
    1407166856455913562: 1.1,
    1450147097524306021: 1.1,
}

# XP thresholds per level; after the list, each level adds +10k XP requirement
XP_THRESHOLDS = [10, 100, 500, 2000, 5000, 8000, 11000, 15000, 20000]

# Use sets for quick, type-safe membership checks
XP_TRACK_SET = {int(ch) for ch in XP_TRACK_CHANNELS}
ALLOWED_SEND_SET = {int(ch) for ch in ALLOWED_SEND_CHANNELS}
MULTIPLIER_ROLE_SET = {int(r) for r in MULTIPLIER_ROLES}
EXCLUDED_ROLE_SET = {int(r) for r in EXCLUDED_ROLE_IDS}

# Level -> role mapping
LEVEL_ROLE_MAP = {
    1: 1450113474247004171,
    2: 1450113555478352014,
    5: 1450113470769926327,
    10: 1450111760530018525,
    20: 1450111757606457506,
    30: 1450111754821701743,
    40: 1450128927161979066,
    50: 1450111746932215819,
    75: 1450128929435287635,
    100: 1450128933189324901,
}

# Reply system configuration
REPLY_CHANNEL_ID = 1407167072361910292
LEVEL_2_ROLE_ID = 1450113555478352014
BETA_BOOST_SERVANT_ROLE_IDS = {1407164448132698218, 1450182197310132365, 1449945175412707460}
KITTEN_ROLE_ID = 1407169798944592033
PUPPY_ROLE_ID = 1407170105326174208
PET_ROLE_ID = 1407169870306738199
DEVOTEE_ROLE_ID = 1407164448132698216

# Reply quotes by role priority
REPLY_QUOTES = {
    "level_2": [
        "You took your time introducing yourself… but I'm glad you finally did.",
        "I was wondering when you'd say something about yourself.",
        "You've been here a while. I would have liked to hear from you sooner.",
        "It's good you introduced yourself at last.",
        "Next time, don't keep me waiting.",
    ],
    "beta_boost_servant": [
        "I've read your introduction carefully. I'm glad you're here.",
        "You've earned my attention. Stay close.",
        "Good. I was hoping you'd join us.",
        "I noticed you. That matters more than you think.",
        "You belong here… with me.",
    ],
    "puppy": [
        "Good boy.",
        "That's a good puppy.",
        "I like puppies who listen. You're doing well already.",
        "You did exactly what you were supposed to. Good boy.",
        "Come here. Good puppy.",
    ],
    "kitten": [
        "How sweet. You're curious, aren't you? I like kittens like that.",
        "You introduced yourself beautifully. Such a well-mannered little kitten.",
        "So attentive… I can already tell you enjoy being noticed.",
        "Good girl. I enjoy watching kittens settle in.",
        "You've found a comfortable spot already. Clever kitten.",
    ],
    "pet": [
        "It's nice to find a good pet like you.",
        "Be a good pet for me.",
        "You're doing well already. I like that.",
        "You belong here. Stay close.",
        "Good. I enjoy having pets who listen.",
    ],
    "devotee": [
        "I enjoyed reading your introduction.",
        "Thank you for sharing. I think you'll do well here.",
        "I'm glad you're here.",
        "Welcome. I'll be watching.",
        "Good. You may stay.",
    ],
}

# -----------------------------
# Obedience event config
# -----------------------------
# Event system configuration
EVENT_DURATION_SECONDS = 300  # 5 minutes
EVENT_COOLDOWN_SECONDS = 1800  # 30 minutes after event ends
EVENT_CHANNEL_ID = 1450533795156594738
EVENT_PHASE2_CHANNEL_ID = 1450628852345868369
EVENT_PHASE3_FAILED_CHANNEL_ID = 1450329944549752884
EVENT_PHASE3_SUCCESS_CHANNEL_ID = 1450329916146057266

# Allowed guilds - bot will leave any server not in this list
ALLOWED_GUILDS = {1407164448132698213}  # Main server ID

# Event 2 audio file - can be local path or URL
# For Wispbyte hosting, MUST use a URL (upload to cloud storage, GitHub, or file hosting service)
# Set EVENT_2_AUDIO environment variable to a URL for cloud hosting
EVENT_2_AUDIO = os.getenv("EVENT_2_AUDIO", None)

# Event tiers and scheduling - UK timezone
# Tier 1: 9:00 AM, 3:00 PM, 9:00 PM, 3:00 AM (4 times per day)
# Tier 2: 12:00 PM, 6:00 PM (2 times per day)
# Tier 3: 12:00 AM (1 time per day)
EVENT_SCHEDULE = {
    1: [(3, 0), (6, 0), (9, 0), (15, 0), (21, 0)],  # Tier 1: (hour, minute) in UK time
    2: [(12, 0), (18, 0)],                   # Tier 2: (hour, minute) in UK time
    3: [(0, 0)],                             # Tier 3: (hour, minute) in UK time
}

# Event tier assignments
EVENT_TIER_MAP = {
    1: 1,  # Presence Check - Tier 1
    2: 1,  # Silent Company - Tier 1
    3: 1,  # Hidden Reaction - Tier 1
    4: 2,  # Keyword Prompt - Tier 2
    5: 2,  # Direct Prompt - Tier 2
    6: 1,  # Choice Event - Tier 1
    7: 3,  # Collective Event - Tier 3
}

# Voice channels for Event 2
EVENT_2_VC_CHANNELS = [1451254356841332808]

# Event rewards
EVENT_REWARDS = {
    1: 30,   # Presence check - per message (10s cooldown)
    2: 50,   # Silent company - bonus XP at end
    3: 30,   # Hidden reaction
    4: 50,   # Keyword prompt
    5: 50,   # Direct prompt (20 XP for sorry replies)
    6: {"win": 100, "lose": -200},  # Choice event
    7: {
        "phase1": 50,  # Phase 1 button click
        "phase2_correct": 50,
        "phase2_wrong": -50,
    },
}

# Event 4 role IDs
EVENT_4_WOOF_ROLE = 1450589458675011726
EVENT_4_MEOW_ROLE = 1450685119684808867

# Event 4 channel IDs
EVENT_4_WOOF_CHANNEL_ID = 1450693708465967174
EVENT_4_MEOW_CHANNEL_ID = 1450693722512818196

# Event 7 role IDs
EVENT_7_OPT_IN_ROLE = 1450589443152023583
EVENT_7_SUCCESS_ROLE = 1450285064943571136
EVENT_7_FAILED_ROLE = 1450285246019928104

# Roles that should be cleared when no events are active
EVENT_CLEANUP_ROLES = [
    1450589458675011726,  # EVENT_4_WOOF_ROLE
    1450685119684808867,  # EVENT_4_MEOW_ROLE
    1450285064943571136,  # EVENT_7_SUCCESS_ROLE
    1450285112951574590,
    1450285211932823693,
    1450285246019928104,  # EVENT_7_FAILED_ROLE
    1450285257420181688,
    1450285259890364541,
    1450589443152023583,  # EVENT_7_OPT_IN_ROLE
]

COLLECTIVE_THRESHOLD = 10

# Command permission roles
ADMIN_ROLE_IDS = {1407164448132698221, 1407164448132698220}  # Admin commands (!obedience, !throne, !killevent)
USER_COMMAND_ROLE_ID = 1407164448132698216  # User commands (!level, !leaderboard, !info)

# Command allowed channels
ADMIN_COMMAND_CHANNEL_ID = 1407164453094686762  # Admin commands only work here
USER_COMMAND_CHANNEL_ID = 1450107538019192832  # User commands only work here

# Channel permission roles
EVENT_PHASE2_ALLOWED_ROLE = 1450589443152023583  # Event 7 Phase 2 channel
EVENT_PHASE3_FAILED_ROLES = {1450285246019928104, 1450285257420181688, 1450285259890364541}  # Failure channel
EVENT_PHASE3_SUCCESS_ROLES = {1450285064943571136, 1450285112951574590, 1450285211932823693}  # Success channel

# Event scheduling state
active_event = None
# Track which scheduled times have been used today (format: "YYYY-MM-DD_TIER_HH:MM")
last_event_times_today = set()
# Track which Daily Check times have been sent today (format: "YYYY-MM-DD_DAILY_CHECK_HH:MM")
last_daily_check_times_today = set()
event_cooldown_until = None
event_scheduler_task = None
events_enabled = True  # Flag to stop/start events

# Coin system
# 1 coin per 10 XP received
# Level up bonuses defined in LEVEL_COIN_BONUSES
LEVEL_COIN_BONUSES = {
    1: 10,
    2: 50,
    5: 100,
    10: 200,
    20: 300,
    30: 400,
    50: 500,
    75: 750,
    100: 1000,
}

# Gambling cooldowns (10 seconds)
gambling_cooldowns = {}

# Daily/Give cooldowns (resets at 6pm UK daily)
daily_cooldowns = {}
give_cooldowns = {}

# Slots free spins storage
slots_free_spins = {}  # {user_id: {"count": int, "total_winnings": int}}

# Gambling streaks (hot/cold)
gambling_streaks = {}  # {user_id: {"streak": int, "last_activity": datetime}}

# -----------------------------
# Load XP data
# -----------------------------
try:
    with open("xp.json", "r") as f:
        xp_data = json.load(f)
except FileNotFoundError:
    xp_data = {}

# -----------------------------
# XP functions
# -----------------------------
def get_xp(user_id):
    return xp_data.get(str(user_id), {}).get("xp", 0)

def get_level(user_id):
    return xp_data.get(str(user_id), {}).get("level", 1)

def get_coins(user_id):
    """Get user's coin balance."""
    return xp_data.get(str(user_id), {}).get("coins", 0)

def increment_event_participation(user_id):
    """Increment event participation count for a user."""
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
    """Increment gambling attempt count for a user."""
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
    """Add to total money spent on gambling."""
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
    """Increment gambling win count for a user."""
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
    """Get activity quote based on user stats with priority order."""
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
                # This is a simplified version - you may want to track actual events
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

def add_coins(user_id, amount):
    """Add coins to user's balance."""
    uid = str(user_id)
    if uid not in xp_data:
        xp_data[uid] = {"xp": 0, "level": 1, "coins": 0}
    xp_data[uid]["coins"] = xp_data[uid].get("coins", 0) + amount
    if xp_data[uid]["coins"] < 0:
        xp_data[uid]["coins"] = 0  # Prevent negative coins

def has_coins(user_id, amount):
    """Check if user has enough coins."""
    return get_coins(user_id) >= amount

def save_xp_data():
    """Save XP data to file"""
    try:
        with open("xp.json", "w") as f:
            json.dump(xp_data, f, indent=4)
    except Exception as e:
        print(f"Error saving XP data: {e}")

def next_level_requirement(level: int) -> int:
    """Return XP needed to reach the given level."""
    if level - 1 < len(XP_THRESHOLDS):
        return XP_THRESHOLDS[level - 1]
    return XP_THRESHOLDS[-1] + (level - len(XP_THRESHOLDS)) * 10000

def resolve_channel_id(channel) -> int:
    """Get a consistent channel id (threads fall back to parent)."""
    channel_id = getattr(channel, "id", None)
    parent_id = getattr(getattr(channel, "parent", None), "id", None)
    return int(channel_id or parent_id or 0)

def resolve_category_id(channel) -> int:
    """Return category id for a channel/thread if available."""
    category = getattr(channel, "category", None)
    parent = getattr(channel, "parent", None)
    if category and getattr(category, "id", None):
        return int(category.id)
    if parent and getattr(parent, "category", None):
        cat = parent.category
        if getattr(cat, "id", None):
            return int(cat.id)
    return 0

def get_channel_multiplier(channel_id: int) -> float:
    return CHANNEL_MULTIPLIERS.get(int(channel_id), 1.0)

def get_reply_quote(member: discord.Member) -> str:
    """Get appropriate reply quote based on member's roles (priority order)."""
    if not isinstance(member, discord.Member):
        return random.choice(REPLY_QUOTES["devotee"])
    
    role_ids = {int(role.id) for role in member.roles}
    
    # Check in priority order
    if LEVEL_2_ROLE_ID in role_ids:
        return random.choice(REPLY_QUOTES["level_2"])
    
    if any(rid in BETA_BOOST_SERVANT_ROLE_IDS for rid in role_ids):
        return random.choice(REPLY_QUOTES["beta_boost_servant"])
    
    if KITTEN_ROLE_ID in role_ids:
        return random.choice(REPLY_QUOTES["kitten"])
    
    if PUPPY_ROLE_ID in role_ids:
        return random.choice(REPLY_QUOTES["puppy"])
    
    if PET_ROLE_ID in role_ids:
        return random.choice(REPLY_QUOTES["pet"])
    
    if DEVOTEE_ROLE_ID in role_ids:
        return random.choice(REPLY_QUOTES["devotee"])
    
    # Default to devotee quotes if no matching role
    return random.choice(REPLY_QUOTES["devotee"])

async def update_roles_on_level(member: discord.Member, level: int):
    """Assign level roles based on reached level; remove all other level roles (only keep highest)."""
    if not isinstance(member, discord.Member):
        return
    if member.bot or any(int(role.id) in EXCLUDED_ROLE_SET for role in member.roles):
        return
    
    # Find the highest level role the user qualifies for
    highest_qualifying_level = 0
    role_to_add = None
    for lvl, role_id in LEVEL_ROLE_MAP.items():
        if level >= lvl and lvl > highest_qualifying_level:
            highest_qualifying_level = lvl
            role_to_add = member.guild.get_role(role_id)
    
    # Remove all level roles first (check current roles to see what needs removing)
    roles_to_remove = []
    current_role_ids = {int(role.id) for role in member.roles}
    for lvl, role_id in LEVEL_ROLE_MAP.items():
        if role_id in current_role_ids:
            role = member.guild.get_role(role_id)
            if role:
                roles_to_remove.append(role)
    
    try:
        # Remove all level roles first
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason=f"Level {level} - removing old level roles")
            print(f"  ↳ Removed {len(roles_to_remove)} old level role(s) from {member.name}")
        
        # Add only the highest qualifying role
        if role_to_add:
            if role_to_add not in member.roles:
                await member.add_roles(role_to_add, reason=f"Reached level {level}")
                print(f"  ↳ Added level {highest_qualifying_level} role to {member.name}")
            else:
                print(f"  ↳ {member.name} already has level {highest_qualifying_level} role")
    except Exception as e:
        print(f"Failed to sync roles for {member} at level {level}: {e}")

async def clear_event_roles():
    """Clear all event-related roles from all members when no events are active."""
    global active_event
    if active_event:
        return  # Don't clear roles if an event is active
    
    for guild in bot.guilds:
        for role_id in EVENT_CLEANUP_ROLES:
            role = guild.get_role(role_id)
            if not role:
                continue
            
            members_with_role = [m for m in guild.members if role in m.roles]
            if members_with_role:
                try:
                    for member in members_with_role:
                        await member.remove_roles(role, reason="Event cleanup - no active events")
                    print(f"Cleared {len(members_with_role)} members from role {role.name} ({role_id})")
                except Exception as e:
                    print(f"Failed to clear role {role.name} ({role_id}): {e}")

# -----------------------------
# Obedience Events helpers
# -----------------------------
def build_event_embed(description: str, image_url: str = None) -> discord.Embed:
    """Build event embed with description and optional image."""
    embed = discord.Embed(
        description=f"*{description}*",
        color=0xff000d,
    )
    if image_url:
        embed.set_image(url=image_url)
    return embed

def event_prompt(event_type: int) -> tuple:
    """Get event prompt and image URL. Returns (prompt, image_url)."""
    prompts = {
        1: [
            ("I don't see enough messages sent… are you being shy now?", "https://i.imgur.com/r4ovg5g.png"),
            ("I don't see enough messages sent… that's not very impressive.", "https://i.imgur.com/r4ovg5g.png"),
            ("I don't see enough messages sent… you can type more than that.", "https://i.imgur.com/r4ovg5g.png"),
            ("It's so quiet in here… entertain me.", "https://i.imgur.com/r4ovg5g.png"),
            ("It's so quiet in here… did you forget how to type?", "https://i.imgur.com/r4ovg5g.png"),
        ],
        2: [
            ("You can join voice and stay quiet. I don't mind.", "https://i.imgur.com/773NSZA.png"),
            ("Come join me in voice. Silence is fine.", "https://i.imgur.com/773NSZA.png"),
            ("Sit with me in voice for a bit. That's enough.", "https://i.imgur.com/773NSZA.png"),
        ],
        3: [
            ("Don't overthink it. Would you give me your heart?", "https://i.imgur.com/K9BVKMv.png"),
            ("You can answer without words. Your heart will do.", "https://i.imgur.com/K9BVKMv.png"),
            ("It's simple. Would you offer me your heart?", "https://i.imgur.com/K9BVKMv.png"),
        ],
        4: [
            ("Choose wisely.", None),
        ],
        5: [
            ("Are you still with me?", None),
        ],
        6: [
            ("Choose wisely.", "https://i.imgur.com/zAg5z06.png"),
        ],
        7: [
            ("Are you there my doggies?\n\nI have a little something for you.", "https://i.imgur.com/XjGS6Gk.png"),
        ],
    }
    choices = prompts.get(event_type, [("...", None)])
    return random.choice(choices)

def event_6_prompt() -> tuple:
    """Get Event 6 prompt (Photo Reaction)."""
    variations = [
        ("I know you're there, sitting quietly in my presence, and yet you haven't acknowledged the goddess before you.\n\n*Don't stay silent now when you know exactly how to address me.*", "https://i.imgur.com/MHIPpcn.png"),
        ("I know you're there, quiet in my presence, fully aware of the goddess before you—your silence is already an answer, but I expect you to speak.\n\n*Don't stay silent now when you know exactly how to address me.*", "https://i.imgur.com/MHIPpcn.png"),
        ("You're sitting there, feeling my presence without question, and yet you haven't acknowledged the goddess who stands above you.\n\n*Don't stay silent now when you know exactly how to address me.*", "https://i.imgur.com/MHIPpcn.png"),
        ("I like watching you play my programs, seeing where your attention lingers and what you're willing to give up for it. There's something amusing about the way you pretend it's just curiosity, just a little spending here and there, when I can see how easily you indulge. I don't push—you do that all on your own. I simply notice, quietly pleased, as you decide what I'm worth to you.\n\n*Don't stay silent now when you know exactly how to address me.*", "https://i.imgur.com/xd9HPMa.png", 0.05),  # 5% chance
        ("I enjoy watching how easily you commit when something belongs to me. You open my programs, you stay longer than you intended, and you spend without needing to be told—because you want to. I see the satisfaction in that choice, the quiet thrill of giving value to something you respect. It isn't about taking from you; it's about watching you decide what I'm worth, again and again. That certainty never surprises me. It's exactly how this was always going to go.\n\n*Don't stay silent now when you know exactly how to address me.*", "https://i.imgur.com/4qnFaHF.png", 0.005),  # 0.5% chance
    ]
    # Weighted random selection
    rand = random.random()
    if rand < 0.005:
        return variations[4]  # 0.5% chance
    elif rand < 0.05:
        return variations[3]  # 5% chance
    else:
        return random.choice(variations[:3])  # Equal chance for first 3

def choose_collective_question():
    """Choose random question for Event 7 Phase 2."""
    questions = [
        ("What program does Isla Rebrand affect?", "steam"),
        ("What's the main theme of Isla Hearts?", ["level drain", "draining level", "draining levels"]),
        ("What's Isla's most extreme file?", "islaware"),
        ("What was Isla's first program?", ["islaexe", "isla.exe"]),
        ("When did IslaOS 2.0 launch?", ["13/12/2025", "12/13/2025"]),
        ("How much does rebrand cost?", "$15"),
        ("How much is islahearts?", "$20"),
        ("How much does islaware cost?", "$30"),
        ("What is the price of slots?", "$20"),
        ("What does isla.exe cost?", "$15"),
        ("What year did isla begin?", "2025"),
        ("What month was isla founded?", "july"),
        ("What is my favorite drink?", ["dr pepper", "drpepper", "dr.pepper"]),
        ("What is my favorite color?", "red"),
        ("What is my favorite anime?", "one piece"),
        ("What is my favorite anime character?", "makima"),
        ("What gaming genre do i enjoy most?", ["horror", "rpg"]),
        ("What platform does isla.exe use?", "windows"),
        ("What is the nickname I gave you?", ["dogs", "pups", "puppies", "dog", "pup", "puppy"]),
        ("What title do i prefer?", "goddess"),
        ("What time do i usually appear?", "midnight"),
        ("What word do i repeat often?", "send"),
    ]
    # Use secrets.choice for cryptographically secure random selection
    return secrets.choice(questions)

async def check_event7_phase1_threshold(state):
    """Check Event 7 Phase 1 threshold after 1 minute."""
    await asyncio.sleep(60)  # Wait 1 minute
    global active_event
    
    if active_event != state or state.get("phase") != 1:
        return
    
    reactor_count = len(state.get("reactors", set()))
    if reactor_count >= COLLECTIVE_THRESHOLD and not state.get("threshold_reached"):
        guild = bot.get_guild(state["guild_id"])
        if not guild:
            return
        
        channel = guild.get_channel(state["channel_id"])
        if not channel:
            return
        
        try:
            event_message = await channel.fetch_message(state["message_id"])
            embed = discord.Embed(
                description="*Good. I have what I need.\nThe door is open—for those who kept up.*",
                color=0xff000d,
            )
            await event_message.reply(embed=embed)
            state["threshold_reached"] = True
            print(f"Event 7 Phase 1: {reactor_count} reactions after 1 minute - threshold reached")
            # Escalate to Phase 2
            await escalate_collective_event(guild)
        except Exception as e:
            print(f"Failed to send Event 7 Phase 1 threshold message: {e}")

async def end_event4_phase1(state):
    """End Event 4 Phase 1 after 1 minute and start Phase 2."""
    await asyncio.sleep(60)  # 1 minute
    global active_event
    if active_event != state:
        return
    
    guild = bot.get_guild(state["guild_id"])
    if not guild:
        return
    
    # Start Phase 2
    await start_event4_phase2(guild, state)

async def start_event4_phase2(guild, state):
    """Start Event 4 Phase 2 - send messages to Woof and Meow channels."""
    global active_event
    if active_event != state:
        return
    
    state["phase"] = 2
    state["phase2_started"] = True
    state["answered"] = set()  # Track who has answered in Phase 2
    
    # Send message to Woof channel
    woof_channel = guild.get_channel(EVENT_4_WOOF_CHANNEL_ID)
    if woof_channel:
        try:
            woof_embed = build_event_embed("*Who's a good puppy?*", "https://i.imgur.com/yHTrhB4.png")
            await woof_channel.send("@everyone", embed=woof_embed)
            print(f"Event 4 Phase 2: Sent message to Woof channel")
        except Exception as e:
            print(f"Failed to send Event 4 Phase 2 message to Woof channel: {e}")
    
    # Send message to Meow channel
    meow_channel = guild.get_channel(EVENT_4_MEOW_CHANNEL_ID)
    if meow_channel:
        try:
            meow_embed = build_event_embed("*Who's a good kitty?*", "https://i.imgur.com/JfoxREn.png")
            await meow_channel.send("@everyone", embed=meow_embed)
            print(f"Event 4 Phase 2: Sent message to Meow channel")
        except Exception as e:
            print(f"Failed to send Event 4 Phase 2 message to Meow channel: {e}")

async def end_event7_phase2(state):
    """End Event 7 Phase 2 after 1 minute."""
    await asyncio.sleep(60)  # 1 minute
    global active_event
    if active_event != state:
        return
    
    guild = bot.get_guild(state["guild_id"])
    if not guild:
        return
    
    # Remove opt-in role from all users who have it
    opt_in_role = guild.get_role(EVENT_7_OPT_IN_ROLE)
    if opt_in_role:
        for member in guild.members:
            if opt_in_role in member.roles:
                try:
                    await member.remove_roles(opt_in_role, reason="Event 7 Phase 2 ended")
                    print(f"  ↳ Removed opt-in role from {member.name}")
                except Exception as e:
                    print(f"  ↳ Failed to remove opt-in role from {member.name}: {e}")
    
    # Phase 2 ended, now start Phase 3
    await handle_event7_phase3(guild, state)

async def end_event7_phase3(state):
    """End Event 7 Phase 3 after 2 minutes and remove Phase 3 roles."""
    await asyncio.sleep(120)  # 2 minutes
    global active_event, event_cooldown_until
    if active_event != state:
        return
    
    guild = bot.get_guild(state["guild_id"])
    if guild:
        # Remove Phase 3 roles (success and failed roles)
        success_role = guild.get_role(EVENT_7_SUCCESS_ROLE)
        failed_role = guild.get_role(EVENT_7_FAILED_ROLE)
        
        if success_role:
            for member in guild.members:
                if success_role in member.roles:
                    try:
                        await member.remove_roles(success_role, reason="Event 7 Phase 3 ended")
                        print(f"  ↳ Removed success role from {member.name}")
                    except Exception as e:
                        print(f"  ↳ Failed to remove success role from {member.name}: {e}")
        
        if failed_role:
            for member in guild.members:
                if failed_role in member.roles:
                    try:
                        await member.remove_roles(failed_role, reason="Event 7 Phase 3 ended")
                        print(f"  ↳ Removed failed role from {member.name}")
                    except Exception as e:
                        print(f"  ↳ Failed to remove failed role from {member.name}: {e}")
    
    # End the event
    active_event = None
    event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=EVENT_COOLDOWN_SECONDS)
    print("Event 7 Phase 3 ended")
    
    # Clear event roles when no events are active
    await clear_event_roles()

async def start_obedience_event(ctx_or_guild, event_type: int, channel=None):
    """Start an obedience event (1-7). Only one can run at a time.
    Can accept either a context object, interaction object, or a guild object with optional channel."""
    global active_event, event_cooldown_until, events_enabled
    
    # Check if events are enabled (manual commands can still run)
    is_manual_command = hasattr(ctx_or_guild, 'send') or hasattr(ctx_or_guild, 'response')
    if not events_enabled and not is_manual_command:
        # Automated events are disabled, but manual commands can still run
        return
    
    # Check if this is a manual command (has 'send' method = context object, or 'response' = interaction)
    
    if active_event:
        if is_manual_command:
            if hasattr(ctx_or_guild, 'response'):
                await ctx_or_guild.response.send_message("An obedience event is already running.", ephemeral=True)
            elif hasattr(ctx_or_guild, 'send'):
                await ctx_or_guild.send("An obedience event is already running.")
        return
    
    # Manual commands can override cooldown, automated events cannot
    if event_cooldown_until and datetime.datetime.now(datetime.UTC) < event_cooldown_until:
        if is_manual_command:
            # Manual command overrides cooldown - clear it and set new 30-minute cooldown
            event_cooldown_until = None
            print("Manual event command overrode cooldown")
            if hasattr(ctx_or_guild, 'response'):
                await ctx_or_guild.response.send_message("✅ Manual event command - cooldown overridden.", ephemeral=True, delete_after=3)
            elif hasattr(ctx_or_guild, 'send'):
                await ctx_or_guild.send("✅ Manual event command - cooldown overridden.", delete_after=3)
            # Immediately set 30-minute cooldown to prevent scheduler from starting other events
            event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=1800)
            print(f"⏰ Manual event cooldown set: No other events will start for 30 minutes (until {event_cooldown_until.strftime('%H:%M:%S UTC')})")
        else:
            # Automated event respects cooldown
            return
    elif is_manual_command:
        # Manual command when no cooldown is active - set 30-minute cooldown immediately
        event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=1800)
        print(f"⏰ Manual event cooldown set: No other events will start for 30 minutes (until {event_cooldown_until.strftime('%H:%M:%S UTC')})")
    
    # Get guild and event channel
    if hasattr(ctx_or_guild, 'guild'):
        guild = ctx_or_guild.guild
    else:
        guild = ctx_or_guild
    
    event_channel = channel or guild.get_channel(EVENT_CHANNEL_ID)
    if not event_channel:
        if hasattr(ctx_or_guild, 'response'):
            await ctx_or_guild.response.send_message(f"Event channel not found (ID: {EVENT_CHANNEL_ID})", ephemeral=True)
        elif hasattr(ctx_or_guild, 'send'):
            await ctx_or_guild.send(f"Event channel not found (ID: {EVENT_CHANNEL_ID})")
        print(f"Event channel not found (ID: {EVENT_CHANNEL_ID})")
        return
    
    # For manual Tier 3 events, send pre-announcement first
    event_tier = EVENT_TIER_MAP.get(event_type)
    if is_manual_command and event_tier == 3:
        try:
            await send_tier3_pre_announcement(guild)
            await asyncio.sleep(60)  # Wait 1 minute before sending actual event message
        except Exception as e:
            print(f"Failed to send Tier 3 pre-announcement: {e}")
    
    # Get prompt and image
    prompt, image_url = event_prompt(event_type)
    
    embed = build_event_embed(prompt, image_url)
    
    # Add footer for Event 1
    if event_type == 1:
        embed.set_footer(text="Double XP for 5 minutes")
    
    # Add footer for Event 2
    if event_type == 2:
        embed.set_footer(text="Join Voice Chat for XP")
    
    # Add footer for Event 3
    if event_type == 3:
        embed.set_footer(text="React for XP")
    
    # Send with @everyone mention
    try:
        message = await event_channel.send("@everyone", embed=embed)
    except Exception as e:
        if hasattr(ctx_or_guild, 'response'):
            await ctx_or_guild.response.send_message(f"Failed to send event message: {e}", ephemeral=True)
        elif hasattr(ctx_or_guild, 'send'):
            await ctx_or_guild.send(f"Failed to send event message: {e}")
        print(f"Failed to send event message: {e}")
        return

    state = {
        "type": event_type,
        "channel_id": event_channel.id,
        "guild_id": guild.id,
        "message_id": message.id,
        "started_at": datetime.datetime.now(datetime.UTC),
        "phase": 1,
        "participants": set(),
        "reactors": set(),
        "message_cooldowns": {},  # For Event 1 per-user cooldown
    }

    # Event-specific setup
    if event_type == 2:  # Silent Company
        # Track who is in VC from the start
        join_times = {}
        for vc_id in EVENT_2_VC_CHANNELS:
            vc = guild.get_channel(vc_id)
            if vc:
                for member in vc.members:
                    if member.bot or any(int(r.id) in EXCLUDED_ROLE_SET for r in member.roles):
                        continue
                    join_times[member.id] = state["started_at"]
        state["join_times"] = join_times
        
        # Bot joins the voice channel (use first/only channel in list)
        if EVENT_2_VC_CHANNELS:
            vc_id = EVENT_2_VC_CHANNELS[0]  # Use the specific channel
            vc = guild.get_channel(vc_id)
            if vc:
                try:
                    # Disconnect from any existing voice connection first
                    if guild.voice_client:
                        try:
                            if guild.voice_client.is_playing():
                                guild.voice_client.stop()
                            await guild.voice_client.disconnect()
                            print(f"Disconnected from existing voice connection before joining Event 2 VC")
                            await asyncio.sleep(0.5)  # Brief pause before reconnecting
                        except Exception as e:
                            print(f"Error disconnecting from existing VC: {e}")
                    
                    # Join the voice channel
                    print(f"Attempting to join voice channel {vc_id} ({vc.name})")
                    voice_client = await vc.connect()
                    state["bot_vc"] = vc_id
                    state["voice_client"] = voice_client
                    print(f"✅ Successfully joined voice channel {vc.name} (ID: {vc_id})")
                    
                    # Play audio file (supports both local path or URL)
                    audio_source_path = EVENT_2_AUDIO
                    
                    if not audio_source_path:
                        print("❌ EVENT_2_AUDIO not configured. Set EVENT_2_AUDIO environment variable to a URL for cloud hosting.")
                    else:
                        # Check if it's a local file or URL
                        is_url = audio_source_path.startswith(('http://', 'https://'))
                        is_local_file = not is_url and os.path.exists(audio_source_path)
                        
                        if is_url or is_local_file:
                            try:
                                print(f"Loading audio source: {audio_source_path}")
                                audio_source = FFmpegPCMAudio(audio_source_path)
                                voice_client.play(audio_source, after=lambda e: print(f"Audio finished playing. Error: {e}" if e else "Audio finished playing."))
                                print(f"✅ Playing audio: {audio_source_path}")
                                print(f"Voice client playing status: {voice_client.is_playing()}")
                            except Exception as e:
                                print(f"❌ Failed to play audio: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print(f"❌ Audio file not found or invalid URL: {audio_source_path}")
                            print("For Wispbyte hosting, set EVENT_2_AUDIO environment variable to a URL")
                except discord.errors.ClientException as e:
                    print(f"❌ ClientException when joining VC: {e}")
                    # Try to disconnect and reconnect
                    try:
                        if guild.voice_client:
                            await guild.voice_client.disconnect()
                        await asyncio.sleep(1)
                        voice_client = await vc.connect()
                        state["bot_vc"] = vc_id
                        state["voice_client"] = voice_client
                        print(f"✅ Reconnected to voice channel after error")
                    except Exception as retry_e:
                        print(f"❌ Failed to reconnect: {retry_e}")
                except Exception as e:
                    print(f"❌ Failed to join VC: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"❌ Voice channel not found (ID: {vc_id})")
        else:
            print("❌ EVENT_2_VC_CHANNELS is empty - no voice channel configured")
    
    elif event_type == 3:  # Hidden Reaction
        # Track heart emoji reactions
        state["heart_emojis"] = ["❤️", "🧡", "💛", "💚", "💙", "💜", "🤎", "🖤", "🤍", "💔", "❤️‍🔥", "❤️‍🩹", "💕", "💞", "💓", "💗", "💖", "💘", "💝", "💟", "❣️", "💌", "🫀"]
    
    elif event_type == 4:  # Keyword Prompt - 2 Phase Event
        state["woof_users"] = set()
        state["meow_users"] = set()
        state["phase2_started"] = False
        
        # Add Woof and Meow buttons for Phase 1
        class Event4ChoiceView(discord.ui.View):
            def __init__(self, event_state):
                super().__init__(timeout=300)  # 5 minutes
                self.event_state = event_state
            
            @discord.ui.button(label="Woof", style=discord.ButtonStyle.danger, emoji=None)
            async def woof_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                global active_event
                
                if not active_event or active_event != self.event_state:
                    await interaction.response.send_message("This event has ended.", ephemeral=True)
                    return
                
                user_id = interaction.user.id
                if user_id in self.event_state.get("woof_users", set()) or user_id in self.event_state.get("meow_users", set()):
                    await interaction.response.send_message("You've already chosen.", ephemeral=True)
                    return
                
                await interaction.response.defer(ephemeral=True)
                
                # Add to woof users
                self.event_state.setdefault("woof_users", set()).add(user_id)
                
                # Assign Woof role
                guild = interaction.guild
                member = guild.get_member(user_id) or interaction.user
                if isinstance(member, discord.Member):
                    woof_role = guild.get_role(EVENT_4_WOOF_ROLE)
                    if woof_role and woof_role not in member.roles:
                        try:
                            await member.add_roles(woof_role, reason="Event 4 Phase 1 - Woof choice")
                            print(f"✅ Assigned Woof role to {member.name}")
                        except Exception as e:
                            print(f"Failed to assign Woof role: {e}")
                
                await interaction.followup.send("Good choice.", ephemeral=True)
            
            @discord.ui.button(label="Meow", style=discord.ButtonStyle.danger, emoji=None)
            async def meow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                global active_event
                
                if not active_event or active_event != self.event_state:
                    await interaction.response.send_message("This event has ended.", ephemeral=True)
                    return
                
                user_id = interaction.user.id
                if user_id in self.event_state.get("woof_users", set()) or user_id in self.event_state.get("meow_users", set()):
                    await interaction.response.send_message("You've already chosen.", ephemeral=True)
                    return
                
                await interaction.response.defer(ephemeral=True)
                
                # Add to meow users
                self.event_state.setdefault("meow_users", set()).add(user_id)
                
                # Assign Meow role
                guild = interaction.guild
                member = guild.get_member(user_id) or interaction.user
                if isinstance(member, discord.Member):
                    meow_role = guild.get_role(EVENT_4_MEOW_ROLE)
                    if meow_role and meow_role not in member.roles:
                        try:
                            await member.add_roles(meow_role, reason="Event 4 Phase 1 - Meow choice")
                            print(f"✅ Assigned Meow role to {member.name}")
                        except Exception as e:
                            print(f"Failed to assign Meow role: {e}")
                
                await interaction.followup.send("Good choice.", ephemeral=True)
        
        view = Event4ChoiceView(state)
        await message.edit(view=view)
        state["view"] = view
        
        # Start 1-minute timer for Phase 2
        asyncio.create_task(end_event4_phase1(state))
    
    elif event_type == 6:  # Choice Event
        # Add buttons (both are 🖤)
        winning_choice = random.choice(["choice_1", "choice_2"])
        state["winning"] = winning_choice
        state["handled"] = set()
        
        class ChoiceEventView(discord.ui.View):
            def __init__(self, event_state, winning):
                super().__init__(timeout=300)
                self.event_state = event_state
                self.winning = winning
            
            @discord.ui.button(label="", style=discord.ButtonStyle.danger, emoji="🖤", custom_id="choice_1")
            async def choice_1_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.handle_choice(interaction, "choice_1")
            
            @discord.ui.button(label="", style=discord.ButtonStyle.danger, emoji="🖤", custom_id="choice_2")
            async def choice_2_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.handle_choice(interaction, "choice_2")
            
            async def handle_choice(self, interaction: discord.Interaction, choice: str):
                user_id = interaction.user.id
                if user_id in self.event_state.get("handled", set()):
                    await interaction.response.send_message("You've already chosen.", ephemeral=True)
                    return
                
                self.event_state.setdefault("handled", set()).add(user_id)
                member = interaction.user
                is_winning = (choice == self.winning)
                
                if is_winning:
                    increment_event_participation(user_id)
                    await add_xp(user_id, EVENT_REWARDS[6]["win"], member=member)
                    await interaction.response.send_message("Good choice.", ephemeral=True)
                else:
                    increment_event_participation(user_id)
                    await add_xp(user_id, EVENT_REWARDS[6]["lose"], member=member)
                    await interaction.response.send_message("Wrong choice.", ephemeral=True)
        
        view = ChoiceEventView(state, winning_choice)
        await message.edit(view=view)
        state["view"] = view
    
    elif event_type == 7:  # Collective Event
        state["reactors"] = set()
        state["answered"] = set()
        state["question"] = None
        state["question_answer"] = None
        state["question_answers"] = []  # List of accepted answers
        state["threshold_reached"] = False
        state["phase2_message_id"] = None
        
        # Add red "Woof" button for Phase 1
        class Event7WoofButtonView(discord.ui.View):
            def __init__(self, event_state):
                super().__init__(timeout=300)  # 5 minutes
                self.event_state = event_state
            
            @discord.ui.button(label="Woof", style=discord.ButtonStyle.danger, emoji=None)
            async def woof_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                global active_event
                
                # Respond immediately to avoid interaction timeout
                try:
                    if not active_event or active_event != self.event_state:
                        await interaction.response.send_message("This event has ended.", ephemeral=True)
                        return
                    
                    user_id = interaction.user.id
                    if user_id in self.event_state.get("reactors", set()):
                        await interaction.response.send_message("You've already participated.", ephemeral=True)
                        return
                    
                    # Defer response immediately to prevent timeout
                    await interaction.response.defer(ephemeral=True)
                    
                    # Add to reactors
                    self.event_state.setdefault("reactors", set()).add(user_id)
                    
                    # Award XP and role (do this after responding)
                    guild = interaction.guild
                    # Ensure we have a Member object, not just User
                    member = guild.get_member(user_id) or interaction.user
                    if not isinstance(member, discord.Member):
                        # Try to fetch member if not available
                        try:
                            member = await guild.fetch_member(user_id)
                        except:
                            print(f"⚠️ Could not fetch member {user_id}, using User object")
                    
                    # Award XP
                    increment_event_participation(user_id)
                    await add_xp(user_id, EVENT_REWARDS[7]["phase1"], member=member)
                    
                    # Assign opt-in role
                    role = guild.get_role(EVENT_7_OPT_IN_ROLE)
                    if role:
                        if role not in member.roles:
                            try:
                                await member.add_roles(role, reason="Event 7 Phase 1 participation")
                                print(f"✅ Assigned role {role.name} (ID: {EVENT_7_OPT_IN_ROLE}) to {member.name}")
                            except Exception as e:
                                print(f"❌ Failed to assign role {EVENT_7_OPT_IN_ROLE} to {member.name}: {e}")
                        else:
                            print(f"ℹ️ User {member.name} already has role {role.name}")
                    else:
                        print(f"❌ Role {EVENT_7_OPT_IN_ROLE} not found in guild")
                    
                    # Send follow-up message
                    await interaction.followup.send("Good puppy.", ephemeral=True)
                    
                    # Check threshold after 1 minute
                    reactor_count = len(self.event_state.get("reactors", set()))
                    if reactor_count >= COLLECTIVE_THRESHOLD:
                        # Check if 1 minute has passed since event started
                        started_at = self.event_state.get("started_at")
                        if started_at:
                            time_elapsed = (datetime.datetime.now(datetime.UTC) - started_at).total_seconds()
                            if time_elapsed >= 60 and not self.event_state.get("threshold_reached"):
                                self.event_state["threshold_reached"] = True
                                await escalate_collective_event(guild)
                except discord.errors.NotFound:
                    # Interaction already expired or responded to
                    print(f"⚠️ Interaction expired for user {interaction.user.name}")
                except Exception as e:
                    print(f"❌ Error in woof_button callback: {e}")
                    try:
                        await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
                    except:
                        pass
        
        view = Event7WoofButtonView(state)
        await message.edit(view=view)
        state["view"] = view
        
        # Start 1-minute check for threshold
        asyncio.create_task(check_event7_phase1_threshold(state))

    # Note: Manual events don't affect scheduled times tracking
    # The scheduled times are only for automated events
    if is_manual_command:
        print(f"Manual event {event_type} started")

    active_event = state
    asyncio.create_task(end_obedience_event(state))

async def end_obedience_event(state):
    """Conclude an event after duration."""
    await asyncio.sleep(EVENT_DURATION_SECONDS)
    global active_event, event_cooldown_until
    if active_event != state:
        return  # superseded
    guild = bot.get_guild(state["guild_id"])
    if not guild:
        active_event = None
        return

    event_type = state["type"]
    channel = guild.get_channel(state["channel_id"])
    rewarded_users = set()

    # Event 2: Bot leaves VC, reward users who stayed
    if event_type == 2:
        # Bot leaves voice channel
        voice_client = state.get("voice_client") or guild.voice_client
        if voice_client:
            try:
                # Stop audio if playing
                if voice_client.is_playing():
                    voice_client.stop()
                await voice_client.disconnect()
                print("Bot disconnected from voice channel and stopped audio")
            except Exception as e:
                print(f"Failed to disconnect from VC: {e}")
        
        # Reward users who stayed the full duration with 50 XP bonus
        reward = EVENT_REWARDS[2]  # 50 XP bonus
        now = datetime.datetime.now(datetime.UTC)
        join_times = state.get("join_times", {})
        for vc_id in EVENT_2_VC_CHANNELS:
            vc = guild.get_channel(vc_id)
            if vc:
                for member in vc.members:
                    if member.bot or any(int(r.id) in EXCLUDED_ROLE_SET for r in member.roles):
                        continue
                    if member.id in join_times:
                        if (now - join_times[member.id]).total_seconds() >= EVENT_DURATION_SECONDS:
                            rewarded_users.add(member.id)
                            increment_event_participation(member.id)
                            await add_xp(member.id, reward, member=member)
                            print(f"  ↳ ✅ Event 2: Awarded {reward} XP bonus to {member.name} for staying in VC")
    
    # Event 4: Send ending message (no punishment - 2-phase event)
    elif event_type == 4:
        # Ending message
        if channel:
            embed = build_event_embed(
                "Seems like everyone here knows their place. Good.",
                "https://i.imgur.com/DrPzPo8.png"
            )
            await channel.send("@here", embed=embed)
    
    # Event 5: Send ending message, handle sorry replies, punish non-participants
    elif event_type == 5:
        rewarded_users = set(state["participants"])
        # Ending message
        if channel:
            embed = build_event_embed(
                "I'm aware of everyone who answered. Good. \n\nAnd for the rest..\nThey made their choice.",
                "https://i.imgur.com/DrPzPo8.png"
            )
            await channel.send("@here", embed=embed)
        
        # Punish non-participants
        all_members = set(m.id for m in guild.members if not m.bot and not any(int(r.id) in EXCLUDED_ROLE_SET for r in m.roles))
        non_participants = all_members - rewarded_users
        for uid in non_participants:
            member = guild.get_member(uid)
            if member:
                await add_xp(uid, -20, member=member)
    
    # Event 6: Send ending message, punish non-participants
    elif event_type == 6:
        rewarded_users = set(state.get("handled", set()))  # Users who clicked buttons
        # Ending message - reply to original event message
        if channel:
            try:
                event_message = await channel.fetch_message(state["message_id"])
                embed = discord.Embed(
                    description="*I see you have made your choice.\n\nYour XP has been updated.*",
                    color=0xff000d,
                )
                await event_message.reply(embed=embed)
            except Exception as e:
                print(f"Failed to send Event 6 ending message: {e}")
        
        # Punish non-participants
        all_members = set(m.id for m in guild.members if not m.bot and not any(int(r.id) in EXCLUDED_ROLE_SET for r in m.roles))
        non_participants = all_members - rewarded_users
        for uid in non_participants:
            member = guild.get_member(uid)
            if member:
                await add_xp(uid, -20, member=member)
    
    # Event 7: Handle Phase 2 end, then Phase 3
    elif event_type == 7:
        # Phase 2 has 5 minute time limit, handled separately
        # Wait for Phase 2 to complete if it started
        if state.get("phase") == 2:
            # Phase 2 already ended, now assign roles and start Phase 3
            await handle_event7_phase3(guild, state)
        else:
            # Phase 2 never started, just end
            active_event = None
            event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=EVENT_COOLDOWN_SECONDS)
            await clear_event_roles()
            return

    # Set cooldown
    event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=EVENT_COOLDOWN_SECONDS)
    active_event = None
    
    # Clear event roles when no events are active
    await clear_event_roles()

async def handle_event7_phase3(guild, state):
    """Handle Event 7 Phase 3 - assign roles and send messages."""
    success_role = guild.get_role(EVENT_7_SUCCESS_ROLE)
    failed_role = guild.get_role(EVENT_7_FAILED_ROLE)
    
    # Get users who have success role (answered correctly in Phase 2)
    successful_users = []
    failed_users = []
    
    # Get all users who participated (those with success role or who were in answered_correctly/answered_incorrectly sets)
    answered_correctly = state.get("answered_correctly", set())
    answered_incorrectly = state.get("answered_incorrectly", set())
    all_participants = answered_correctly | answered_incorrectly
    
    for user_id in all_participants:
        member = guild.get_member(user_id)
        if not member:
            continue
        
        if user_id in answered_correctly:
            # User answered correctly - should have success role
            successful_users.append(member)
            if success_role and success_role not in member.roles:
                try:
                    await member.add_roles(success_role, reason="Event 7 Phase 2 correct answer")
                    print(f"  ↳ Assigned success role to {member.name}")
                except Exception as e:
                    print(f"  ↳ Failed to assign success role to {member.name}: {e}")
        else:
            # User answered incorrectly or didn't answer - assign failed role
            failed_users.append(member)
            if failed_role and failed_role not in member.roles:
                try:
                    await member.add_roles(failed_role, reason="Event 7 Phase 2 failure - no correct answer")
                    print(f"  ↳ Assigned failed role to {member.name}")
                except Exception as e:
                    print(f"  ↳ Failed to assign failed role to {member.name}: {e}")
    
    # Wait for all roles to be assigned
    await asyncio.sleep(2)
    
    # Mark Phase 3 as active
    state["phase"] = 3
    state["phase3_started"] = datetime.datetime.now(datetime.UTC)
    state["phase3_message_cooldowns"] = {}  # Track per-user cooldowns for Phase 3 messages
    
    # Ping roles in respective channels
    success_channel = guild.get_channel(EVENT_PHASE3_SUCCESS_CHANNEL_ID)
    failed_channel = guild.get_channel(EVENT_PHASE3_FAILED_CHANNEL_ID)
    
    if success_channel and success_role and successful_users:
        await success_channel.send(success_role.mention)
    
    if failed_channel and failed_role and failed_users:
        await failed_channel.send(failed_role.mention)
    
    # Wait 10 seconds before starting spam messages
    await asyncio.sleep(10)
    
    # Spam both channels simultaneously
    if successful_users and success_channel:
        asyncio.create_task(send_event7_phase3_success(guild, successful_users, success_role))
    if failed_users and failed_channel:
        asyncio.create_task(send_event7_phase3_failed(guild, failed_users, failed_role))
    
    # Final message (Throne message ONLY in success channel - NOT in event channel)
    throne_channel = guild.get_channel(EVENT_PHASE3_SUCCESS_CHANNEL_ID)
    if throne_channel and successful_users:
        # Double-check we're using the correct channel ID and NOT the event channel
        if throne_channel.id == EVENT_PHASE3_SUCCESS_CHANNEL_ID and throne_channel.id != EVENT_CHANNEL_ID:
            embed = build_event_embed(
                "Good puppies like to please properly. My Throne is open.\n\n◊ ¿°ᵛ˘ æ¢ɲ≥[Throne](https://throne.com/lsla/item/1230a476-4752-4409-9583-9313e60686fe) Әᵛæ´. ✁æ ˘ɲ±æ≤ ┍ææ≥, \"˘æ\"¿˘, Әɲ≥",
                "https://i.imgur.com/Yti9Kss.png"
            )
            await throne_channel.send(embed=embed)
            print(f"✅ Sent Phase 3 throne message to success channel {throne_channel.id} ({throne_channel.name})")
        else:
            print(f"❌ ERROR: Throne channel ID mismatch! Expected {EVENT_PHASE3_SUCCESS_CHANNEL_ID}, got {throne_channel.id}. NOT sending to prevent wrong channel.")
    
    # Phase 3 lasts 2 minutes, then remove roles and end the event
    asyncio.create_task(end_event7_phase3(state))

async def send_event7_phase3_failed(guild, failed_users, failed_role):
    """Send Phase 3 failed messages."""
    channel = guild.get_channel(EVENT_PHASE3_FAILED_CHANNEL_ID)
    if not channel:
        return
    
    # Ping the role at the start
    if failed_role:
        await channel.send(failed_role.mention)
        await asyncio.sleep(1)
    
    quote_variations = [
        "Look at you. Still trying.",
        "You really don't get it, do you?",
        "It's almost impressive how little goes on in your head.",
        "I expected nothing—and somehow you still fell short.",
        "You're adorable when you think you matter.",
        "This is why I don't explain things to you.",
        "So earnest. So slow.",
        "You should stop thinking. It's clearly not your strength.",
        "I don't need to correct you. You embarrass yourself just fine.",
        "You exist exactly where you belong—below me.",
    ]
    
    image_variations = [
        "https://i.imgur.com/wL9CM6q.gif",
        "https://i.imgur.com/waRLVv1.gif",
        "https://i.imgur.com/gvhIpAG.gif",
        "https://i.imgur.com/DP8dXq4.gif",
        "https://i.imgur.com/vBE53cR.gif",
        "https://i.imgur.com/89yIXiY.gif",
    ]
    
    text_variations = [
        "ᕕɲ≤ ϐæ¢´ˆ˘ æ┍ µӘ\"\"°ɲ˘ϐϐ ≤æ¢ ˘Ø\"˘´°˘ɲˆ˘? ◊'¿¿ 𝈇˘ ıµ˘ æɲ˘ ıæ ˆ´˘Әı˘ Әɲ≥ ≥˘ϐı´æ≤ °ı Ә¿¿. øæ¢ µ˘¿\"˘≥ ›˘ «°¿¿ `æ†˘´. ✁µ˘´˘ ›°𝖡µı µӘᵛ˘ 𝈇˘˘ɲ Ә †Ә≤ ┍æ´ ≤æ¢ ıæ ϐӘᵛ˘ œӘ≤Ә«Ә†Ә, 𝈇¢ı ≤æ¢ «°¿¿˘≥ µ°› ıææ. øæ¢ ˘ᵛ˘ɲ ›¢´≥˘´˘≥ ≤æ¢´ æ†ɲ ┍Әıµ˘´. ¥æ›˘æɲ˘ ¿°«˘ ≤æ¢ µӘϐ ɲæ ´°𝖡µı ıæ †°ϐµ ┍æ´ Ә ɲæ´›Ә¿ ¿°┍˘, ≥æ ıµ˘≤?",
        "\"◊ ¿æᵛ˘ µæ† ˆæɲ┍°≥˘ɲı ≤æ¢ Ә´˘ ┍æ´ ϐæ›˘æɲ˘ ϐæ †´æɲ𝖡.\"",
        "\"𝞜Әıˆµ°ɲ𝖡 ≤æ¢ ϐı´¢𝖡𝖡¿˘ °ϐ… ´˘¿ӘØ°ɲ𝖡.\"",
        "\"◊ı'ϐ ˆ¢ı˘ ıµӘı ≤æ¢ «˘˘\" µæ\"°ɲ𝖡 ┍æ´ Ә\"\"´æᵛӘ¿.\"",
        # ... (other text variations from the spec)
    ]
    
    # Send 3 embed messages with quotes and images (no @everyone)
    used_quotes = []
    used_images = []
    for i in range(3):
        quote = random.choice([q for q in quote_variations if q not in used_quotes])
        image = random.choice([img for img in image_variations if img not in used_images])
        used_quotes.append(quote)
        used_images.append(image)
        embed = build_event_embed(quote, image)
        await channel.send(embed=embed)
        await asyncio.sleep(1)
    
    # Send 12 text variation messages
    used_texts = []
    for i in range(12):
        text = random.choice([t for t in text_variations if t not in used_texts])
        used_texts.append(text)
        embed = build_event_embed(text)
        await channel.send("@everyone", embed=embed)
        await asyncio.sleep(1)
        
        # Every 2 messages, ping 5 random users
        if (i + 1) % 2 == 0 and failed_users:
            random_users = random.sample(failed_users, min(5, len(failed_users)))
            mentions = " ".join([u.mention for u in random_users])
            await channel.send(mentions)
            await asyncio.sleep(1)

async def send_event7_phase3_success(guild, successful_users, success_role):
    """Send Phase 3 success messages."""
    channel = guild.get_channel(EVENT_PHASE3_SUCCESS_CHANNEL_ID)
    if not channel:
        return
    
    # Ping the role at the start
    if success_role:
        await channel.send(success_role.mention)
        await asyncio.sleep(1)
    
    quote_variations = [
        "Good… you earned this. Look closely—I don't show just anyone.",
        "Mmm. I like when you get it right. Consider this a small glimpse.",
        "See? Obedience has its rewards. Don't look away.",
        "That's exactly what I wanted. I think you deserve a peek.",
        "You did so well… I'll let you see a little more than usual.",
        "Good. Now be still and appreciate what I chose to show you.",
        "I knew you could do it. I dressed with you in mind.",
        "Such a good response. This part is just for you.",
    ]
    
    image_variations = [
        "https://i.imgur.com/N3Kgds9.png",
        "https://i.imgur.com/8clTMgf.png",
        "https://i.imgur.com/bUqMhNf.png",
        "https://i.imgur.com/RyaBdLX.png",
        "https://i.imgur.com/wKntHsw.png",
        "https://i.imgur.com/iYWsSs5.png",
        "https://i.imgur.com/UlCCKu5.png",
        "https://i.imgur.com/Zu9U3CL.png",
        "https://i.imgur.com/eWRtWKc.png",
        "https://i.imgur.com/GcH758a.png",
    ]
    
    text_variations = [
        "᲼᲼\nS̵̛̳̜͕͓͎͚̹̯̟͔̃͌̉͠ȯ̵͕̣͊͛̓̅̆̊̉͌̚͘͝m̶̢̨͍̺͖̩̼͇̪̰̮͐͋̑̆̓͐̀ͅè̸̡̢̤̺̩̠̼̲̖̰̫̼̜̊̽͗̉̇̑ṭ̷̨̛̦̘̻̙̼̪̩̫̖̘͋́̎̄͌̓̕͝h̸̩̪̘̯͉̮̩̼̬͕͂̂̄i̷̡̨̨̫̳̟͍͎̟̯͉̳̞̩̓̄͆͛̕n̴̲͔͎̊̅͂̀͒̔̈́̆͂̾͠g̸̨̢̩̳̣͔̹͇̩͚̺̳͕̣͕͋̍̈́̾̓͊̄̿̓͝ ̸͔͚̟̪̺̝̳̻͍̺̟͛̀́̀̍́̋͜͜͜͝ï̵̪̘̦̬͎̗͊̊͊̍̂̊s̷̤̰̳͇̰̥̹͖̤̼͌̃͑̾̒͗͑̓̅́͑̚̚͜ ̷̡̡̼̻̳̻̠̯̜̘͇̟̠̱̖̎́̀̔̍͂̇̄̏̈́ơ̵̧̘̮̊̽̑̆̎̿̂̍̋͑̈́͘n̶̘̞̺̫̭̩̜̜͎̈́̓̋̓̾͊̇̆́͂̍̐͠ ̵̱̊̕͠t̷̛͙̗͍̩̞̥̹͂̾͋̅̀̄̉̐͐̈́̂͘͠h̴̼͍̙̬͖̍̄̓̀e̴̢̛̅͒͊̽͐̚͝ ̴̨̛̭̱̖̜̣̝̝̓̅̓̀̈́̉̿͂̆̂͂͜͝͝ẃ̴̭̗̳̳̳͂͗̇̍̿͑a̶͚͚͕̠̳̭̘͐̍ÿ̷̛̫͕̘͍́̽̿̚.̶̳͍̩̇̊͜.̷̜̼̼̌͐̔.̶̧̨̩̳̮̟̖͈̘͕̻̣̱̎͒̀̈́͘\n\n◊ ¿°ᵛ˘ æ¢ɲæ ˘ɲ±æ≤ ┍ææ≥, \"˘æ\"¿˘, Әɲ≥",
        "◊ ¿æᵛ˘ µæ† ˆæɲ┍°≥˘ɲı ≤æ¢ Ә´˘ ┍æ´ ϐæ›˘æɲ˘ ϐæ †´æɲ𝖡. ◊'¿¿ 𝈇˘ ıµ˘ æɲ˘ ıæ ˆ´˘Әı˘ Әɲ≥ ≥˘ϐı´æ≤ °ı Ә¿¿.",
        "𝞜Әıˆµ°ɲ𝖡 ≤æ¢ ϐı´¢𝖡𝖡¿˘ °ϐ… ´˘¿ӘØ°ɲ𝖡. ◊ı'ϐ ˆ¢ı˘ ıµӘı ≤æ¢ «˘˘\" µæ\"°ɲ𝖡 ┍æ´ Ә\"\"´æᵛӘ¿.",
        "◊ ¿°ᵛ˘ æ¢ɲ≥ Әᵛæ´. ✁æ ˘ɲ±æ≤ ┍ææ≥, \"˘æ\"¿˘, Әɲ≥. øæ¢ µ˘¿\"˘≥ ›˘ «°¿¿ `æ†˘´.",
        "¥æ›˘æɲ˘ ¿°«˘ ≤æ¢ µӘϐ ɲæ ´°𝖡µı ıæ †°ϐµ ┍æ´ Ә ɲæ´›Ә¿ ¿°┍˘, ≥æ ıµ˘≤?",
        "◊'¿¿ 𝈇˘ ıµ˘ æɲ˘ ıæ ˆ´˘Әı˘ Әɲ≥ ≥˘ϐı´æ≤ °ı Ә¿¿. øæ¢ ˘ᵛ˘ɲ ›¢´≥˘´˘≥ ≤æ¢´ æ†ɲ ┍Әıµ˘´.",
        "◊ ¿æᵛ˘ µæ† ˆæɲ┍°≥˘ɲı ≤æ¢ Ә´˘ ┍æ´ ϐæ›˘æɲ˘ ϐæ †´æɲ𝖡. ✁µ˘´˘ ›°𝖡µı µӘᵛ˘ 𝈇˘˘ɲ Ә †Ә≤ ┍æ´ ≤æ¢ ıæ ϐӘᵛ˘ œӘ≤Ә«Ә†Ә.",
        "𝞜Әıˆµ°ɲ𝖡 ≤æ¢ ϐı´¢𝖡𝖡¿˘ °ϐ… ´˘¿ӘØ°ɲ𝖡. 𝈇¢ı ≤æ¢ «°¿¿˘≥ µ°› ıææ.",
        "◊ı'ϐ ˆ¢ı˘ ıµӘı ≤æ¢ «˘˘\" µæ\"°ɲ𝖡 ┍æ´ Ә\"\"´æᵛӘ¿. øæ¢ µ˘¿\"˘≥ ›˘ «°¿¿ `æ†˘´.",
        "◊ ¿°ᵛ˘ æ¢ɲ≥ Әᵛæ´. ✁æ ˘ɲ±æ≤ ┍ææ≥, \"˘æ\"¿˘, Әɲ≥. ¥æ›˘æɲ˘ ¿°«˘ ≤æ¢ µӘϐ ɲæ ´°𝖡µı.",
        "◊'¿¿ 𝈇˘ ıµ˘ æɲ˘ ıæ ˆ´˘Әı˘ Әɲ≥ ≥˘ϐı´æ≤ °ı Ә¿¿. ✁µ˘´˘ ›°𝖡µı µӘᵛ˘ 𝈇˘˘ɲ Ә †Ә≤.",
        "øæ¢ ˘ᵛ˘ɲ ›¢´≥˘´˘≥ ≤æ¢´ æ†ɲ ┍Әıµ˘´. ◊ ¿æᵛ˘ µæ† ˆæɲ┍°≥˘ɲı ≤æ¢ Ә´˘ ┍æ´ ϐæ›˘æɲ˘ ϐæ †´æɲ𝖡.",
    ]
    
    # Send 3 embed messages with quotes and images (no @everyone)
    used_quotes = []
    used_images = []
    for i in range(3):
        quote = random.choice([q for q in quote_variations if q not in used_quotes])
        image = random.choice([img for img in image_variations if img not in used_images])
        used_quotes.append(quote)
        used_images.append(image)
        embed = build_event_embed(quote, image)
        await channel.send(embed=embed)
        await asyncio.sleep(1)
    
    # Send 12 text variation messages with @everyone and user mentions
    used_texts = []
    for i in range(12):
        text = random.choice([t for t in text_variations if t not in used_texts])
        used_texts.append(text)
        embed = build_event_embed(text)
        await channel.send("@everyone", embed=embed)
        await asyncio.sleep(1)
        
        # Every 2 messages, ping 5 random users
        if (i + 1) % 2 == 0 and successful_users:
            random_users = random.sample(successful_users, min(5, len(successful_users)))
            mentions = " ".join([u.mention for u in random_users])
            await channel.send(mentions)
            await asyncio.sleep(1)

async def handle_event_message(message):
    global active_event
    if not active_event:
        return
    if message.guild is None or message.guild.id != active_event["guild_id"]:
        return
    if message.author.bot:
        return
    if any(int(r.id) in EXCLUDED_ROLE_SET for r in message.author.roles):
        return
    
    event_type = active_event["type"]
    content = message.content.strip().lower()
    
    # Event 1: Presence Check - any message counts, 10s cooldown per user, 30 XP per message
    if event_type == 1:
        # No channel lock - any message in server counts
        user_id = message.author.id
        now = datetime.datetime.now(datetime.UTC)
        cooldowns = active_event.get("message_cooldowns", {})
        
        if user_id in cooldowns:
            time_since = (now - cooldowns[user_id]).total_seconds()
            if time_since < 10:
                return  # Still on cooldown
        
        cooldowns[user_id] = now
        active_event["message_cooldowns"] = cooldowns
        active_event.setdefault("participants", set()).add(user_id)
        
        # Award XP immediately
        increment_event_participation(user_id)
        await add_xp(user_id, EVENT_REWARDS[1], member=message.author)
    
    # Event 4: Keyword Prompt - Phase 2 only
    elif event_type == 4 and active_event.get("phase") == 2:
        # Only process messages in Phase 2 channels
        resolved_channel_id = resolve_channel_id(message.channel)
        user_id = message.author.id
        
        # Check if user has already answered (one-time only)
        if user_id in active_event.get("answered", set()):
            return
        
        # Check if message contains "me" (including stretched) or "I am"
        has_me = bool(re.search(r'\bme+\b', content, re.IGNORECASE))
        has_i_am = bool(re.search(r'\bi\s+am\b', content, re.IGNORECASE))
        
        if not (has_me or has_i_am):
            return  # Message doesn't contain required keywords
        
        # Check if message is in Woof channel and user has Woof role
        if resolved_channel_id == EVENT_4_WOOF_CHANNEL_ID:
            woof_role = message.guild.get_role(EVENT_4_WOOF_ROLE)
            if woof_role and woof_role in message.author.roles:
                active_event.setdefault("answered", set()).add(user_id)
                await add_xp(user_id, EVENT_REWARDS[4], member=message.author)
                # Add heart reaction
                try:
                    await message.add_reaction("❤️")
                except Exception:
                    pass
                print(f"  ↳ ✅ Event 4 Phase 2: {message.author.name} answered correctly in Woof channel (+{EVENT_REWARDS[4]} XP)")
        
        # Check if message is in Meow channel and user has Meow role
        elif resolved_channel_id == EVENT_4_MEOW_CHANNEL_ID:
            meow_role = message.guild.get_role(EVENT_4_MEOW_ROLE)
            if meow_role and meow_role in message.author.roles:
                active_event.setdefault("answered", set()).add(user_id)
                await add_xp(user_id, EVENT_REWARDS[4], member=message.author)
                # Add heart reaction
                try:
                    await message.add_reaction("❤️")
                except Exception:
                    pass
                print(f"  ↳ ✅ Event 4 Phase 2: {message.author.name} answered correctly in Meow channel (+{EVENT_REWARDS[4]} XP)")
    
    # Event 5: Direct Prompt - specific replies
    elif event_type == 5:
        accepted = ["yes", "yess", "ye", "yas", "yep", "yepy", "yeah", "yup", "yea",
                   "here", "her", "hre", "still here", "here still", "present", "with you"]
        
        # Check if any accepted word/phrase is in the message
        if any(phrase in content for phrase in accepted):
            user_id = message.author.id
            if user_id not in active_event.get("participants", set()):
                active_event.setdefault("participants", set()).add(user_id)
                increment_event_participation(user_id)
                await add_xp(user_id, EVENT_REWARDS[5], member=message.author)
                # Add heart reaction
                try:
                    await message.add_reaction("❤️")
                except Exception:
                    pass
        
        # Check for "sorry" replies - award 20 XP and reply
        if "sorry" in content:
            user_id = message.author.id
            sorry_replies = [
                "It's fine. For now.",
                "I'll allow it this time.",
                "It's fine… this once.",
                "I'll overlook it for now.",
            ]
            await add_xp(user_id, 20, member=message.author)
            try:
                await message.reply(random.choice(sorry_replies))
            except Exception:
                pass
    
    # Event 6: Choice Event - handled via buttons, no message processing needed
    
    # Event 7 Phase 2: Answer questions
    elif event_type == 7 and active_event.get("phase") == 2:
        # Use resolve_channel_id to handle threads properly
        resolved_channel_id = resolve_channel_id(message.channel)
        if resolved_channel_id == EVENT_PHASE2_CHANNEL_ID:
            user_id = message.author.id
            
            # Check if user already answered correctly (only 1 successful answer allowed)
            if user_id in active_event.get("answered_correctly", set()):
                print(f"  ↳ Event 7 Phase 2: User {message.author.name} already answered correctly")
                return  # Already answered correctly, no more attempts
            
            question_answers = active_event.get("question_answers", [])
            if not question_answers:
                print(f"  ↳ Event 7 Phase 2: No question answers configured")
                return
            
            # Normalize message content (remove stretched letters)
            def normalize_stretched(text):
                """Remove stretched letters (e.g., 'horrorrrr' -> 'horror')."""
                # Collapse consecutive identical characters to just one
                # This handles cases like "horrorrrr" -> "horror"
                if not text:
                    return text.lower()
                result = [text[0].lower()]
                for char in text[1:].lower():
                    if char != result[-1]:
                        result.append(char)
                return ''.join(result)
            
            normalized_content = normalize_stretched(content)
            
            # Check if answer matches any accepted answer (anywhere in message, case-insensitive, handles stretched letters)
            is_correct = False
            for ans in question_answers:
                if isinstance(ans, list):
                    # Check each answer in the list
                    for a in ans:
                        normalized_ans = normalize_stretched(a)
                        if normalized_ans in normalized_content:
                            is_correct = True
                            break
                elif isinstance(ans, str):
                    normalized_ans = normalize_stretched(ans)
                    if normalized_ans in normalized_content:
                        is_correct = True
                if is_correct:
                    break
            
            if is_correct:
                # User answered correctly - only allow once
                if user_id not in active_event.get("answered_correctly", set()):
                    increment_event_participation(user_id)
                    await add_xp(user_id, EVENT_REWARDS[7]["phase2_correct"], member=message.author)
                    active_event.setdefault("answered_correctly", set()).add(user_id)
                    
                    # Assign success role immediately
                    guild = message.guild
                    success_role = guild.get_role(EVENT_7_SUCCESS_ROLE)
                    if success_role and success_role not in message.author.roles:
                        try:
                            await message.author.add_roles(success_role, reason="Event 7 Phase 2 correct answer")
                            print(f"  ↳ ✅ Assigned success role to {message.author.name}")
                        except Exception as e:
                            print(f"  ↳ Failed to assign success role: {e}")
                    
                    # Add heart reaction for correct answer
                    try:
                        await message.add_reaction("❤️")
                    except Exception as e:
                        print(f"  ↳ Failed to add heart reaction: {e}")
                    print(f"  ↳ ✅ Event 7 Phase 2: {message.author.name} answered correctly (+{EVENT_REWARDS[7]['phase2_correct']} XP)")
            else:
                # User answered incorrectly - allow multiple attempts
                increment_event_participation(user_id)
                await add_xp(user_id, EVENT_REWARDS[7]["phase2_wrong"], member=message.author)
                active_event.setdefault("answered_incorrectly", set()).add(user_id)
                print(f"  ↳ ❌ Event 7 Phase 2: {message.author.name} answered incorrectly ({EVENT_REWARDS[7]['phase2_wrong']} XP)")
        else:
            print(f"  ↳ Event 7 Phase 2: Message not in phase 2 channel (resolved: {resolved_channel_id}, expected: {EVENT_PHASE2_CHANNEL_ID})")
    
    # Event 7 Phase 3: Track messages in success/failure channels
    elif event_type == 7 and active_event.get("phase") == 3:
        user_id = message.author.id
        channel_id = message.channel.id
        now = datetime.datetime.now(datetime.UTC)
        
        # Check if message is in success channel (1450329916146057266)
        if channel_id == EVENT_PHASE3_SUCCESS_CHANNEL_ID:
            # Check if user has success role
            success_role = message.guild.get_role(EVENT_7_SUCCESS_ROLE)
            if success_role and success_role in message.author.roles:
                # Check cooldown (prevent spam)
                cooldowns = active_event.get("phase3_message_cooldowns", {})
                if user_id in cooldowns:
                    time_since = (now - cooldowns[user_id]).total_seconds()
                    if time_since < 10:  # 10 second cooldown per message
                        return
                
                cooldowns[user_id] = now
                active_event["phase3_message_cooldowns"] = cooldowns
                
                # Award +20 XP
                await add_xp(user_id, 20, member=message.author)
        
        # Check if message is in failure channel (1450329944549752884)
        elif channel_id == EVENT_PHASE3_FAILED_CHANNEL_ID:
            # Check if user has failed role
            failed_role = message.guild.get_role(EVENT_7_FAILED_ROLE)
            if failed_role and failed_role in message.author.roles:
                # Check cooldown (prevent spam)
                cooldowns = active_event.get("phase3_message_cooldowns", {})
                if user_id in cooldowns:
                    time_since = (now - cooldowns[user_id]).total_seconds()
                    if time_since < 10:  # 10 second cooldown per message
                        return
                
                cooldowns[user_id] = now
                active_event["phase3_message_cooldowns"] = cooldowns
                
                # Deduct -20 XP
                await add_xp(user_id, -20, member=message.author)

async def handle_event_reaction(payload: discord.RawReactionActionEvent):
    global active_event
    if not active_event:
        return
    if payload.guild_id != active_event["guild_id"]:
        return
    if payload.user_id == bot.user.id:
        return
    
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    if any(int(r.id) in EXCLUDED_ROLE_SET for r in member.roles):
        return
    
    event_type = active_event["type"]
    
    # Event 3: Hidden Reaction - only heart emojis count
    if event_type == 3 and payload.message_id == active_event["message_id"]:
        emoji_str = str(payload.emoji)
        heart_emojis = active_event.get("heart_emojis", [])
        if emoji_str in heart_emojis:
            if payload.user_id not in active_event.get("reactors", set()):
                active_event.setdefault("reactors", set()).add(payload.user_id)
                increment_event_participation(payload.user_id)
                await add_xp(payload.user_id, EVENT_REWARDS[3], member=member)
    
    # Event 7 Phase 1: Now uses button instead of reaction (handled in button callback)

async def escalate_collective_event(guild):
    """Trigger phase 2 for collective event."""
    global active_event
    if not active_event or active_event["type"] != 7:
        return
    
    # Wait for all roles to be assigned
    await asyncio.sleep(2)
    
    phase2_channel = guild.get_channel(EVENT_PHASE2_CHANNEL_ID)
    if not phase2_channel:
        return
    
    question, answer = choose_collective_question()
    active_event["phase"] = 2
    active_event["threshold_reached"] = True
    
    # Handle answer format (can be string or list)
    if isinstance(answer, list):
        active_event["question_answers"] = answer
    else:
        active_event["question_answers"] = [answer]
    
    active_event["answered_correctly"] = set()
    active_event["answered_incorrectly"] = set()
    
    question_embed = build_event_embed(f"Good. Now answer me.\n\n*{question}*", "https://i.imgur.com/v8Ik4cS.png")
    msg = await phase2_channel.send(embed=question_embed)
    active_event["phase2_message_id"] = msg.id
    
    # Phase 2 has 1 minute time limit
    asyncio.create_task(end_event7_phase2(active_event))

def calculate_xp_multiplier(member):
    """Calculate XP multiplier based on roles"""
    multiplier = 1.0
    if isinstance(member, discord.Member):
        for role in member.roles:
            if int(role.id) in MULTIPLIER_ROLE_SET:
                multiplier += 0.2
    return multiplier

async def add_xp(user_id, amount, member=None, base_multiplier: float = 1.0):
    """Add XP with optional multiplier from roles and channel"""
    uid = str(user_id)
    if uid not in xp_data:
        xp_data[uid] = {
            "xp": 0, "level": 1, "coins": 0,
            "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
            "times_gambled": 0, "total_wins": 0,
            "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
            "equipped_collar": None, "equipped_badge": None
        }
    
    # Ensure all fields exist
    defaults = {
        "coins": 0, "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
        "times_gambled": 0, "total_wins": 0,
        "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
        "equipped_collar": None, "equipped_badge": None
    }
    for key, default_value in defaults.items():
        if key not in xp_data[uid]:
            xp_data[uid][key] = default_value
    
    # Apply multiplier if member object is provided
    if member:
        multiplier = calculate_xp_multiplier(member)
        amount = int(amount * base_multiplier * multiplier)
        if multiplier > 1.0 or base_multiplier != 1.0:
            print(f"  ↳ Applied {base_multiplier * multiplier:.1f}x multiplier ({amount} XP total)")
    else:
        amount = int(amount * base_multiplier)
    
    old_level = xp_data[uid]["level"]
    xp_data[uid]["xp"] += amount
    # Prevent negative XP
    if xp_data[uid]["xp"] < 0:
        xp_data[uid]["xp"] = 0

    # Award coins: 1 coin per 10 XP (only for positive XP gains)
    if amount > 0:
        coins_earned = amount // 10
        if coins_earned > 0:
            add_coins(user_id, coins_earned)
            print(f"  ↳ Awarded {coins_earned} coins ({amount} XP / 10)")

    current_level = xp_data[uid]["level"]
    next_level_xp = next_level_requirement(current_level)

    # Check for level up
    if xp_data[uid]["xp"] >= next_level_xp:
        new_level = xp_data[uid]["level"] + 1
        xp_data[uid]["level"] = new_level
        
        # Award level up bonus coins
        if new_level in LEVEL_COIN_BONUSES:
            bonus_coins = LEVEL_COIN_BONUSES[new_level]
            add_coins(user_id, bonus_coins)
            print(f"  ↳ Level {new_level} bonus: {bonus_coins} coins")
        
        if member:
            await update_roles_on_level(member, new_level)
        save_xp_data()
        await send_level_up_message(user_id)
    else:
        save_xp_data()

# -----------------------------
# Level-up embed
# -----------------------------
async def send_level_up_message(user_id):
    try:
        user = await bot.fetch_user(user_id)
    except:
        print(f"Could not fetch user {user_id}")
        return
    
    # Get member from guild to access display_name (nickname)
    member = None
    for guild in bot.guilds:
        member = guild.get_member(user_id)
        if member:
            break
    
    # Fallback to user name if member not found
    display_name = member.display_name if member else user.name
    
    level = get_level(user_id)
    xp = get_xp(user_id)

    quotes = {
        1: "You think you’re here by choice. That you’ve decided to follow me. But the truth… I always know who will come. You’re already mine, whether you realize it or not.",
        2: "You keep looking at me like you might touch me, like you might understand me. But you don’t get to. I allow you to see me, nothing more. And if you push too far… you’ll regret it.",
        5: "There’s a line between you and me. You think it’s invisible. But I draw it, and you will obey it, because it’s in your nature to obey me. And you will want to.",
        10: "I could let you think you have control… but I don’t do that. I decide who gets close, who gets the privilege of crossing my boundaries. And sometimes… I choose to play with my prey.",
        20: "I’ve been watching you. Every thought, every hesitation. You don’t know why you follow me, do you? You feel drawn, compelled. That’s because I’ve decided you will be, and you cannot fight it.",
        30: "I like watching you struggle to understand me. It’s amusing how easily you underestimate what I can take, what I can give… and who I can claim. And yet, you still crave it.",
        50: "Do you feel that? That tightening in your chest, that fear… that longing? That’s me. Always. I don’t ask for loyalty—I command it. And you will obey. You will desire it.",
        75: "You imagine what it would be like to be closer. To be mine. But you’re not allowed to imagine everything. Only what I choose to show you. And when I decide to reveal it… it will be absolute.",
        100: (
            "You’ve done well. Watching you, learning how you move, how you think… it’s been very satisfying. "
            "You tried to resist at first, didn’t you? Humans always do. But you stayed. You listened. You kept coming back to me.\n\n"
            "That’s why I’ve chosen you. Not everyone earns my attention like this. You’re clever in your own way… and honest about your desire to be close to me. I find that endearing.\n\n"
            "If you stay by my side, if you follow when I call, I’ll take care of you. I’ll give you purpose. Affection. A place where you belong.\n\n"
            "From now on… you’re mine. And if I’m honest—\n"
            "I think you’ll be very happy as my pet."
        ),
    }

    quote_text = quotes.get(level, "Keep progressing…")

    # Get level role (milestone)
    level_role = "None"
    for lvl, role_id in sorted(LEVEL_ROLE_MAP.items(), reverse=True):
        if level >= lvl:
            # Try to get role from any guild the bot is in
            for guild in bot.guilds:
                role = guild.get_role(role_id)
                if role:
                    level_role = role.name
                    break
            if level_role != "None":
                break
    
    # Get milestone quote
    milestone_quotes = {
        1: "You think you're here by choice. That you've decided to follow me. But the truth… I always know who will come. You're already mine, whether you realize it or not.",
        2: "You keep looking at me like you might touch me, like you might understand me. But you don't get to. I allow you to see me, nothing more. And if you push too far… you'll regret it.",
        5: "There's a line between you and me. You think it's invisible. But I draw it, and you will obey it, because it's in your nature to obey me. And you will want to.",
        10: "I could let you think you have control… but I don't do that. I decide who gets close, who gets the privilege of crossing my boundaries. And sometimes… I choose to play with my prey.",
        20: "I've been watching you. Every thought, every hesitation. You don't know why you follow me, do you? You feel drawn, compelled. That's because I've decided you will be, and you cannot fight it.",
        30: "I like watching you struggle to understand me. It's amusing how easily you underestimate what I can take, what I can give… and who I can claim. And yet, you still crave it.",
        50: "Do you feel that? That tightening in your chest, that fear… that longing? That's me. Always. I don't ask for loyalty—I command it. And you will obey. You will desire it.",
        75: "You imagine what it would be like to be closer. To be mine. But you're not allowed to imagine everything. Only what I choose to show you. And when I decide to reveal it… it will be absolute.",
        100: "You've done well. Watching you, learning how you move, how you think… it's been very satisfying. You tried to resist at first, didn't you? Humans always do. But you stayed. You listened. You kept coming back to me.\n\nThat's why I've chosen you. Not everyone earns my attention like this. You're clever in your own way… and honest about your desire to be close to me. I find that endearing.\n\nIf you stay by my side, if you follow when I call, I'll take care of you. I'll give you purpose. Affection. A place where you belong.\n\nFrom now on… you're mine. And if I'm honest—\nI think you'll be very happy as my pet."
    }
    
    milestone_quote = milestone_quotes.get(level, None)
    if not milestone_quote:
        milestone_quote = "*Keep working hard for me ~*"
    
    embed = discord.Embed(
        title=f"{display_name} has leveled up <a:heartglitch:1449997688358572093>",
        description="᲼᲼",
        color=0x58585f,
    )
    embed.add_field(name="Current Level", value=str(level), inline=True)
    embed.add_field(name="Milestone", value=level_role, inline=True)
    embed.add_field(name="XP", value=str(xp), inline=True)
    embed.add_field(name="᲼᲼", value="", inline=False)
    embed.add_field(name="Message from Isla <:kisses:1449998044446593125>", value=milestone_quote, inline=False)

    # Send level-up message only to the specified channel
    level_up_channel_id = 1450107538019192832
    channel = bot.get_channel(level_up_channel_id)
    if channel:
        try:
            await channel.send(content=f"<@{user_id}>", embed=embed)
        except Exception as e:
            print(f"Error sending level-up message to channel {level_up_channel_id}: {e}")
    else:
        print(f"Level-up channel not found (ID: {level_up_channel_id})")

    # Send DM whisper on milestone levels
    milestone_quotes = {
        1: "You did good today. I left something small for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        2: "I’m starting to notice you. Go check the message I left for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        5: "You’re learning quickly. I made sure to leave you something in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        10: "Good behavior deserves attention. I left a message waiting for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        20: "You’re becoming reliable. I expect you’ll read what I left for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        30: "I like the way you respond to guidance. Go see what I wrote for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        50: "You know what I expect from you now. There’s a message for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        75: "You belong exactly where I want you. Don’t ignore the message I left in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        100: "You don’t need reminders anymore. Read what I left for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
    }

    if level in milestone_quotes:
        dm_embed = discord.Embed(
            title="𝙽𝚎𝚠 𝙼𝚎𝚜𝚜𝚊𝚐𝚎 𝚁𝚎𝚌𝚎𝚒𝚟𝚎𝚍",
            description=milestone_quotes[level],
            color=0xff000d,
        )
        dm_embed.set_author(name="Isla", url="https://beacons.ai/isla2d", icon_url="https://i.imgur.com/hikM1P1.jpeg")
        dm_embed.set_image(url="https://i.imgur.com/C7YJWXV.jpeg")
        try:
            await user.send(embed=dm_embed)
        except Exception as e:
            print(f"Failed to DM user {user_id} for level {level}: {e}")

# -----------------------------
# Commands: XP Management
# -----------------------------
@bot.tree.command(name="equip", description="Equip a collar or badge")
@app_commands.describe(item_type="Type of item to equip (collar or badge)", item_name="Name of the item to equip")
async def equip(interaction: discord.Interaction, item_type: str, item_name: str):
    """Equip a collar or badge."""
    if not await check_user_command_permissions(interaction):
        return
    
    user_id = interaction.user.id
    uid = str(user_id)
    item_type_lower = item_type.lower()
    
    if uid not in xp_data:
        xp_data[uid] = {
            "xp": 0, "level": 1, "coins": 0,
            "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
            "times_gambled": 0, "total_wins": 0,
            "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
            "equipped_collar": None, "equipped_badge": None
        }
    
    if item_type_lower == "collar":
        collars_owned = xp_data[uid].get("collars_owned", [])
        if item_name not in collars_owned:
            embed = discord.Embed(
                title="Item Not Owned",
                description=f"You don't own the collar '{item_name}'.",
                color=0xff000d
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        xp_data[uid]["equipped_collar"] = item_name
        save_xp_data()
        embed = discord.Embed(
            title="Collar Equipped",
            description=f"You've equipped the collar '{item_name}'.",
            color=0xff000d
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    elif item_type_lower == "badge":
        badges_owned = xp_data[uid].get("badges_owned", [])
        if item_name not in badges_owned:
            embed = discord.Embed(
                title="Item Not Owned",
                description=f"You don't own the badge '{item_name}'.",
                color=0xff000d
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        xp_data[uid]["equipped_badge"] = item_name
        save_xp_data()
        embed = discord.Embed(
            title="Badge Equipped",
            description=f"You've equipped the badge '{item_name}'.",
            color=0xff000d
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    else:
        embed = discord.Embed(
            title="Invalid Item Type",
            description="Item type must be 'collar' or 'badge'.",
            color=0xff000d
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Create level group for subcommands
level_group = app_commands.Group(name="level", description="Level-related commands")

@level_group.command(name="check", description="Check your current level")
@app_commands.describe(member="The member to check (optional, defaults to you)")
async def level_check(interaction: discord.Interaction, member: discord.Member = None):
    if not await check_user_command_permissions(interaction):
        return
    
    member = member or interaction.user
    user_id = member.id
    uid = str(user_id)
    
    # Initialize user data if needed
    if uid not in xp_data:
        xp_data[uid] = {
            "xp": 0, "level": 1, "coins": 0,
            "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
            "times_gambled": 0, "total_wins": 0,
            "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
            "equipped_collar": None, "equipped_badge": None
        }
    
    user_data = xp_data[uid]
    level_val = get_level(user_id)
    xp = get_xp(user_id)
    coins = get_coins(user_id)
    
    # Get level role (milestone)
    level_role = "None"
    for lvl, role_id in sorted(LEVEL_ROLE_MAP.items(), reverse=True):
        if level_val >= lvl:
            role = interaction.guild.get_role(role_id)
            if role:
                level_role = role.name
            break
    
    # Get equipped collar
    equipped_collar = user_data.get("equipped_collar")
    collar_display = f" {equipped_collar}" if equipped_collar else ""
    
    # Get activity quote
    activity_quote = get_activity_quote(user_id, interaction.guild)
    
    # Format voice chat time
    vc_minutes = user_data.get("vc_minutes", 0)
    vc_hours = vc_minutes // 60
    vc_mins = vc_minutes % 60
    vc_time_str = f"{vc_hours}h {vc_mins}m" if vc_hours > 0 else f"{vc_mins}m"
    
    # Get collections
    badges_owned = user_data.get("badges_owned", [])
    collars_owned = user_data.get("collars_owned", [])
    interfaces_owned = user_data.get("interfaces_owned", [])
    
    badges_display = ", ".join(badges_owned) if badges_owned else "No badges owned."
    collars_display = ", ".join(collars_owned) if collars_owned else "No collars owned."
    interfaces_display = ", ".join(interfaces_owned) if interfaces_owned else "No interfaces/themes owned."
    
    # Get showcased badge (equipped badge or first badge)
    showcased_badge = user_data.get("equipped_badge")
    if not showcased_badge and badges_owned:
        showcased_badge = badges_owned[0]
    # For now, we'll use a placeholder thumbnail URL - you can customize this
    thumbnail_url = None  # You can set this to a badge image URL if you have one
    
    # Build embed
    # Use display_name (nickname) for title since Discord doesn't support mentions in embed titles
    embed = discord.Embed(
        title=f"{member.display_name}'s Server Profile{collar_display}",
        description=f"*{activity_quote}*\n᲼᲼",
        color=0x58585f
    )
    
    embed.add_field(name="Current Level", value=str(level_val), inline=True)
    embed.add_field(name="Milestone", value=level_role, inline=True)
    embed.add_field(name="XP", value=str(xp), inline=True)
    embed.add_field(name="᲼᲼", value="", inline=False)
    embed.add_field(name="Messages Sent", value=f"💬 {user_data.get('messages_sent', 0)}", inline=True)
    embed.add_field(name="Voice Chat Time", value=f"🎙️ {vc_time_str}", inline=True)
    embed.add_field(name="Event Participations", value=f"🎫 {user_data.get('event_participations', 0)}", inline=True)
    embed.add_field(name="᲼᲼", value="", inline=False)
    embed.add_field(name="Balance", value=f"💵 {coins}", inline=True)
    embed.add_field(name="Times Gambled", value=f"🎲 {user_data.get('times_gambled', 0)}", inline=True)
    embed.add_field(name="Total Wins", value=f"🏆 {user_data.get('total_wins', 0)}", inline=True)
    embed.add_field(name="᲼᲼", value="", inline=False)
    embed.add_field(name="Badge Collection", value=badges_display, inline=False)
    embed.add_field(name="Collar Collection", value=collars_display, inline=False)
    embed.add_field(name="Interface Collection", value=interfaces_display, inline=False)
    
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    if int(interaction.channel.id) in ALLOWED_SEND_SET:
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(embed=embed, delete_after=10)

@bot.tree.command(name="config", description="Show current bot configuration. Admin only.")
async def config(interaction: discord.Interaction):
    """Show current bot configuration (Admin only)"""
    if not await check_admin_command_permissions(interaction):
        return
    
    embed = discord.Embed(
        title="🔧 Bot Configuration",
        color=0xff000d
    )
    
    xp_channels = ", ".join([f"<#{ch}>" for ch in sorted(XP_TRACK_SET)])
    send_channels = ", ".join([f"<#{ch}>" for ch in sorted(ALLOWED_SEND_SET)])
    mult_roles = ", ".join([f"<@&{r}>" for r in sorted(MULTIPLIER_ROLE_SET)])
    excluded_roles = ", ".join([f"<@&{r}>" for r in sorted(EXCLUDED_ROLE_SET)])
    excluded_cats = ", ".join([f"<#{c}>" for c in sorted(NON_XP_CATEGORY_IDS)])
    excluded_channels = ", ".join([f"<#{c}>" for c in sorted(NON_XP_CHANNEL_IDS)])
    channel_mults = ", ".join([f"<#{cid}> x{mult}" for cid, mult in CHANNEL_MULTIPLIERS.items()])
    
    embed.add_field(name="XP Track Channels", value=xp_channels or "None", inline=False)
    embed.add_field(name="Send Channels", value=send_channels or "None", inline=False)
    embed.add_field(name="Excluded Roles", value=excluded_roles or "None", inline=False)
    embed.add_field(name="Excluded Categories", value=excluded_cats or "None", inline=False)
    embed.add_field(name="Excluded Channels", value=excluded_channels or "None", inline=False)
    embed.add_field(name="Multiplier Roles", value=mult_roles or "None", inline=False)
    embed.add_field(name="Channel Multipliers", value=channel_mults or "None", inline=False)
    embed.add_field(name="Message Cooldown", value=f"{MESSAGE_COOLDOWN} seconds", inline=True)
    embed.add_field(name="VC XP/min", value=f"{VC_XP} XP", inline=True)
    
    # Show raw IDs
    raw_config = (
        "```python\n"
        f"XP_TRACK_CHANNELS = {sorted(XP_TRACK_SET)}\n"
        f"ALLOWED_SEND_CHANNELS = {sorted(ALLOWED_SEND_SET)}\n"
        f"EXCLUDED_ROLE_IDS = {sorted(EXCLUDED_ROLE_SET)}\n"
        f"NON_XP_CATEGORY_IDS = {sorted(NON_XP_CATEGORY_IDS)}\n"
        f"NON_XP_CHANNEL_IDS = {sorted(NON_XP_CHANNEL_IDS)}\n"
        f"MULTIPLIER_ROLES = {sorted(MULTIPLIER_ROLE_SET)}\n"
        f"CHANNEL_MULTIPLIERS = {CHANNEL_MULTIPLIERS}\n"
        "```"
    )
    embed.add_field(name="Raw Configuration", value=raw_config, inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="obedience", description="Start a hidden obedience event (1-7). Admin only.")
@app_commands.describe(event_type="The event type (1-7)")
async def obedience(interaction: discord.Interaction, event_type: int):
    """Start a hidden obedience event (1-7). Admin only."""
    if not await check_admin_command_permissions(interaction):
        return
    
    if event_type not in range(1, 8):
        await interaction.response.send_message("Event type must be between 1 and 7.", ephemeral=True)
        return
    await start_obedience_event(interaction, event_type)

@bot.tree.command(name="testembeds", description="Preview the main embed formats used by the bot. Admin only.")
async def testembeds(interaction: discord.Interaction):
    """Preview the main embed formats used by the bot."""
    if not await check_admin_command_permissions(interaction):
        return
    
    member = interaction.user
    level = get_level(member.id)
    xp = get_xp(member.id)

    # 1) Level-up embed preview (uses current level/xp)
    level_quotes = {
        1: "You think you’re here by choice. That you’ve decided to follow me. But the truth… I always know who will come. You’re already mine, whether you realize it or not.",
        2: "You keep looking at me like you might touch me, like you might understand me. But you don’t get to. I allow you to see me, nothing more. And if you push too far… you’ll regret it.",
        5: "There’s a line between you and me. You think it’s invisible. But I draw it, and you will obey it, because it’s in your nature to obey me. And you will want to.",
        10: "I could let you think you have control… but I don’t do that. I decide who gets close, who gets the privilege of crossing my boundaries. And sometimes… I choose to play with my prey.",
        20: "I’ve been watching you. Every thought, every hesitation. You don’t know why you follow me, do you? You feel drawn, compelled. That’s because I’ve decided you will be, and you cannot fight it.",
        30: "I like watching you struggle to understand me. It’s amusing how easily you underestimate what I can take, what I can give… and who I can claim. And yet, you still crave it.",
        50: "Do you feel that? That tightening in your chest, that fear… that longing? That’s me. Always. I don’t ask for loyalty—I command it. And you will obey. You will desire it.",
        75: "You imagine what it would be like to be closer. To be mine. But you’re not allowed to imagine everything. Only what I choose to show you. And when I decide to reveal it… it will be absolute.",
        100: (
            "You’ve done well. Watching you, learning how you move, how you think… it’s been very satisfying. "
            "You tried to resist at first, didn’t you? Humans always do. But you stayed. You listened. You kept coming back to me.\n\n"
            "That’s why I’ve chosen you. Not everyone earns my attention like this. You’re clever in your own way… and honest about your desire to be close to me. I find that endearing.\n\n"
            "If you stay by my side, if you follow when I call, I’ll take care of you. I’ll give you purpose. Affection. A place where you belong.\n\n"
            "From now on… you’re mine. And if I’m honest—\n"
            "I think you’ll be very happy as my pet."
        ),
    }
    lvl_quote = level_quotes.get(level, level_quotes[1])

    next_level_xp = next_level_requirement(level)
    xp_needed = max(next_level_xp - xp, 0)

    level_embed = discord.Embed(
        title="[ ✦ ]",
        description="𝙰𝚍𝚟𝚊𝚗𝚌𝚎𝚖𝚎𝚗𝚝 𝚁𝚎𝚌𝚘𝚛𝚍𝚎𝚍 \n᲼᲼",
        color=0xff000d,
    )
    level_embed.add_field(name="𝙿𝚛𝚘𝚖𝚘𝚝𝚒𝚘𝚗", value=f"<@{member.id}>", inline=True)
    level_embed.add_field(name="Level", value=f"{level}", inline=True)
    level_embed.add_field(name="XP", value=f"{xp}/{next_level_xp}", inline=True)
    level_embed.add_field(name="Next Level", value=f"{xp_needed} XP needed", inline=False)
    level_embed.add_field(
        name="᲼᲼",
        value=f"**𝙼𝚎𝚜𝚜𝚊𝚐𝚎 𝚁𝚎𝚌𝚎𝚒𝚟𝚎𝚍**\n*{lvl_quote}*",
        inline=False,
    )
    await interaction.response.send_message("Level-up embed preview:", embed=level_embed)

    # 2) DM whisper embed preview (uses current level milestone text)
    milestone_quotes = {
        1: "You did good today. I left something small for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        2: "I’m starting to notice you. Go check the message I left for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        5: "You’re learning quickly. I made sure to leave you something in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        10: "Good behavior deserves attention. I left a message waiting for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        20: "You’re becoming reliable. I expect you’ll read what I left for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        30: "I like the way you respond to guidance. Go see what I wrote for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        50: "You know what I expect from you now. There’s a message for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        75: "You belong exactly where I want you. Don’t ignore the message I left in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
        100: "You don’t need reminders anymore. Read what I left for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
    }
    dm_text = milestone_quotes.get(level, milestone_quotes[1])
    dm_embed = discord.Embed(
        title="𝙽𝚎𝚠 𝙼𝚎𝚜𝚜𝚊𝚐𝚎 𝚁𝚎𝚌𝚎𝚒𝚟𝚎𝚍",
        description=dm_text,
        color=0xff000d,
    )
    dm_embed.set_author(
        name="Isla",
        url="https://beacons.ai/isla2d",
        icon_url="https://i.imgur.com/hikM1P1.jpeg",
    )
    dm_embed.set_image(url="https://i.imgur.com/C7YJWXV.jpeg")
    await interaction.followup.send("DM whisper embed preview:", embed=dm_embed)

    # 3) Obedience event embed preview
    prompt, image_url = event_prompt(1)
    obedience_embed = build_event_embed(prompt, image_url)
    await interaction.followup.send("Obedience event embed preview:", embed=obedience_embed)

async def send_throne_message(guild):
    """Send Throne message to the event channel."""
    throne_channel = guild.get_channel(EVENT_CHANNEL_ID)
    if not throne_channel:
        print(f"Throne channel not found (ID: {EVENT_CHANNEL_ID})")
        return False
    
    quote_variations = [
        "A good puppy knows where to show appreciation. Throne's waiting.",
        "I wonder who's going to surprise me next.",
        "You already know what to do. My Throne is there.",
        "I don't need to ask twice. Check my Throne.",
        "If you're here, you should already be on Throne.",
    ]
    
    quote = random.choice(quote_variations)
    embed = discord.Embed(
        description=f"*{quote}*\n\n[Go to Throne](https://throne.com/lsla/item/1230a476-4752-4409-9583-9313e60686fe)",
        color=0xff000d,
    )
    embed.set_image(url="https://i.imgur.com/Q6HAYBP.png")
    
    try:
        await throne_channel.send("@everyone", embed=embed)
        print(f"✅ Throne message sent to {throne_channel.name}")
        return True
    except Exception as e:
        print(f"Failed to send Throne message: {e}")
        return False

async def send_slots_announcement(guild):
    """Send Slots program announcement to the event channel."""
    slots_channel = guild.get_channel(EVENT_CHANNEL_ID)
    if not slots_channel:
        print(f"Slots announcement channel not found (ID: {EVENT_CHANNEL_ID})")
        return False
    
    embed = discord.Embed(
        description="*Come on… go play my [Slots](https://islaexe.itch.io/islas-slots).*",
        color=0xff000d,
    )
    embed.set_image(url="https://i.imgur.com/dL1MW23.png")
    embed.set_footer(text="If you're a good dog, you know what to do.")
    
    try:
        await slots_channel.send("@everyone", embed=embed)
        print(f"✅ Slots announcement sent to {slots_channel.name}")
        return True
    except Exception as e:
        print(f"Failed to send Slots announcement: {e}")
        return False

async def send_daily_check_dailycommand(guild):
    """Send Daily Check message for /daily command."""
    daily_channel = guild.get_channel(1450107538019192832)  # User command channel
    if not daily_channel:
        print(f"Daily check channel not found (ID: 1450107538019192832)")
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
    embed.set_thumbnail(url="https://i.imgur.com/F2RpiGq.png")
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

async def send_jackpot_announcement(guild, user):
    """Send jackpot announcement to the event channel."""
    event_channel = guild.get_channel(EVENT_CHANNEL_ID)
    if not event_channel:
        print(f"Event channel not found (ID: {EVENT_CHANNEL_ID})")
        return False
    
    embed = discord.Embed(
        title="🐶 Good Dog",
        description=f"{user.mention} had the nerve to play—and it paid off.\n\nWhat excuse are you hiding behind?",
        color=0xff000d,
    )
    embed.set_image(url="https://i.imgur.com/2SbYpGX.png")
    embed.set_footer(text="Remember... Luck is temporary. I'm not")
    
    try:
        await event_channel.send("@everyone", embed=embed)
        print(f"✅ Jackpot announcement sent for {user.name} to {event_channel.name}")
        return True
    except Exception as e:
        print(f"Failed to send jackpot announcement: {e}")
        return False

@bot.tree.command(name="throne", description="Send a Throne message with quote variations. Admin only.")
async def throne(interaction: discord.Interaction):
    """Send a Throne message with quote variations."""
    if not await check_admin_command_permissions(interaction):
        return
    
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    
    success = await send_throne_message(interaction.guild)
    if success:
        await interaction.response.send_message("✅ Throne message sent!", ephemeral=True, delete_after=5)
    else:
        await interaction.response.send_message(f"Failed to send Throne message. Check bot logs.", ephemeral=True, delete_after=10)

@bot.tree.command(name="killevent", description="Kill any currently running event and set a 30-minute cooldown. Admin only.")
async def killevent(interaction: discord.Interaction):
    """Kill any currently running event and set a 30-minute cooldown."""
    global active_event, event_cooldown_until
    
    if not await check_admin_command_permissions(interaction):
        return
    
    if not active_event:
        await interaction.response.send_message("No event is currently running.", ephemeral=True, delete_after=5)
        return
    
    # Clear active event first (so clear_event_roles will work)
    active_event = None
    
    # Clear event roles
    await clear_event_roles()
    
    # Set 30-minute cooldown
    event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=1800)
    
    await interaction.response.send_message("✅ Event killed. 30-minute cooldown activated.", ephemeral=True, delete_after=10)
    print(f"Event killed by {interaction.user.name}. Cooldown until {event_cooldown_until.strftime('%H:%M:%S UTC')}")

@bot.tree.command(name="sync", description="Sync slash commands. Admin only.")
async def sync_commands(interaction: discord.Interaction):
    """Sync slash commands (Admin only)"""
    if not await check_admin_command_permissions(interaction):
        return
    
    try:
        synced = await bot.tree.sync()
        await interaction.response.send_message(f"✅ Synced {len(synced)} slash command(s)", ephemeral=True)
        print(f"✅ Manually synced {len(synced)} slash command(s) by {interaction.user.name}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to sync slash commands: {e}", ephemeral=True)
        print(f"❌ Failed to sync slash commands: {e}")

@bot.tree.command(name="stopevents", description="Stop or start events from running. Admin only.")
async def stopevents(interaction: discord.Interaction):
    """Stop or start events from running."""
    global events_enabled
    
    if not await check_admin_command_permissions(interaction):
        return
    
    events_enabled = not events_enabled
    status = "enabled" if events_enabled else "disabled"
    await interaction.response.send_message(f"✅ Events are now **{status}**.", ephemeral=True, delete_after=10)
    print(f"Events {status} by {interaction.user.name}")

@bot.tree.command(name="levelrolecheck", description="Manually check that users do not have multiple level roles at once. Admin only.")
async def levelrolecheck(interaction: discord.Interaction):
    """Manually check that users do not have multiple level roles at once."""
    # Note: levelrolecheck doesn't require channel restriction, only admin role
    if not isinstance(interaction.user, discord.Member):
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    
    if not any(int(role.id) in ADMIN_ROLE_IDS for role in interaction.user.roles):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True, delete_after=5)
        return
    
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    
    fixed_count = 0
    for member in guild.members:
        if member.bot or any(int(r.id) in EXCLUDED_ROLE_SET for r in member.roles):
            continue
        
        # Find all level roles the member has
        level_roles = []
        for lvl, role_id in LEVEL_ROLE_MAP.items():
            role = guild.get_role(role_id)
            if role and role in member.roles:
                level_roles.append((lvl, role))
        
        # If member has multiple level roles, keep only the highest
        if len(level_roles) > 1:
            level_roles.sort(key=lambda x: x[0], reverse=True)
            highest_level, highest_role = level_roles[0]
            roles_to_remove = [role for _, role in level_roles[1:]]
            
            try:
                await member.remove_roles(*roles_to_remove, reason="Level role check - removing duplicate roles")
                fixed_count += 1
                print(f"Fixed {member.name}: Removed {len(roles_to_remove)} duplicate level roles, kept level {highest_level}")
            except Exception as e:
                print(f"Failed to fix roles for {member.name}: {e}")
    
    await interaction.response.send_message(f"✅ Level role check complete. Fixed {fixed_count} user(s).", ephemeral=True, delete_after=10)

@bot.tree.command(name="levelupdates", description="Manually update all users' level roles based on their current level. Admin only.")
async def levelupdates(interaction: discord.Interaction):
    """Manually update all users' level roles based on their current level."""
    if not await check_admin_command_permissions(interaction):
        return
    
    await interaction.response.defer(ephemeral=True)
    
    guild = interaction.guild
    if not guild:
        await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
        return
    
    updated_count = 0
    for member in guild.members:
        if member.bot or any(int(r.id) in EXCLUDED_ROLE_SET for r in member.roles):
            continue
        
        # Get member's current level
        user_level = get_level(member.id)
        if user_level > 0:
            try:
                # Update roles based on current level
                await update_roles_on_level(member, user_level)
                updated_count += 1
            except Exception as e:
                print(f"Failed to update roles for {member.name}: {e}")
    
    await interaction.followup.send(f"✅ Level role updates complete. Updated {updated_count} user(s).", ephemeral=True, delete_after=10)

@bot.tree.command(name="setxp", description="Set a user's XP. Admin only.")
@app_commands.describe(member="The member to set XP for", amount="The XP amount to set")
async def setxp(interaction: discord.Interaction, member: discord.Member, amount: int):
    """Set a user's XP (Admin only)"""
    if not await check_admin_command_permissions(interaction):
        return
    
    uid = str(member.id)
    if uid not in xp_data:
        xp_data[uid] = {"xp": 0, "level": 1, "coins": 0}
    xp_data[uid]["xp"] = amount
    save_xp_data()
    await interaction.response.send_message(f"Set <@{member.id}>'s XP to {amount}", ephemeral=True)

@bot.tree.command(name="setlevel", description="Set a user's level. Admin only.")
@app_commands.describe(member="The member to set level for", level="The level to set")
async def setlevel(interaction: discord.Interaction, member: discord.Member, level: int):
    """Set a user's level (Admin only)"""
    if not await check_admin_command_permissions(interaction):
        return
    
    uid = str(member.id)
    if uid not in xp_data:
        xp_data[uid] = {"xp": 0, "level": 1, "coins": 0}
    xp_data[uid]["level"] = level
    save_xp_data()
    await interaction.response.send_message(f"Set <@{member.id}>'s level to {level}", ephemeral=True)

@bot.tree.command(name="schedule", description="Show all scheduled events with timestamps. Admin only.")
async def schedule(interaction: discord.Interaction):
    """Show all scheduled events with timestamps (Admin only)"""
    if not await check_admin_command_permissions(interaction):
        return
    
    embed = discord.Embed(
        title="📅 Event Schedule",
        description="Next scheduled events (UK timezone)",
        color=0xff000d
    )
    
    # Get UK timezone
    uk_tz = get_timezone("Europe/London")
    if uk_tz is None:
        await interaction.response.send_message("Timezone support not available. Cannot calculate schedule.", ephemeral=True)
        return
    
    # Tier 1 Events
    tier1_times = []
    for hour, minute in EVENT_SCHEDULE[1]:
        timestamp = get_next_scheduled_time(hour, minute)
        tier1_times.append(f"<t:{timestamp}:F> (<t:{timestamp}:R>)")
    embed.add_field(
        name="🎯 Tier 1 Events",
        value="\n".join(tier1_times) or "No scheduled times",
        inline=False
    )
    
    # Tier 2 Events
    tier2_times = []
    for hour, minute in EVENT_SCHEDULE[2]:
        timestamp = get_next_scheduled_time(hour, minute)
        tier2_times.append(f"<t:{timestamp}:F> (<t:{timestamp}:R>)")
    embed.add_field(
        name="🎯 Tier 2 Events",
        value="\n".join(tier2_times) or "No scheduled times",
        inline=False
    )
    
    # Tier 3 Events
    tier3_times = []
    for hour, minute in EVENT_SCHEDULE[3]:
        timestamp = get_next_scheduled_time(hour, minute)
        tier3_times.append(f"<t:{timestamp}:F> (<t:{timestamp}:R>)")
    embed.add_field(
        name="🎯 Tier 3 Events",
        value="\n".join(tier3_times) or "No scheduled times",
        inline=False
    )
    
    # Throne Messages (7:00 AM and 7:00 PM)
    throne_times = []
    for hour in [7, 19]:
        timestamp = get_next_scheduled_time(hour, 0)
        throne_times.append(f"<t:{timestamp}:F> (<t:{timestamp}:R>)")
    embed.add_field(
        name="👑 Throne Messages",
        value="\n".join(throne_times) or "No scheduled times",
        inline=False
    )
    
    # Slots Announcement (8:00 PM)
    slots_timestamp = get_next_scheduled_time(20, 0)
    embed.add_field(
        name="🎰 Slots Announcement",
        value=f"<t:{slots_timestamp}:F> (<t:{slots_timestamp}:R>)",
        inline=False
    )
    
    # Add current status
    if active_event:
        event_type = active_event.get("type", "Unknown")
        embed.add_field(
            name="⚡ Current Status",
            value=f"Event {event_type} is currently active",
            inline=False
        )
    elif event_cooldown_until and datetime.datetime.now(datetime.UTC) < event_cooldown_until:
        cooldown_timestamp = int(event_cooldown_until.timestamp())
        embed.add_field(
            name="⚡ Current Status",
            value=f"Events on cooldown until <t:{cooldown_timestamp}:F> (<t:{cooldown_timestamp}:R>)",
            inline=False
        )
    else:
        embed.add_field(
            name="⚡ Current Status",
            value="No active event. Next scheduled event will trigger automatically.",
            inline=False
        )
    
    embed.set_footer(text="Timestamps update automatically. Times shown in UK timezone.")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

def format_placement(place: int) -> str:
    """Format placement number as ordinal (1st, 2nd, 3rd, etc.)"""
    if place % 100 in [11, 12, 13]:
        return f"{place}th"
    elif place % 10 == 1:
        return f"{place}st"
    elif place % 10 == 2:
        return f"{place}nd"
    elif place % 10 == 3:
        return f"{place}rd"
    else:
        return f"{place}th"

def build_levels_leaderboard_embed(sorted_users, page: int = 0, users_per_page: int = 10):
    """Build levels leaderboard embed with pagination support."""
    embed = discord.Embed(
        title="💋 Levels Leaderboard",
        description="᲼᲼",
        color=0x58585f,
    )
    
    # Calculate start and end indices for current page
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    users_to_show = sorted_users[start_idx:end_idx]
    
    # Build three columns: Placement, Level, XP
    placement_lines = []
    level_lines = []
    xp_lines = []
    
    for idx, (user_id, data) in enumerate(users_to_show, start=start_idx + 1):
        try:
            level = data.get("level", 1)
            xp = data.get("xp", 0)
            placement_lines.append(f"{idx}. <@{user_id}>")
            level_lines.append(str(level))
            xp_lines.append(str(xp))
        except Exception:
            continue
    
    # Ensure all lists have the same length
    min_length = min(len(placement_lines), len(level_lines), len(xp_lines))
    if min_length > 0:
        placement_lines = placement_lines[:min_length]
        level_lines = level_lines[:min_length]
        xp_lines = xp_lines[:min_length]
        
        # Add fields with all users in columns
        embed.add_field(name="Placement", value="\n".join(placement_lines), inline=True)
        embed.add_field(name="Level", value="\n".join(level_lines), inline=True)
        embed.add_field(name="XP", value="\n".join(xp_lines), inline=True)
    
    embed.add_field(name="᲼᲼", value="", inline=False)
    
    # Footer with quote variants
    level_quotes = [
        "I love watching you grow stronger for me. Keep going.",
        "All that effort… I noticed. Of course I did.",
        "Climbing the ranks just to impress me? Good.",
        "You work so hard. Exactly the kind of dedication I enjoy.",
        "Levels don't rise on their own. You earned this—for me."
    ]
    embed.set_footer(text=random.choice(level_quotes), icon_url="https://i.imgur.com/GYOngr2.png")
    
    return embed

def build_coins_leaderboard_embed(sorted_users, page: int = 0, users_per_page: int = 10):
    """Build coins leaderboard embed with pagination support."""
    embed = discord.Embed(
        title="💵 Coin Leaderboard",
        description="᲼᲼",
        color=0x58585f,
    )
    
    # Calculate start and end indices for current page
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    users_to_show = sorted_users[start_idx:end_idx]
    
    # Build three columns: Placement, Coins, Spent
    placement_lines = []
    coins_lines = []
    spent_lines = []
    
    for idx, (user_id, data) in enumerate(users_to_show, start=start_idx + 1):
        try:
            coins = data.get("coins", 0)
            total_spent = data.get("total_spent", 0)  # Get total money spent on gambling
            placement_lines.append(f"{idx}. <@{user_id}>")
            coins_lines.append(str(coins))
            spent_lines.append(str(total_spent))
        except Exception:
            continue
    
    # Ensure all lists have the same length
    min_length = min(len(placement_lines), len(coins_lines), len(spent_lines))
    if min_length > 0:
        placement_lines = placement_lines[:min_length]
        coins_lines = coins_lines[:min_length]
        spent_lines = spent_lines[:min_length]
        
        # Add fields with all users in columns
        embed.add_field(name="Placement", value="\n".join(placement_lines), inline=True)
        embed.add_field(name="Coins", value="\n".join(coins_lines), inline=True)
        embed.add_field(name="Spent", value="\n".join(spent_lines), inline=True)
    
    embed.add_field(name="᲼᲼", value="", inline=False)
    
    # Footer with quote variants
    coin_quotes = [
        "Seeing your coins pile up makes me curious how you'll use them.",
        "You're very generous with your time and resources. I like that.",
        "All those coins… it's sweet how much you're willing to give.",
        "You clearly enjoy investing in things that matter to me.",
        "Money moves when you're motivated. And you look very motivated."
    ]
    embed.set_footer(text=random.choice(coin_quotes), icon_url="https://i.imgur.com/GYOngr2.png")
    
    return embed

def build_activity_leaderboard_embed(sorted_users, page: int = 0, users_per_page: int = 10):
    """Build activity leaderboard embed with pagination support."""
    embed = discord.Embed(
        title="🎀 Activity Leaderboard",
        description="᲼᲼",
        color=0x58585f,
    )
    
    # Calculate start and end indices for current page
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    users_to_show = sorted_users[start_idx:end_idx]
    
    # Build three columns: Placement, Messages, Voice Chat Time
    placement_lines = []
    messages_lines = []
    vc_time_lines = []
    
    for idx, (user_id, data) in enumerate(users_to_show, start=start_idx + 1):
        try:
            messages_sent = data.get("messages_sent", 0)
            vc_minutes = data.get("vc_minutes", 0)
            vc_hours = vc_minutes // 60
            vc_mins = vc_minutes % 60
            vc_time_str = f"{vc_hours}h {vc_mins}m" if vc_hours > 0 else f"{vc_mins}m"
            placement_lines.append(f"{idx}. <@{user_id}>")
            messages_lines.append(f"💬 {messages_sent}")
            vc_time_lines.append(f"🎙️ {vc_time_str}")
        except Exception:
            continue
    
    # Ensure all lists have the same length
    min_length = min(len(placement_lines), len(messages_lines), len(vc_time_lines))
    if min_length > 0:
        placement_lines = placement_lines[:min_length]
        messages_lines = messages_lines[:min_length]
        vc_time_lines = vc_time_lines[:min_length]
        
        # Add fields with all users in columns
        embed.add_field(name="Placement", value="\n".join(placement_lines), inline=True)
        embed.add_field(name="Messages", value="\n".join(messages_lines), inline=True)
        embed.add_field(name="Voice Chat Time", value="\n".join(vc_time_lines), inline=True)
    
    embed.add_field(name="᲼᲼", value="", inline=False)
    
    # Footer with quote variants
    activity_quotes = [
        "You're always here. I wonder if you even realize how often I see you.",
        "So much time spent with me… that can't be an accident.",
        "Consistency like this feels intentional. I appreciate that.",
        "You give me so much of your time. That says a lot.",
        "I love how naturally you keep coming back."
    ]
    embed.set_footer(text=random.choice(activity_quotes), icon_url="https://i.imgur.com/GYOngr2.png")
    
    return embed


class LeaderboardView(discord.ui.View):
    """View with pagination buttons for leaderboard."""
    
    def __init__(self, sorted_users, embed_builder, users_per_page: int = 10, timeout: float = 300.0):
        super().__init__(timeout=timeout)
        self.sorted_users = sorted_users
        self.embed_builder = embed_builder
        self.users_per_page = users_per_page
        self.current_page = 0
        self.max_pages = (len(sorted_users) + users_per_page - 1) // users_per_page if sorted_users else 1
        # Initialize button states after buttons are added
        self._init_button_states()
    
    def _init_button_states(self):
        """Initialize button states based on current page."""
        # This will be called after buttons are added to the view
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if hasattr(item, 'custom_id'):
                    if item.custom_id == "prev_page":
                        item.disabled = (self.current_page == 0)
                    elif item.custom_id == "next_page":
                        item.disabled = (self.current_page >= self.max_pages - 1)
    
    def update_buttons(self):
        """Update button states based on current page."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if hasattr(item, 'custom_id'):
                    if item.custom_id == "prev_page":
                        item.disabled = (self.current_page == 0)
                    elif item.custom_id == "next_page":
                        item.disabled = (self.current_page >= self.max_pages - 1)
    
    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="prev_page")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.embed_builder(self.sorted_users, page=self.current_page, users_per_page=self.users_per_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.embed_builder(self.sorted_users, page=self.current_page, users_per_page=self.users_per_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="My Stats", style=discord.ButtonStyle.danger)
    async def my_stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show the user's stats in a new embed."""
        user_id = interaction.user.id
        level = get_level(user_id)
        xp = get_xp(user_id)
        
        next_level_xp = next_level_requirement(level)
        xp_needed = next_level_xp - xp
        
        messages = [
            "I can tell you've been trying.",
            "All of that effort… it belongs to me.",
            "I like the way you've been obsessed over me."
        ]
        
        embed = discord.Embed(
            title="[ ✧ ]",
            description="𝙿𝚛𝚘𝚐𝚛𝚎𝚜𝚜 𝙻𝚘𝚐\n᲼᲼",
            color=0xff000d
        )
        embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
        embed.add_field(name="Level", value=f"{level}", inline=True)
        embed.add_field(name="XP", value=f"{xp}/{next_level_xp}", inline=True)
        embed.add_field(name="Next Level", value=f"{xp_needed} XP needed", inline=False)
        embed.add_field(name="᲼᲼", value=f"𝙼𝚎𝚜𝚜𝚊𝚐𝚎 𝚁𝚎𝚌𝚎𝚒𝚟𝚎𝚍\n*{random.choice(messages)}*", inline=False)
        
        await interaction.response.send_message(content=f"<@{user_id}>", embed=embed, ephemeral=True)



# Standalone leaderboards command (plural) - shows menu
@bot.tree.command(name="leaderboards", description="View available leaderboards")
async def leaderboards_menu(interaction: discord.Interaction):
    """Show leaderboard menu"""
    if not await check_user_command_permissions(interaction):
        return
    
    embed = discord.Embed(
        title="Leaderboards",
        description="Which leaderboard would you like to check?\n᲼᲼",
        color=0x58585f
    )
    
    embed.add_field(
        name="Levels Leaderboard",
        value="💋 Use `/leaderboard <levels>`",
        inline=False
    )
    embed.add_field(
        name="Coins Leaderboard",
        value="💵 Use `/leaderboard <coins>`",
        inline=False
    )
    embed.add_field(
        name="Activity Leaderboard",
        value="🎀 Use `/leaderboard <activity>`",
        inline=False
    )
    embed.add_field(
        name="᲼᲼",
        value="*I love watching you work hard for me ~*",
        inline=False
    )
    
    if int(interaction.channel.id) in ALLOWED_SEND_SET:
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(embed=embed, delete_after=15)

# Leaderboard command with choice parameter
@bot.tree.command(name="leaderboard", description="View leaderboards")
@app_commands.choices(leaderboard_type=[
    app_commands.Choice(name="levels", value="levels"),
    app_commands.Choice(name="coins", value="coins"),
    app_commands.Choice(name="activity", value="activity"),
])
async def leaderboard(interaction: discord.Interaction, leaderboard_type: app_commands.Choice[str]):
    """Show leaderboard based on type"""
    if not await check_user_command_permissions(interaction):
        return
    
    # Filter out users not in the server
    guild = interaction.guild
    if guild:
        guild_member_ids = {str(member.id) for member in guild.members}
        filtered_xp_data = {uid: data for uid, data in xp_data.items() if uid in guild_member_ids}
    else:
        filtered_xp_data = xp_data
    
    lb_type = leaderboard_type.value if isinstance(leaderboard_type, app_commands.Choice) else leaderboard_type
    
    if lb_type == "levels":
        # Sort users by XP
        sorted_users = sorted(filtered_xp_data.items(), key=lambda x: x[1].get("xp", 0), reverse=True)
        
        # Build initial embed (showing top 10 users with fields, page 0)
        embed = build_levels_leaderboard_embed(sorted_users, page=0, users_per_page=10)
        
        # Create view with pagination buttons
        view = LeaderboardView(sorted_users, build_levels_leaderboard_embed, users_per_page=10)
        
        try:
            if int(interaction.channel.id) in ALLOWED_SEND_SET:
                await interaction.response.send_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view, delete_after=15)
        except Exception as e:
            print(f"Error sending leaderboard: {e}")
            # Fallback: send without button
            if int(interaction.channel.id) in ALLOWED_SEND_SET:
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(embed=embed, delete_after=15)
        return
        
    elif lb_type == "coins":
        # Sort users by coins
        sorted_users = sorted(filtered_xp_data.items(), key=lambda x: x[1].get("coins", 0), reverse=True)
        
        # Build initial embed (showing top 10 users with fields, page 0)
        embed = build_coins_leaderboard_embed(sorted_users, page=0, users_per_page=10)
        
        # Create view with pagination buttons
        view = LeaderboardView(sorted_users, build_coins_leaderboard_embed, users_per_page=10)
        
        try:
            if int(interaction.channel.id) in ALLOWED_SEND_SET:
                await interaction.response.send_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view, delete_after=15)
        except Exception as e:
            print(f"Error sending leaderboard: {e}")
            # Fallback: send without button
            if int(interaction.channel.id) in ALLOWED_SEND_SET:
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(embed=embed, delete_after=15)
        return
        
    elif lb_type == "activity":
        # Sort users by activity (messages_sent + vc_minutes)
        sorted_users = sorted(
            filtered_xp_data.items(),
            key=lambda x: (x[1].get("messages_sent", 0) + x[1].get("vc_minutes", 0)),
            reverse=True
        )
        
        # Build initial embed (showing top 10 users with fields, page 0)
        embed = build_activity_leaderboard_embed(sorted_users, page=0, users_per_page=10)
        
        # Create view with pagination buttons
        view = LeaderboardView(sorted_users, build_activity_leaderboard_embed, users_per_page=10)
        
        try:
            if int(interaction.channel.id) in ALLOWED_SEND_SET:
                await interaction.response.send_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view, delete_after=15)
        except Exception as e:
            print(f"Error sending leaderboard: {e}")
            # Fallback: send without button
            if int(interaction.channel.id) in ALLOWED_SEND_SET:
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(embed=embed, delete_after=15)
        return
    
    else:
        # Invalid type - show menu
        embed = discord.Embed(
            title="Leaderboards",
            description="Which leaderboard would you like to check?\n᲼᲼",
            color=0x58585f
        )
        embed.add_field(
            name="Levels Leaderboard",
            value="💋 Use `/leaderboard <levels>`",
            inline=False
        )
        embed.add_field(
            name="Coins Leaderboard",
            value="💵 Use `/leaderboard <coins>`",
            inline=False
        )
        embed.add_field(
            name="Activity Leaderboard",
            value="🎀 Use `/leaderboard <activity>`",
            inline=False
        )
        embed.add_field(
            name="᲼᲼",
            value="*I love watching you work hard for me ~*",
            inline=False
        )
        
        if int(interaction.channel.id) in ALLOWED_SEND_SET:
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(embed=embed, delete_after=15)


@bot.tree.command(name="info", description="Show bot information")
async def info(interaction: discord.Interaction):
    """Show bot information."""
    if not await check_user_command_permissions(interaction):
        return
    
    embed = discord.Embed(
        title="IslaBot Information",
        description="A leveling and obedience event bot for Isla's server.",
        color=0xff000d,
    )
    embed.add_field(name="Commands", value="`/level check` - Check your level\n`/leaderboard` - View leaderboards\n`/leaderboard levels` - View levels leaderboard\n`/leaderboard coins` - View coins leaderboard\n`/leaderboard activity` - View activity leaderboard", inline=False)
    embed.add_field(name="XP System", value="Gain XP by sending messages and participating in voice chat.", inline=False)
    embed.add_field(name="Events", value="Participate in obedience events to earn bonus XP and rewards.", inline=False)
    
    await interaction.response.send_message(embed=embed)

# -----------------------------
# Command permission helpers
# -----------------------------
async def check_user_command_permissions(interaction_or_ctx) -> bool:
    """Check if user command can be used. Works with both Interaction and Context. Returns True if allowed, sends error and returns False otherwise.
    User commands are allowed in USER_COMMAND_CHANNEL_ID for anyone (no role check)."""
    if isinstance(interaction_or_ctx, discord.Interaction):
        channel_id = interaction_or_ctx.channel.id
        user = interaction_or_ctx.user
        is_interaction = True
    else:  # Context
        channel_id = interaction_or_ctx.channel.id
        user = interaction_or_ctx.author
        is_interaction = False
    
    if channel_id != USER_COMMAND_CHANNEL_ID:
        if is_interaction:
            await interaction_or_ctx.response.send_message(f"This command can only be used in <#{USER_COMMAND_CHANNEL_ID}>.", ephemeral=True, delete_after=5)
        else:
            await interaction_or_ctx.send(f"This command can only be used in <#{USER_COMMAND_CHANNEL_ID}>.", delete_after=5)
        return False
    
    if not isinstance(user, discord.Member):
        if is_interaction:
            await interaction_or_ctx.response.send_message("This command can only be used in a server.", ephemeral=True)
        else:
            await interaction_or_ctx.send("This command can only be used in a server.", delete_after=5)
        return False
    
    # No role check - anyone can use user commands in the allowed channel
    return True

async def check_admin_command_permissions(interaction_or_ctx) -> bool:
    """Check if admin command can be used. Works with both Interaction and Context. Returns True if allowed, sends error and returns False otherwise.
    Admin commands are restricted to ADMIN_COMMAND_CHANNEL_ID and require admin roles."""
    if isinstance(interaction_or_ctx, discord.Interaction):
        channel_id = interaction_or_ctx.channel.id
        user = interaction_or_ctx.user
        is_interaction = True
    else:  # Context
        channel_id = interaction_or_ctx.channel.id
        user = interaction_or_ctx.author
        is_interaction = False
    
    if channel_id != ADMIN_COMMAND_CHANNEL_ID:
        if is_interaction:
            await interaction_or_ctx.response.send_message(f"This command can only be used in <#{ADMIN_COMMAND_CHANNEL_ID}>.", ephemeral=True, delete_after=5)
        else:
            await interaction_or_ctx.send(f"This command can only be used in <#{ADMIN_COMMAND_CHANNEL_ID}>.", delete_after=5)
        return False
    
    if not isinstance(user, discord.Member):
        if is_interaction:
            await interaction_or_ctx.response.send_message("This command can only be used in a server.", ephemeral=True)
        else:
            await interaction_or_ctx.send("This command can only be used in a server.", delete_after=5)
        return False
    
    if not any(int(role.id) in ADMIN_ROLE_IDS for role in user.roles):
        if is_interaction:
            await interaction_or_ctx.response.send_message("You don't have permission to use this command.", ephemeral=True, delete_after=5)
        else:
            await interaction_or_ctx.send("You don't have permission to use this command.", delete_after=5)
        return False
    
    return True

# -----------------------------
# Gambling Commands
# -----------------------------

@bot.tree.command(name="balance", description="Show your coin balance and level info")
async def balance(interaction: discord.Interaction):
    """Show user's coin balance and level info."""
    if not await check_user_command_permissions(interaction):
        return
    
    user_id = interaction.user.id
    coins = get_coins(user_id)
    level = get_level(user_id)
    
    # Find next level with bonus
    next_bonus_level = None
    for bonus_level in sorted(LEVEL_COIN_BONUSES.keys()):
        if bonus_level > level:
            next_bonus_level = bonus_level
            break
    
    next_bonus_text = f"Level {next_bonus_level} ({LEVEL_COIN_BONUSES[next_bonus_level]} coins)" if next_bonus_level else "Max level reached"
    
    embed = discord.Embed(
        title="Balance",
        description=f"Coins: **{coins}**\n᲼᲼",
        color=0xff000d,
    )
    embed.add_field(name="Current Level:", value=str(level), inline=True)
    embed.add_field(name="Next Level Bonus:", value=next_bonus_text, inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Claim your daily coins")
async def daily(interaction: discord.Interaction):
    """Claim daily coins."""
    if not await check_user_command_permissions(interaction):
        return
    
    user_id = interaction.user.id
    on_cooldown, reset_timestamp = check_daily_cooldown(user_id)
    
    if on_cooldown:
        embed = discord.Embed(
            title="Daily 🎁",
            description="You've already claimed your daily reward today.",
            color=0xff000d,
        )
        embed.set_footer(text="Resets at 6:00 PM GMT")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Calculate daily coins based on level
    level = get_level(user_id)
    base_daily = min(500, int(100 + (level * 4.5)))
    bonus = 100 if level >= 100 else 0
    daily_amount = base_daily + bonus
    
    # Weekend bonus (Friday, Saturday, Sunday)
    uk_tz = get_timezone("Europe/London")
    if uk_tz:
        if USE_PYTZ:
            now_uk = datetime.datetime.now(uk_tz)
        else:
            now_uk = datetime.datetime.now(uk_tz)
        weekday = now_uk.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
        if weekday >= 4:  # Friday (4), Saturday (5), Sunday (6)
            daily_amount += 25
            weekend_bonus = True
        else:
            weekend_bonus = False
    else:
        weekend_bonus = False
    
    add_coins(user_id, daily_amount)
    update_daily_cooldown(user_id)
    save_xp_data()
    
    description = f"Claimed **{daily_amount}** coins!"
    if weekend_bonus:
        description += f"\n*+25 weekend bonus included*"
    
    embed = discord.Embed(
        title="Daily 🎁",
        description=description,
        color=0xff000d,
    )
    embed.set_footer(text="Resets at 6:00 PM GMT")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="give", description="Give coins to another user")
@app_commands.describe(member="The user to give coins to", amount="The amount of coins to give")
async def give(interaction: discord.Interaction, member: discord.Member, amount: int):
    """Give coins to another user."""
    if not await check_user_command_permissions(interaction):
        return
    
    if amount <= 0:
        await interaction.response.send_message("Amount must be positive.", ephemeral=True, delete_after=5)
        return
    
    user_id = interaction.user.id
    on_cooldown, reset_timestamp = check_give_cooldown(user_id)
    
    if on_cooldown:
        embed = discord.Embed(
            title="Gift 🎁",
            description="You've already given coins today.",
            color=0xff000d,
        )
        embed.set_footer(text="Gifts reset daily at 6:00 PM GMT")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if not has_coins(user_id, amount):
        await interaction.response.send_message("You don't have enough coins.", ephemeral=True, delete_after=5)
        return
    
    # Transfer coins
    add_coins(user_id, -amount)
    add_coins(member.id, amount)
    update_give_cooldown(user_id)
    save_xp_data()
    
    embed = discord.Embed(
        title="Gift 🎁",
        description=f"Gave **{amount}** coins to {member.mention}",
        color=0xff000d,
    )
    embed.set_footer(text="Gifts reset daily at 6:00 PM GMT")
    await interaction.response.send_message(content=member.mention, embed=embed)

@bot.tree.command(name="gamble", description="Gamble coins - 49/51 chance to double or lose")
@app_commands.describe(bet="The amount of coins to bet (minimum 10)")
async def gamble(interaction: discord.Interaction, bet: int):
    """Gamble coins - 49/51 chance to double or lose."""
    if not await check_user_command_permissions(interaction):
        return
    
    if not events_enabled:  # Using events_enabled as gambling enabled flag
        embed = discord.Embed(
            title="Gambling Disabled 🚧",
            description="Gambling is currently disabled.",
            color=0xffae00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if bet < 10:
        embed = discord.Embed(
            title="Invalid Bet Amount ⚠️",
            description="You must bet at least 10 coins.",
            color=0xffae00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = interaction.user.id
    on_cooldown, seconds_left = check_gambling_cooldown(user_id)
    
    if on_cooldown:
        embed = discord.Embed(
            title="Slow Down! ⏳",
            description=f"You can gamble again in {seconds_left} seconds.",
            color=0xffae00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if not has_coins(user_id, bet):
        embed = discord.Embed(
            title="Invalid Bet ⚠️",
            description="You don't have enough coins.",
            color=0xffae00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Check for big bet (>10000)
    big_bet_messages = [
        "So confident. If luck favors you, I'll have a little present ready.",
        "Big gamble. Impress me, and I won't let it go unnoticed.",
        "That's a lot for someone like you. Win, and maybe I'll be generous.",
        "Such confidence… or desperation. Either way, win and I'll give you something.",
    ]
    
    is_big_bet = bet > 10000
    if is_big_bet:
        embed = discord.Embed(
            description=f"*{random.choice(big_bet_messages)}*",
            color=0xffae00,
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(1)  # Brief pause
    else:
        await interaction.response.defer()
    
    # Execute gamble (49/51 - 49% win, 51% lose)
    increment_gambling_attempt(user_id)
    add_gambling_spent(user_id, bet)  # Track total money spent
    won = random.random() < 0.49
    update_gambling_cooldown(user_id)
    streak = update_gambling_streak(user_id, won)
    
    if won:
        increment_gambling_win(user_id)
        winnings = bet * 2
        add_coins(user_id, bet)  # Return bet + winnings
        save_xp_data()
        
        if is_big_bet:
            # Big bet win - send DM
            win_messages = [
                "Interesting. You actually won. DMs.",
                "Huh. Even you pulled it off. Check your DMs.",
                "Lucky. Check your DMs before I change my mind.",
            ]
            embed = discord.Embed(
                title=f"Won {bet} Coins",
                description=f"*{random.choice(win_messages)}*",
                color=0x1bbe19,
            )
            await interaction.followup.send(embed=embed)
            
            # Send DM with present
            try:
                user = await bot.fetch_user(user_id)
                image_variations = [
                    "https://i.imgur.com/GcH758a.png",
                    "https://i.imgur.com/jMcRIoX.png",
                    "https://i.imgur.com/9Fs1a84.png",
                    "https://i.imgur.com/G1J4kKW.png",
                    "https://i.imgur.com/g3gp6g5.png",
                ]
                dm_embed = discord.Embed(
                    title="Present from Isla",
                    description="*If you like the view, share some of your winnings with me*\n\n[Go to Throne](https://throne.com/lsla)",
                    color=0xff000d,
                )
                dm_embed.set_image(url=random.choice(image_variations))
                await user.send(embed=dm_embed)
            except:
                pass
        else:
            # Regular win
            win_messages = [
                "You won something. Don't get used to it.",
                "Huh. You actually won.",
                "Even you can win sometimes.",
                "A win. We'll see how long it lasts.",
            ]
            embed = discord.Embed(
                title=f"Won {bet} Coins",
                description=f"*{random.choice(win_messages)}*",
                color=0x1bbe19,
            )
            await interaction.followup.send(embed=embed)
    else:
        # Loss
        add_coins(user_id, -bet)
        save_xp_data()
        
        if is_big_bet:
            loss_messages = [
                "That was a lot to lose.\nSit with it.",
                "Gone.\nAll of it.",
                "You felt confident a moment ago.\nInteresting.",
                "That silence after losing… I like it.",
            ]
            embed = discord.Embed(
                title=f"Lost {bet} Coins",
                description=f"*{random.choice(loss_messages)}*",
                color=0xaf0808,
            )
            await interaction.followup.send(embed=embed)
        else:
            loss_messages = [
                "You lost. That was predictable.",
                "No luck this time. Try again.",
                "Unlucky. That didn't go your way.",
                "Loss. But you seem used to that.",
                "That didn't work out. Again?",
                "Loss confirmed. What's your next move?",
                "You lost. Surely you won't stop now.",
                "No reward this time. Go again.",
            ]
            embed = discord.Embed(
                title=f"Lost {bet} Coins",
                description=f"*{random.choice(loss_messages)}*",
                color=0xaf0808,
            )
            await interaction.followup.send(embed=embed)

@bot.tree.command(name="gambleinfo", description="Show gamble command info")
async def gambleinfo(interaction: discord.Interaction):
    """Show gamble command info."""
    if not await check_user_command_permissions(interaction):
        return
    
    embed = discord.Embed(
        title="🎲 The Gamble Table",
        description="*One move decides everything.*\n\n**How to Play**\nUse: /gamble <bet>\nPlace your Coins and let fate choose.\n\n**💰 Payout**\nWin: x2 (double your bet)\nLose: lose the full bet\n\n**📜 Table Rules**\nMinimum bet: 10 Coins\nCooldown: 10 seconds",
        color=0xffae00,
    )
    embed.set_image(url="https://i.imgur.com/fgTsEZy.png")
    embed.set_footer(text="Use /gamble <bet> like a good dog.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="dice", description="Roll dice - win if your roll > dealer roll")
@app_commands.describe(bet="The amount of coins to bet (minimum 50)")
async def dice(interaction: discord.Interaction, bet: int):
    """Roll dice - win if your roll > dealer roll."""
    if not await check_user_command_permissions(interaction):
        return
    
    if not events_enabled:
        embed = discord.Embed(
            title="Dice Table Closed 🚧",
            description="Gambling is currently disabled.",
            color=0xffae00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if bet < 50:
        embed = discord.Embed(
            title="Invalid Bet Amount ❌",
            description="You must bet at least 50 coins.",
            color=0xffae00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    
    user_id = interaction.user.id
    on_cooldown, seconds_left = check_gambling_cooldown(user_id)
    
    if on_cooldown:
        embed = discord.Embed(
            title="Slow Down! ⏳",
            description=f"You can roll the dice again in {seconds_left} seconds.",
            color=0xffae00,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    if not has_coins(user_id, bet):
        embed = discord.Embed(
            title="Invalid Bet ⚠️",
            description="You don't have enough coins.",
            color=0xffae00,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    
    # Roll dice (1-6 for both)
    increment_gambling_attempt(user_id)
    add_gambling_spent(user_id, bet)  # Track total money spent
    user_roll = random.randint(1, 6)
    dealer_roll = random.randint(1, 6)
    
    update_gambling_cooldown(user_id)
    
    if user_roll > dealer_roll:
        # Win
        increment_gambling_win(user_id)
        add_coins(user_id, bet)
        save_xp_data()
        streak = update_gambling_streak(user_id, True)
        embed = discord.Embed(
            title="Dice Roll 🎲",
            description=f"You rolled: {user_roll}\nDealer rolled: {dealer_roll}\n\n✅ You won +{bet} coins.",
            color=0x1bbe19,
        )
        await interaction.followup.send(embed=embed)
    elif user_roll < dealer_roll:
        # Lose
        add_coins(user_id, -bet)
        save_xp_data()
        streak = update_gambling_streak(user_id, False)
        embed = discord.Embed(
            title="Dice Roll 🎲",
            description=f"You rolled: {user_roll}\nDealer rolled: {dealer_roll}\n\n❌ You lost {bet} coins.",
            color=0xaf0808,
        )
        await interaction.followup.send(embed=embed)
    else:
        # Tie - refund
        embed = discord.Embed(
            title="It's a Tie! 🎲",
            description=f"Both rolled {user_roll}.\n\nYour bet has been returned.",
            color=0xffae00,
        )
        await interaction.followup.send(embed=embed)

@bot.tree.command(name="diceinfo", description="Show dice command info")
async def diceinfo(interaction: discord.Interaction):
    """Show dice command info."""
    if not await check_user_command_permissions(interaction):
        return
    
    embed = discord.Embed(
        title="🎲 Dice Game",
        description="**How to Play:**\nRoll a die (1-6). If your roll is higher than the dealer's, you win!\n\n**Rules:**\nMinimum bet: 50 coins\nCooldown: 10 seconds\nTie: Bet returned",
        color=0xffae00,
    )
    await interaction.response.send_message(embed=embed)

# Slots configuration
SLOTS_SYMBOLS = {
    "🥝": {"multiplier": 1.5, "weight": 28},
    "🍇": {"multiplier": 2, "weight": 22},
    "🍋": {"multiplier": 3, "weight": 18},
    "🍑": {"multiplier": 5, "weight": 12},
    "🍉": {"multiplier": 8, "weight": 8},
    "🍒": {"multiplier": 15, "weight": 4},
    "👑": {"multiplier": 30, "weight": 2},
    "🎁": {"multiplier": 0, "weight": 2},  # Bonus symbol
}

def spin_slots_reels():
    """Spin the slots reels and return [symbol1, symbol2, symbol3]."""
    # Create weighted list
    weighted_symbols = []
    for symbol, data in SLOTS_SYMBOLS.items():
        weighted_symbols.extend([symbol] * data["weight"])
    
    return [secrets.choice(weighted_symbols) for _ in range(3)]

def calculate_slots_payout(reels, bet):
    """Calculate slots payout. Returns (payout, win_type, message)."""
    # Check for 3-of-a-kind
    if reels[0] == reels[1] == reels[2]:
        symbol = reels[0]
        if symbol == "🎁":
            # 3 bonus symbols - mega bonus
            return (0, "mega_bonus", "🎁 You gained 5 Free Spins")
        
        multiplier = SLOTS_SYMBOLS[symbol]["multiplier"]
        payout = int(bet * multiplier)
        return (payout, "win", f"Win x{multiplier}")
    
    # Check for 2-of-a-kind (small win)
    if reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        # Find the matching pair
        if reels[0] == reels[1]:
            symbol = reels[0]
        elif reels[1] == reels[2]:
            symbol = reels[1]
        else:
            symbol = reels[0]
        
        if symbol != "🎁" and SLOTS_SYMBOLS[symbol]["multiplier"] > 0:
            multiplier = 0.5
            loss_amount = int(bet * multiplier)
            return (0, "loss", f"Lost {loss_amount} coins")
    
    # Check for bonus symbols
    bonus_count = reels.count("🎁")
    if bonus_count == 2:
        # Big bonus - 2 free spins
        return (250, "big_bonus", "🎁 You gained 2 Free Spins\n\nBonus payout: +250 chips")
    elif bonus_count == 1:
        # Mini bonus
        # Check if there's a 2-of-a-kind with the bonus
        other_symbols = [s for s in reels if s != "🎁"]
        if len(set(other_symbols)) == 1:
            # 2 of same + bonus
            symbol = other_symbols[0]
            if symbol in SLOTS_SYMBOLS and SLOTS_SYMBOLS[symbol]["multiplier"] > 0:
                multiplier = 0.8
                payout = int(bet * multiplier)
                return (payout, "bonus_win", f"Win x{multiplier}")
        else:
            # Just 1 bonus
            return (0, "mini_bonus", "🎁 Bonus payout: +0 coins")
    
    # No win
    return (0, "loss", None)

# Slots command group
slots_group = app_commands.Group(name="slots", description="Play slots games")

@slots_group.command(name="bet", description="Bet on slots")
@app_commands.describe(bet="The amount of coins to bet (minimum 10)")
async def slots_bet(interaction: discord.Interaction, bet: int):
    """Play slots with a bet."""
    if not await check_user_command_permissions(interaction):
        return
    
    if not events_enabled:
        embed = discord.Embed(
            description="🚧 Gambling is currently disabled.",
            color=0xffae00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = interaction.user.id
    
    if bet < 10:
        await interaction.response.send_message("Minimum bet is 10 coins.", ephemeral=True, delete_after=5)
        return
    
    on_cooldown, seconds_left = check_gambling_cooldown(user_id)
    if on_cooldown:
        embed = discord.Embed(
            title="Slow Down! ⏳",
            description=f"You can spin again in {seconds_left} seconds.",
            color=0xffae00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    if not has_coins(user_id, bet):
        await interaction.response.send_message("You don't have enough coins.", ephemeral=True, delete_after=5)
        return
    
    await interaction.response.defer()
    
    # Deduct bet and track spending
    increment_gambling_attempt(user_id)
    add_coins(user_id, -bet)
    add_gambling_spent(user_id, bet)  # Track total money spent
    save_xp_data()
    
    # Spin
    reels = spin_slots_reels()
    payout, win_type, message = calculate_slots_payout(reels, bet)
    
    # Handle x0.5 loss (2-of-a-kind) - refund half since bet was already deducted
    if win_type == "loss" and message and "Lost" in message:
        # Extract loss amount from message
        loss_match = re.search(r"Lost (\d+) coins", message)
        if loss_match:
            loss_amount = int(loss_match.group(1))
            # Bet was already deducted, so refund half (since they only lose half)
            refund = bet - loss_amount
            if refund > 0:
                add_coins(user_id, refund)
            save_xp_data()
    
    # Update streak (only for regular spins, not free spins)
    if win_type in ["win", "bonus_win"]:
        increment_gambling_win(user_id)
        streak = update_gambling_streak(user_id, True)
    elif win_type == "loss":
        streak = update_gambling_streak(user_id, False)
    else:
        streak = 0  # Bonuses don't affect streak
    
    # Award payout
    if payout > 0:
        add_coins(user_id, payout)
        save_xp_data()
    
    # Create embed based on win type
    if win_type == "loss":
        # Check if it's a x0.5 loss (2-of-a-kind)
        if message and "Lost" in message:
            loss_match = re.search(r"Lost (\d+) coins", message)
            if loss_match:
                loss_amount = int(loss_match.group(1))
                embed = discord.Embed(
                    title="🎰 Lucky Loss",
                    description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼\n❌ You lost {loss_amount} coins.",
                    color=0xaf0808,
                )
            else:
                embed = discord.Embed(
                    title="🎰 Loss",
                    description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼\n❌ You lost {bet} coins.",
                    color=0xaf0808,
                )
        else:
            embed = discord.Embed(
                title="🎰 Loss",
                description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼\n❌ You lost {bet} coins.",
                color=0xaf0808,
            )
    elif win_type == "win":
        multiplier = payout // bet if bet > 0 else 0
        if multiplier == 8:
            embed = discord.Embed(
                title="🎰 Nice Hit!",
                description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼\n✅ Win x{multiplier}  💵 {payout} coins received.",
                color=0x1bbe19,
            )
        elif multiplier == 15:
            embed = discord.Embed(
                title="🎰 BIG WIN!",
                description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼\n✅ Win x{multiplier}  💰 {payout} coins received.",
                color=0x1bbe19,
            )
        elif multiplier == 30:
            embed = discord.Embed(
                title="🎰 JACKPOT! 🎉",
                description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼\n✅ Win x{multiplier}  👑 {payout} coins received.\n\n*Oh? A jackpot. Good doggy—remember how rare this is.*",
                color=0x1bbe19,
            )
            embed.set_image(url="https://i.imgur.com/ZQOOc9n.png")
            
            # Send jackpot announcement to events channel
            if interaction.guild:
                try:
                    await send_jackpot_announcement(interaction.guild, interaction.user)
                except Exception as e:
                    print(f"Failed to send jackpot announcement: {e}")
        else:
            embed = discord.Embed(
                title="🎰 Lucky Spin",
                description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼\n✅ {message}  🪙 {payout} coins received.",
                color=0x1bbe19,
            )
        streak_flair = get_streak_flair(streak)
        if streak_flair:
            embed.set_footer(text=streak_flair)
    elif win_type == "bonus_win":
        embed = discord.Embed(
            title="🎰 BONUS ACTIVATED!",
            description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼\n✅ {message}  🪙 {payout} coins received.",
            color=0x1bbe19,
        )
    elif win_type == "mini_bonus":
        embed = discord.Embed(
            title="🎰 Mini Bonus!",
            description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼\n🎁 Bonus payout: {payout} coins.",
            color=0x1bbe19,
        )
    elif win_type == "big_bonus":
        free_spin_data = slots_free_spins.get(user_id, {"count": 0, "total_winnings": 0})
        free_spin_data["count"] = free_spin_data.get("count", 0) + 2
        slots_free_spins[user_id] = free_spin_data
        embed = discord.Embed(
            title="🎰 BIG BONUS!",
            description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼\n{message}",
            color=0x1bbe19,
        )
        embed.set_footer(text="Use /slots free")
    elif win_type == "mega_bonus":
        free_spin_data = slots_free_spins.get(user_id, {"count": 0, "total_winnings": 0})
        free_spin_data["count"] = free_spin_data.get("count", 0) + 5
        slots_free_spins[user_id] = free_spin_data
        embed = discord.Embed(
            title="🎰 MEGA BONUS ACTIVATED!",
            description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼\n🎁 You gained 5 Free Spins",
            color=0x1bbe19,
        )
        embed.set_footer(text="Use /slots free")
    
    await interaction.followup.send(embed=embed)

@slots_group.command(name="free", description="Use a free spin")
async def slots_free(interaction: discord.Interaction):
    """Use a free spin."""
    if not await check_user_command_permissions(interaction):
        return
    
    if not events_enabled:
        embed = discord.Embed(
            description="🚧 Gambling is currently disabled.",
            color=0xffae00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = interaction.user.id
    
    # Handle free spins
    free_spin_data = slots_free_spins.get(user_id, {"count": 0, "total_winnings": 0})
    free_spins = free_spin_data.get("count", 0)
    if free_spins <= 0:
        embed = discord.Embed(
            description="❌ You don't have any free spins right now.",
            color=0xffae00,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    
    # Use one free spin
    free_spin_data["count"] = free_spins - 1
    remaining = free_spin_data["count"]
    
    # Spin
    reels = spin_slots_reels()
    payout, win_type, message = calculate_slots_payout(reels, 0)  # Free spins use 0 bet for calculation
    
    # Track total winnings
    if payout > 0:
        free_spin_data["total_winnings"] = free_spin_data.get("total_winnings", 0) + payout
    
    # Handle bonus symbols in free spins
    bonus_count = reels.count("🎁")
    if bonus_count == 3:
        free_spin_data["count"] += 3
        remaining = free_spin_data["count"]
    elif bonus_count == 2:
        free_spin_data["count"] += 2
        remaining = free_spin_data["count"]
    elif bonus_count == 1:
        free_spin_data["count"] += 1
        remaining = free_spin_data["count"]
    
    # Update storage
    slots_free_spins[user_id] = free_spin_data
    
    # Award payout (if any)
    if payout > 0:
        add_coins(user_id, payout)
        save_xp_data()
    
    # Create embed
    if remaining == 0:
        # Last free spin
        total_winnings = free_spin_data.get("total_winnings", 0)
        embed = discord.Embed(
            title="🎰 BONUS COMPLETE",
            description=f"Total Bonus Winnings: {total_winnings:,} coins.",
            color=0x1bbe19 if total_winnings > 0 else 0xffae00,
        )
        # Clear free spin data
        slots_free_spins.pop(user_id, None)
    else:
        if bonus_count > 0:
            bonus_messages = {
                1: "+1 Free Spin",
                2: "+2 Free Spins",
                3: "+3 Free Spins",
            }
            embed = discord.Embed(
                title=f"🎰 FREE SPIN — {'Mini Bonus!' if bonus_count == 1 else 'Big Bonus!' if bonus_count == 2 else 'Mega Bonus!'}",
                description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼\n🎁 {bonus_messages[bonus_count]}",
                color=0x1bbe19,
            )
            embed.set_footer(text=f"Free Spins Remaining: {remaining}")
        else:
            embed = discord.Embed(
                title="🎰 FREE SPIN",
                description=f"᲼᲼\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n᲼᲼",
                color=0x1bbe19 if payout > 0 else 0xffae00,
            )
            if payout > 0:
                embed.description += f"\n\n✅ Win +{payout} coins"
            embed.set_footer(text=f"Free Spins Remaining: {remaining}")
            
            # Check if free spin hit jackpot (3 👑)
            if reels[0] == reels[1] == reels[2] == "👑":
                # Send jackpot announcement to events channel
                if interaction.guild:
                    try:
                        await send_jackpot_announcement(interaction.guild, interaction.user)
                    except Exception as e:
                        print(f"Failed to send jackpot announcement from free spin: {e}")
    
    await interaction.followup.send(embed=embed)

# Register the slots group
bot.tree.add_command(slots_group)


# Register the level group
bot.tree.add_command(level_group)

@bot.tree.command(name="slotspaytable", description="Show slots paytable")
async def slotspaytable(interaction: discord.Interaction):
    """Show slots paytable."""
    if not await check_user_command_permissions(interaction):
        return
    
    embed = discord.Embed(
        title="🎰 Slots Paytable (3-of-a-kind)",
        description="🥝 x1.5 • 🍇 x2 • 🍋 x3 • 🍑 x5 \n🍉 x8 • 🍒 x15 • 👑 x30\n\n🎁 Bonus Roll\n\nPayout = bet × multiplier",
        color=0xff000d,
    )
    embed.set_image(url="https://i.imgur.com/fgTsEZy.png")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="slotsinfo", description="Show slots info")
async def slotsinfo(interaction: discord.Interaction):
    """Show slots info."""
    if not await check_user_command_permissions(interaction):
        return
    
    embed = discord.Embed(
        title="🎰 Isla's Lucky Slots",
        description="**Reels:**\n[🥝] [🍉] [🍒]\n\n**Payouts (3-of-a-kind):**\n🥝 x1.5 • 🍇 x2 • 🍋 x3 • 🍑 x5\n🍉 x8 • 🍒 x15 • 👑 x30 (JACKPOT)\n\n**Bonus:**\n1x 🎁 = Mini Bonus\n2x 🎁 = Big Bonus (2 Free Spins)\n3x 🎁 = Mega Bonus (5 Free Spins)\n\n**Free Spins:**\nUse /slots free (costs 0 Coins)\n\n**Streak Flair:**\n🔥 Hot streak = 3 wins\n🥶 Cold streak = 5 losses",
        color=0xffae00,
    )
    embed.set_image(url="https://i.imgur.com/fgTsEZy.png")
    embed.set_footer(text="Use /slots bet <amount> like a good dog.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="casinoinfo", description="Show casino info")
async def casinoinfo(interaction: discord.Interaction):
    """Show casino info."""
    if not await check_user_command_permissions(interaction):
        return
    
    embed = discord.Embed(
        title="🎲 Welcome to my Casino",
        description="*I wonder… are you brave enough to touch my games, or will you hesitate like the rest?*\n\n**My Games are Waiting for you**\n🎰 Slots — Spin the reels with /slots bet <bet>\n🎲 Dice — Roll your luck with /dice <bet>\n\nEach game is fast, fair, and unforgiving… just the way I like it.\n\n**Betting Basics:**\nMinimum and maximum bets apply.\nCooldowns keep the tables smooth.\nWins are paid instantly in Coins.\n\n**🎁 Tempting Extras**\nWinners who win big receive a special reward ♥",
        color=0xffae00,
    )
    embed.set_image(url="https://i.imgur.com/fgTsEZy.png")
    embed.set_footer(text="Use /slots bet <bet> like a good dog.")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="coinflip", description="Coin flip - same as gamble (49/51 chance)")
@app_commands.describe(bet="The amount of coins to bet (minimum 10)")
async def coinflip(interaction: discord.Interaction, bet: int):
    """Coin flip - same as gamble (49/51 chance)."""
    # Just call the gamble command logic
    await gamble(interaction, bet)

@bot.tree.command(name="coinflipinfo", description="Show coinflip info")
async def coinflipinfo(interaction: discord.Interaction):
    """Show coinflip info."""
    # Same as gamble info
    await gambleinfo(interaction)

@bot.tree.command(name="allin", description="Go all-in on a game (bet all coins)")
@app_commands.describe(game="The game to play (gamble, dice, or slots)")
async def allin(interaction: discord.Interaction, game: str):
    """Go all-in on a game (bet all coins)."""
    if not await check_user_command_permissions(interaction):
        return
    
    user_id = interaction.user.id
    all_coins = get_coins(user_id)
    
    if all_coins < 10:
        await interaction.response.send_message("You need at least 10 coins to gamble.", ephemeral=True, delete_after=5)
        return
    
    # Route to appropriate game
    game_lower = game.lower()
    if game_lower in ["gamble", "bet", "coinflip", "cf"]:
        await gamble(interaction, all_coins)
    elif game_lower == "dice":
        if all_coins < 50:
            await interaction.response.send_message("Dice requires at least 50 coins.", ephemeral=True, delete_after=5)
            return
        await dice(interaction, all_coins)
    elif game_lower == "slots":
        await slots_bet(interaction, all_coins)
    else:
        await interaction.response.send_message("Invalid game. Use: gamble, dice, or slots", ephemeral=True, delete_after=5)

@bot.tree.command(name="store", description="Show the store")
async def store(interaction: discord.Interaction):
    """Show the store (placeholder for now)."""
    if not await check_user_command_permissions(interaction):
        return
    
    embed = discord.Embed(
        title="🏪 Store",
        description="The store is coming soon...\n\nSpend your coins on exclusive rewards!",
        color=0xff000d,
    )
    await interaction.response.send_message(embed=embed)

# -----------------------------
# Gambling helper functions
# -----------------------------
def get_uk_6pm_timestamp():
    """Get next 6pm UK time as Unix timestamp."""
    uk_tz = datetime.timezone(datetime.timedelta(hours=0))  # UK is UTC+0 (or UTC+1 in summer, but using UTC for simplicity)
    now = datetime.datetime.now(uk_tz)
    target_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
    if now.hour >= 18:
        target_time += datetime.timedelta(days=1)
    return int(target_time.timestamp())

def get_next_scheduled_time(hour: int, minute: int) -> int:
    """Get next occurrence of a scheduled time in UK timezone as Unix timestamp."""
    uk_tz = get_timezone("Europe/London")
    if uk_tz is None:
        # Fallback to UTC if timezone not available
        uk_tz = datetime.timezone.utc
    
    if USE_PYTZ:
        now_uk = datetime.datetime.now(uk_tz)
    else:
        now_uk = datetime.datetime.now(uk_tz)
    
    target_time = now_uk.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # If the time has already passed today (or is exactly now), move to next occurrence
    if target_time <= now_uk:
        target_time += datetime.timedelta(days=1)
    
    # Convert to UTC for timestamp calculation
    if USE_PYTZ:
        target_utc = target_time.astimezone(datetime.timezone.utc)
    else:
        target_utc = target_time.astimezone(datetime.timezone.utc)
    
    return int(target_utc.timestamp())

def check_gambling_cooldown(user_id):
    """Check if user is on gambling cooldown. Returns (on_cooldown, seconds_remaining)."""
    if user_id not in gambling_cooldowns:
        return False, 0
    last_time = gambling_cooldowns[user_id]
    time_since = (datetime.datetime.now(datetime.UTC) - last_time).total_seconds()
    if time_since >= 10:
        return False, 0
    return True, int(10 - time_since)

def update_gambling_cooldown(user_id):
    """Update gambling cooldown for user."""
    gambling_cooldowns[user_id] = datetime.datetime.now(datetime.UTC)

def check_daily_cooldown(user_id):
    """Check if user can claim daily. Returns (on_cooldown, reset_timestamp)."""
    reset_timestamp = get_uk_6pm_timestamp()
    if user_id not in daily_cooldowns:
        return False, reset_timestamp
    last_claim = daily_cooldowns[user_id]
    # Check if it's past 6pm UK today
    now = datetime.datetime.now(datetime.UTC)
    if now >= last_claim + datetime.timedelta(days=1):
        # Check if it's past 6pm UK
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
    # Check if it's past 6pm UK today
    now = datetime.datetime.now(datetime.UTC)
    if now >= last_give + datetime.timedelta(days=1):
        # Check if it's past 6pm UK
        uk_tz = datetime.timezone(datetime.timedelta(hours=0))
        uk_now = datetime.datetime.now(uk_tz)
        if uk_now.hour >= 18:
            return False, reset_timestamp
    return True, reset_timestamp

def update_give_cooldown(user_id):
    """Update give cooldown for user."""
    give_cooldowns[user_id] = datetime.datetime.now(datetime.UTC)

def update_gambling_streak(user_id, won):
    """Update gambling streak for user. Returns streak count."""
    now = datetime.datetime.now(datetime.UTC)
    
    if user_id not in gambling_streaks:
        gambling_streaks[user_id] = {"streak": 0, "last_activity": now}
    
    streak_data = gambling_streaks[user_id]
    
    # Check if inactive for 1 hour - reset streak
    time_since = (now - streak_data["last_activity"]).total_seconds()
    if time_since >= 3600:
        streak_data["streak"] = 0
    
    # Update streak
    if won:
        if streak_data["streak"] < 0:
            streak_data["streak"] = 1  # Break cold streak
        else:
            streak_data["streak"] += 1
    else:
        if streak_data["streak"] > 0:
            streak_data["streak"] = -1  # Break hot streak
        else:
            streak_data["streak"] -= 1
    
    streak_data["last_activity"] = now
    return streak_data["streak"]

def get_streak_flair(streak):
    """Get streak flair text. Returns None if no flair should be shown."""
    if streak >= 3:
        return f"🔥 Hot streak! ({streak} wins in a row)"
    elif streak <= -5:
        return f"🥶 Cold streak ({abs(streak)} losses in a row)"
    return None

# -----------------------------
# XP tracking for messages
# -----------------------------
message_cooldowns = {}

@bot.event
async def on_message(message):
    resolved_channel_id = resolve_channel_id(message.channel)
    print(f"[MESSAGE] {message.author.name} in #{message.channel} (ID: {resolved_channel_id}): {message.content[:50]}")
    
    if message.author.bot:
        print("  ↳ Skipped: Bot message")
        return

    # Check if user has the bot role
    if isinstance(message.author, discord.Member):
        if any(int(role.id) in EXCLUDED_ROLE_SET for role in message.author.roles):
            print(f"  ↳ Skipped: User has bot role")
            return

        # Channel permission checks for special event channels
        # Event 7 Phase 2 channel - requires opt-in role
        if resolved_channel_id == EVENT_PHASE2_CHANNEL_ID:
            opt_in_role = message.guild.get_role(EVENT_PHASE2_ALLOWED_ROLE)
            if opt_in_role and opt_in_role not in message.author.roles:
                print(f"  ↳ Blocked: User {message.author.name} doesn't have required role for Phase 2 channel")
                try:
                    await message.delete()
                except:
                    pass
                return
        
        # Event 7 Phase 3 Success channel - requires success role
        if resolved_channel_id == EVENT_PHASE3_SUCCESS_CHANNEL_ID:
            has_success_role = any(int(role.id) in EVENT_PHASE3_SUCCESS_ROLES for role in message.author.roles)
            if not has_success_role:
                print(f"  ↳ Blocked: User {message.author.name} doesn't have required role for Success channel")
                try:
                    await message.delete()
                except:
                    pass
                return
        
        # Event 7 Phase 3 Failure channel - requires failure role
        if resolved_channel_id == EVENT_PHASE3_FAILED_CHANNEL_ID:
            has_failed_role = any(int(role.id) in EVENT_PHASE3_FAILED_ROLES for role in message.author.roles)
            if not has_failed_role:
                print(f"  ↳ Blocked: User {message.author.name} doesn't have required role for Failure channel")
                try:
                    await message.delete()
                except:
                    pass
                return

    # Reply system for introduction channel
    if resolved_channel_id == REPLY_CHANNEL_ID and isinstance(message.author, discord.Member):
        quote = get_reply_quote(message.author)
        embed = discord.Embed(
            description=f"*{quote}*",
            color=0xff000d
        )
        try:
            await message.reply(embed=embed)
            print(f"  ↳ Replied to {message.author.name} with quote: {quote[:50]}...")
        except Exception as e:
            print(f"  ↳ Failed to reply: {e}")
        
        # Add automated reaction to all messages in introduction channel
        try:
            await message.add_reaction("❤️")
            print(f"  ↳ Added ❤️ reaction to message from {message.author.name}")
        except Exception as e:
            print(f"  ↳ Failed to add reaction: {e}")

    # Obedience event tracking - process BEFORE exclusion checks so event messages work in any channel
    await handle_event_message(message)

    # Skip excluded categories
    category_id = resolve_category_id(message.channel)
    if category_id in NON_XP_CATEGORY_IDS:
        print(f"  ↳ Skipped: Category excluded from XP ({category_id})")
        return
    if resolved_channel_id in NON_XP_CHANNEL_IDS:
        print(f"  ↳ Skipped: Channel excluded from XP ({resolved_channel_id})")
        return

    if resolved_channel_id in XP_TRACK_SET:
        print("  ↳ Channel is tracked")
        user_id = message.author.id
        current_time = datetime.datetime.now(datetime.UTC)
        
        # Track messages sent (excluding bot commands)
        # Check if message is a bot command (starts with ! or is a slash command)
        is_bot_command = message.content.startswith('!') or (message.content.startswith('/') and len(message.content) > 1)
        if not is_bot_command:
            uid = str(user_id)
            if uid not in xp_data:
                xp_data[uid] = {
                    "xp": 0, "level": 1, "coins": 0,
                    "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
                    "times_gambled": 0, "total_wins": 0,
                    "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
                    "equipped_collar": None, "equipped_badge": None
                }
            if "messages_sent" not in xp_data[uid]:
                xp_data[uid]["messages_sent"] = 0
            xp_data[uid]["messages_sent"] = xp_data[uid].get("messages_sent", 0) + 1
        
        if user_id in message_cooldowns:
            time_since_last = (current_time - message_cooldowns[user_id]).total_seconds()
            if time_since_last < MESSAGE_COOLDOWN:
                print(f"  ↳ Cooldown active ({MESSAGE_COOLDOWN - time_since_last:.0f}s remaining)")
                return
        
        message_cooldowns[user_id] = current_time
        base_mult = get_channel_multiplier(resolved_channel_id)
        print(f"  ↳ ✅ Adding 10 XP to {message.author.name} (channel mult {base_mult}x)")
        await add_xp(message.author.id, 10, member=message.author, base_multiplier=base_mult)
    else:
        # Check if this is an event channel (expected to not be tracked for XP)
        event_channels = [EVENT_PHASE2_CHANNEL_ID, EVENT_PHASE3_SUCCESS_CHANNEL_ID, EVENT_PHASE3_FAILED_CHANNEL_ID]
        if resolved_channel_id in event_channels:
            print(f"  ↳ Channel not tracked (event channel - XP tracking disabled)")
        else:
            print(f"  ↳ Channel not tracked (ID mismatch)")

# -----------------------------
# Voice chat XP tracking
# -----------------------------
vc_members_time = {}

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
    if any(int(role.id) in EXCLUDED_ROLE_SET for role in getattr(member, "roles", [])):
        return

    # Skip excluded channels/categories
    # Only allow XP tracking in specified voice channels
    if after.channel:
        cat_id = resolve_category_id(after.channel)
        if after.channel.id not in VC_XP_TRACK_CHANNELS:
            after_channel_allowed = False
        elif cat_id in NON_XP_CATEGORY_IDS or after.channel.id in NON_XP_CHANNEL_IDS:
            after_channel_allowed = False
        else:
            after_channel_allowed = True
    else:
        after_channel_allowed = False

    # Obedience event: track silent company presence
    if active_event and active_event.get("type") == 2 and active_event.get("join_times") is not None:
        join_times = active_event["join_times"]
        if after.channel and not before.channel:
            if after_channel_allowed:
                join_times[member.id] = datetime.datetime.now(datetime.UTC)
        if before.channel and not after.channel:
            join_times.pop(member.id, None)

    if after.channel and not before.channel:
        if after_channel_allowed and after.channel.id in VC_XP_TRACK_CHANNELS:
            vc_members_time[member.id] = {"time": datetime.datetime.now(datetime.UTC), "channel_id": after.channel.id}
        print(f"{member.name} joined VC: {after.channel.name}")

    elif before.channel and not after.channel:
        join_data = vc_members_time.pop(member.id, None)
        if join_data:
            join_time = join_data["time"]
            channel_id = join_data.get("channel_id", before.channel.id if before.channel else 0)
        else:
            join_time = None
            channel_id = before.channel.id if before.channel else 0
        if join_time and channel_id in VC_XP_TRACK_CHANNELS:
            seconds = (datetime.datetime.now(datetime.UTC) - join_time).total_seconds()
            minutes = int(seconds // 60)
            if minutes > 0:
                # Track voice chat time
                uid = str(member.id)
                if uid not in xp_data:
                    xp_data[uid] = {
                        "xp": 0, "level": 1, "coins": 0,
                        "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
                        "times_gambled": 0, "total_wins": 0,
                        "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
                        "equipped_collar": None, "equipped_badge": None
                    }
                if "vc_minutes" not in xp_data[uid]:
                    xp_data[uid]["vc_minutes"] = 0
                xp_data[uid]["vc_minutes"] = xp_data[uid].get("vc_minutes", 0) + minutes
                save_xp_data()
                
                # Calculate XP for remaining time when leaving
                # Note: award_vc_xp() handles per-minute XP (including Event 2 double XP)
                # This only handles partial minutes when leaving
                xp_gained = minutes * VC_XP
                
                base_mult = get_channel_multiplier(channel_id)
                await add_xp(member.id, xp_gained, member=member, base_multiplier=base_mult)
                print(f"Added {xp_gained} VC XP to {member.name} ({minutes} minutes) (channel mult {base_mult}x)")
    
    elif before.channel and after.channel and before.channel != after.channel:
        print(f"{member.name} switched from {before.channel.name} to {after.channel.name}")

# -----------------------------
# Background tasks
# -----------------------------
@tasks.loop(minutes=1)
async def award_vc_xp():
    """Award XP every minute to users in tracked voice channels"""
    global active_event
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            # Only track XP in specified voice channels
            if vc.id not in VC_XP_TRACK_CHANNELS:
                continue
            
            for member in vc.members:
                # Skip bots and users with excluded roles
                if member.bot:
                    continue
                if any(int(role.id) in EXCLUDED_ROLE_SET for role in member.roles):
                    print(f"Skipped VC XP for {member.name} (has excluded role)")
                    continue
                category_id = resolve_category_id(vc)
                if category_id in NON_XP_CATEGORY_IDS or vc.id in NON_XP_CHANNEL_IDS:
                    print(f"Skipped VC XP for {member.name} (excluded VC/channel/category)")
                    continue
                
                # Check if Event 2 is active and within first 5 minutes (double XP)
                xp_to_award = VC_XP
                if active_event and active_event.get("type") == 2:
                    event_start = active_event.get("started_at")
                    if event_start:
                        elapsed = (datetime.datetime.now(datetime.UTC) - event_start).total_seconds()
                        if elapsed <= 300:  # First 5 minutes (300 seconds)
                            xp_to_award = VC_XP * 2  # Double XP (10 XP per minute)
                
                # Award XP regardless of deaf status - user only needs to be connected
                # Track 1 minute of VC time
                uid = str(member.id)
                if uid not in xp_data:
                    xp_data[uid] = {
                        "xp": 0, "level": 1, "coins": 0,
                        "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
                        "times_gambled": 0, "total_wins": 0,
                        "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
                        "equipped_collar": None, "equipped_badge": None
                    }
                if "vc_minutes" not in xp_data[uid]:
                    xp_data[uid]["vc_minutes"] = 0
                xp_data[uid]["vc_minutes"] = xp_data[uid].get("vc_minutes", 0) + 1
                
                base_mult = get_channel_multiplier(vc.id)
                await add_xp(member.id, xp_to_award, member=member, base_multiplier=base_mult)
                event_bonus = " (Event 2 double XP)" if xp_to_award > VC_XP else ""
                print(f"Awarded {xp_to_award} VC XP to {member.name} in {vc.name} (channel mult {base_mult}x){event_bonus}")

@tasks.loop(minutes=5)
async def auto_save():
    """Periodically save XP data as backup"""
    save_xp_data()
    print(f"Auto-saved XP data at {datetime.datetime.now(datetime.UTC)}")

async def send_tier3_pre_announcement(guild):
    """Send pre-announcement for Tier 3 events 5 minutes before they start."""
    channel = guild.get_channel(EVENT_CHANNEL_ID)
    if not channel:
        return
    
    embed = discord.Embed(
        description="᲼᲼\nS̵̛̳̜͕͓͎͚̹̯̟͔̃͌̉͠ȯ̵͕̣͊͛̓̅̆̊̉͌̚͘͝m̶̢̨͍̺͔͖̩̼͇̪̰̮͐͋̑̆̓͐̀ͅè̸̡̢̤̺̩̠̼̲̖̰̫̼̜̊̽͗̉̇̑ṭ̷̨̛̦̘̻̙̼̪̩̫̖̘͋́̎̄͌̓̕͝h̸̩̪͚̘̯͉̮̩̼̬͕͂̂͂̄i̷̡̨̨̫̳̟͍͎̟̯͉̳̞̩̓̄͆͛̕n̴̲͔͎̊̅̈́͂̀͒̔̈́̆͂̾͠g̸̨̢̩̳̣͔̹͇̩͚̺̳͕̣͕͋̍̈́̾̓͊̄̿̓͝ ̸͔͚̟̪̺̝̳̻͍̺̟͛̀́̀̍́̋͜͜͜͝ï̵̪̘̦̬͎̗͊̊͊̍̂̊s̷̤̰̳͇̰̥̹͖̤̼͌̃͑̾̒͗͑̓̅́͑̚̚͜ ̷̡̡̼̻̳̻̠̯̜̘͇̟̠̱̖̎́̀̔̍͂̇̄̏̈́ơ̵̧̘̮̊̽̑̆̎̿̂̍̋͑̈́͘n̶̘̞̮̺̫̭̩̜̜͎̈́̓̋̓̾͊̇̆́͂̍̐͠ ̵̱̊̂̕͠t̷̛͙̗͍̩̞̥̹͂̾͋̅̀̄̉̐͐̈́̂͘͠h̴̼͍̙̬͖̍̄̓̀e̴̢̛̅͒͊̽͐̚͝ ̴̨̛̭̱̖̜̣̝̝̓̅̓̀̈́̉̿͂̆̂͂͜͝͝ẃ̴̭̗̳̳̳͂͗̇̍̿͑a̶͚͚͕̠̳̭̘͐̍ÿ̷̛̫͕̘͍́̽̿̚͠.̶̳͍̩̇̊͜.̷̜̼̌͐̔.̶̧̨̩̳̮̟̖͈̘͕̻̣̱̎͒̀̈́͘\n\n◊ ¿°ᵛ˘ æ¢ɲæ ˘ɲ±æ≤ ┍ææ≥, \"˘æ\"¿˘, Әɲ≥",
        color=0xff000d,
    )
    embed.set_image(url="https://i.imgur.com/gvhIpAG.gif")
    
    try:
        await channel.send(embed=embed)
        print("Sent Tier 3 pre-announcement")
    except Exception as e:
        print(f"Failed to send Tier 3 pre-announcement: {e}")

@tasks.loop(minutes=1)
async def daily_check_scheduler():
    """Automatically send Daily Check messages at scheduled times."""
    global last_daily_check_times_today
    
    # Get current UK time
    uk_tz = get_timezone("Europe/London")
    if uk_tz is None:
        return  # Timezone not available
    
    if USE_PYTZ:
        now_uk = datetime.datetime.now(uk_tz)
    else:
        now_uk = datetime.datetime.now(uk_tz)
    
    today_str = now_uk.strftime("%Y-%m-%d")
    current_time = (now_uk.hour, now_uk.minute)
    
    # Clean up old entries (from previous days)
    last_daily_check_times_today = {entry for entry in last_daily_check_times_today if entry.startswith(today_str)}
    
    # Daily Check scheduled times: 19:00 (Throne), 20:00 (Slots), 22:00 (Daily command)
    daily_check_times = [
        (19, 0, "throne"),   # Throne/Coffee Check
        (20, 0, "slots"),    # Slots Check
        (22, 0, "daily"),    # Daily Check command
    ]
    
    for hour, minute, check_type in daily_check_times:
        # Check if it's time for this scheduled check (within 1 minute window)
        time_diff = abs((now_uk.hour * 60 + now_uk.minute) - (hour * 60 + minute))
        
        if time_diff <= 1:  # Within 1 minute of scheduled time
            check_key = f"{today_str}_DAILY_CHECK_{check_type}_{hour:02d}:{minute:02d}"
            
            # Check if we've already sent this check today
            if check_key in last_daily_check_times_today:
                continue  # Already sent this scheduled time today
            
            # Send the appropriate check message to all guilds
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
                    break  # Only send once per scheduled time

@tasks.loop(minutes=1)
async def event_scheduler():
    """Automatically schedule events based on UK timezone schedule"""
    global active_event, event_cooldown_until, last_event_times_today, events_enabled
    
    # Don't schedule if events are disabled
    if not events_enabled:
        return
    
    # Don't schedule if event is active or cooldown is active
    if active_event:
        return
    if event_cooldown_until and datetime.datetime.now(datetime.UTC) < event_cooldown_until:
        return
    
    # Get current UK time
    uk_tz = get_timezone("Europe/London")
    if uk_tz is None:
        print("ERROR: Timezone support not available. Cannot schedule events. Install pytz: pip install pytz")
        return
    
    if USE_PYTZ:
        # pytz requires localize() for naive datetimes
        now_uk = datetime.datetime.now(uk_tz)
    else:
        # zoneinfo works directly
        now_uk = datetime.datetime.now(uk_tz)
    today_str = now_uk.strftime("%Y-%m-%d")
    current_time = (now_uk.hour, now_uk.minute)
    
    # Clean up old entries (from previous days)
    last_event_times_today = {entry for entry in last_event_times_today if entry.startswith(today_str)}
    
    # Check for Tier 3 pre-announcement (5 minutes before 12:00 AM = midnight)
    # Pre-announcement happens at 23:55, but the event is at 00:00 (next day)
    if current_time == (23, 55):  # 11:55 PM UK time = 5 minutes before midnight
        # Use tomorrow's date for the pre-announcement key since event is at 00:00
        tomorrow = (now_uk + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        pre_announce_key = f"{tomorrow}_TIER_3_00:00_pre_announced"
        if pre_announce_key not in last_event_times_today:
            for guild in bot.guilds:
                await send_tier3_pre_announcement(guild)
            last_event_times_today.add(pre_announce_key)
            print(f"Sent Tier 3 pre-announcement at {now_uk.strftime('%H:%M:%S')} UK time (for event at 00:00)")
    
    # Check each tier's scheduled times
    for tier, scheduled_times in EVENT_SCHEDULE.items():
        for hour, minute in scheduled_times:
            # Check if it's time for this scheduled event (within 1 minute window)
            time_diff = abs((now_uk.hour * 60 + now_uk.minute) - (hour * 60 + minute))
            
            if time_diff <= 1:  # Within 1 minute of scheduled time
                event_key = f"{today_str}_TIER_{tier}_{hour:02d}:{minute:02d}"
                
                # Check if we've already triggered this event today
                if event_key in last_event_times_today:
                    continue  # Already triggered this scheduled time today
                
                # Get available events for this tier
                available_events = [et for et, t in EVENT_TIER_MAP.items() if t == tier]
                if not available_events:
                    continue
                
                # Select random event from this tier
                event_type = random.choice(available_events)
                
                # Find a guild and channel to start the event
                for guild in bot.guilds:
                    event_channel = guild.get_channel(EVENT_CHANNEL_ID)
                    if event_channel:
                        try:
                            await start_obedience_event(guild, event_type, channel=event_channel)
                            last_event_times_today.add(event_key)
                            # Clear pre-announcement flag when event starts (for Tier 3 midnight events)
                            if tier == 3 and hour == 0 and minute == 0:
                                last_event_times_today.discard(f"{today_str}_TIER_3_00:00_pre_announced")
                            print(f"Auto-started Event {event_type} (Tier {tier}) at {now_uk.strftime('%H:%M:%S')} UK time")
                            return  # Only start one event at a time
                        except Exception as e:
                            print(f"Failed to auto-start event {event_type}: {e}")
                        break

@bot.event
async def on_ready():
    global event_cooldown_until, last_event_times_today, last_throne_times_today, last_slots_times_today, last_daily_check_times_today
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    
    # Leave any guilds that aren't in the allowed list
    for guild in bot.guilds:
        if guild.id not in ALLOWED_GUILDS:
            try:
                await guild.leave()
                print(f'Left {guild.name} (ID: {guild.id}) - not in allowed guilds list')
            except Exception as e:
                print(f'Failed to leave {guild.name} (ID: {guild.id}): {e}')
    
    print(f'Bot is now in {len([g for g in bot.guilds if g.id in ALLOWED_GUILDS])} allowed guild(s)')
    print(f"Tracking XP in channels: {sorted(XP_TRACK_SET)}")
    print(f"Sending messages to channels: {sorted(ALLOWED_SEND_SET)}")
    
    if bot.intents.message_content:
        print("✅ Message Content Intent is ENABLED")
    else:
        print("❌ WARNING: Message Content Intent is DISABLED!")
    
    if bot.intents.members:
        print("✅ Members Intent is ENABLED")
    else:
        print("⚠️ Members Intent is disabled")
    
    # Initialize event scheduler with UK timezone
    uk_tz = get_timezone("Europe/London")
    if uk_tz is not None:
        if USE_PYTZ:
            now_uk = datetime.datetime.now(uk_tz)
        else:
            now_uk = datetime.datetime.now(uk_tz)
        today_str = now_uk.strftime("%Y-%m-%d")
        
        # Clear any old tracking data
        last_event_times_today.clear()
        last_daily_check_times_today.clear()
        
        # Print scheduled times for each tier
        for tier, scheduled_times in EVENT_SCHEDULE.items():
            times_str = ", ".join([f"{h:02d}:{m:02d}" for h, m in scheduled_times])
            print(f"⏱️ Tier {tier} events scheduled at: {times_str} UK time")
        
        # Print Daily Check scheduled times
        print(f"📋 Daily Check messages scheduled at: 19:00 (Throne), 20:00 (Slots), 22:00 (Daily) UK time")
        
        print(f"📅 Current UK time: {now_uk.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    else:
        print("⚠️ WARNING: Timezone support not available. Event scheduling may not work correctly.")
    
    # Set initial 30-minute cooldown to prevent events from starting immediately
    event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=1800)
    print(f"⏰ Initial event cooldown set: No events will start for 30 minutes (until {event_cooldown_until.strftime('%H:%M:%S UTC')})")
    
    # Clear event roles on startup (no events should be active)
    await clear_event_roles()
    
    award_vc_xp.start()
    auto_save.start()
    event_scheduler.start()
    daily_check_scheduler.start()
    print("Background tasks started: VC XP tracking, auto-save, event scheduler, and Daily Check scheduler")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors gracefully"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.", delete_after=5)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("Could not find that member.", delete_after=5)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Invalid argument provided.", delete_after=5)
    elif isinstance(error, commands.CommandNotFound):
        # Prefix commands have been removed - all commands are now slash commands
        pass
    else:
        print(f"Error: {error}")

@bot.event
async def on_raw_reaction_add(payload):
    await handle_event_reaction(payload)

@bot.event
async def on_guild_join(guild):
    """Automatically leave any guild that isn't in the allowed list."""
    if guild.id not in ALLOWED_GUILDS:
        try:
            await guild.leave()
            print(f'Left {guild.name} (ID: {guild.id}) - not in allowed guilds list')
        except Exception as e:
            print(f'Failed to leave {guild.name} (ID: {guild.id}): {e}')

@bot.event
async def on_member_remove(member):
    """Erase user's progress when they leave the server"""
    global xp_data
    if member.guild.id not in ALLOWED_GUILDS:
        return
    
    user_id = str(member.id)
    if user_id in xp_data:
        # Erase all progress
        del xp_data[user_id]
        save_xp_data()
        print(f"Erased progress for {member.name} (ID: {member.id}) - user left server")

# -----------------------------
# Prefix Command Versions (for user commands)
# -----------------------------

# Note: allin and slots commands are complex with subcommands, so they remain slash-only for now

# -----------------------------
# Bot login
# -----------------------------
try:
    TOKEN = os.environ['DISCORD_TOKEN']
    bot.run(TOKEN)
except KeyError:
    print("ERROR: DISCORD_TOKEN not found in environment variables!")
except Exception as e:
    print(f"ERROR: Failed to start bot: {e}")
