"""
Utility functions for IslaBot
"""
import random
import discord

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

from core.config import (
    XP_THRESHOLDS, CHANNEL_MULTIPLIERS, LEVEL_ROLE_MAP, EXCLUDED_ROLE_SET,
    REPLY_QUOTES, LEVEL_2_ROLE_ID, BETA_BOOST_SERVANT_ROLE_IDS,
    KITTEN_ROLE_ID, PUPPY_ROLE_ID, PET_ROLE_ID, DEVOTEE_ROLE_ID
)

# Bot instance (set by main.py, but not used in this module)
bot = None

def set_bot(bot_instance):
    """Set the bot instance for this module (not currently used, but kept for consistency)"""
    global bot
    bot = bot_instance

def next_level_requirement(level: int) -> int:
    """Return XP needed to reach the given level"""
    if level - 1 < len(XP_THRESHOLDS):
        return XP_THRESHOLDS[level - 1]
    return XP_THRESHOLDS[-1] + (level - len(XP_THRESHOLDS)) * 10000

def resolve_channel_id(channel) -> int:
    """Get a consistent channel id (threads fall back to parent)"""
    channel_id = getattr(channel, "id", None)
    parent_id = getattr(getattr(channel, "parent", None), "id", None)
    return int(channel_id or parent_id or 0)

def resolve_category_id(channel) -> int:
    """Return category id for a channel/thread if available"""
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
    """Get XP multiplier for a channel"""
    return CHANNEL_MULTIPLIERS.get(int(channel_id), 1.0)

def get_reply_quote(member: discord.Member) -> str:
    """Get appropriate reply quote based on member's roles (priority order)"""
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
    """Assign level roles based on reached level; remove all other level roles (only keep highest)"""
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

