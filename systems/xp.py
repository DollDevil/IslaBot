"""
XP system - leveling, XP calculation, and level-up messages
"""
import discord
from core.config import MULTIPLIER_ROLE_SET, LEVEL_COIN_BONUSES
from core.data import add_coins, get_level, get_xp
from core.db import upsert_user_profile, fetchone
from core.utils import next_level_requirement, update_roles_on_level

# This will be set by main.py
bot = None

def set_bot(bot_instance):
    """Set the bot instance for this module"""
    global bot
    bot = bot_instance

def calculate_xp_multiplier(member):
    """Calculate XP multiplier based on roles"""
    multiplier = 1.0
    if isinstance(member, discord.Member):
        for role in member.roles:
            if int(role.id) in MULTIPLIER_ROLE_SET:
                multiplier += 0.2
    return multiplier

async def add_xp(user_id, amount, member=None, base_multiplier: float = 1.0, guild_id=None):
    """Add XP with optional multiplier from roles and channel"""
    # Get guild_id from member if not provided
    if guild_id is None and member:
        guild_id = member.guild.id if isinstance(member, discord.Member) else 0
    if guild_id is None:
        guild_id = 0
    
    guild_id = int(guild_id)
    user_id = int(user_id)
    
    # Get current stats
    profile = await fetchone(
        "SELECT xp, level FROM user_profile WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    
    if not profile:
        old_level = 1
        old_xp = 0
    else:
        old_level = profile["level"]
        old_xp = profile["xp"]
    
    # Apply multiplier if member object is provided
    if member:
        multiplier = calculate_xp_multiplier(member)
        amount = int(amount * base_multiplier * multiplier)
        if multiplier > 1.0 or base_multiplier != 1.0:
            print(f"  -> Applied {base_multiplier * multiplier:.1f}x multiplier ({amount} XP total)")
    else:
        amount = int(amount * base_multiplier)
    
    current_xp = old_xp + amount
    # Prevent negative XP
    if current_xp < 0:
        current_xp = 0
    
    # Calculate what level the user should be based on their XP
    calculated_level = old_level
    while True:
        next_level_xp = next_level_requirement(calculated_level + 1)
        if current_xp >= next_level_xp:
            calculated_level += 1
        else:
            break
    
    # Calculate what level they should have been based on old XP (before this addition)
    old_calculated_level = old_level
    while True:
        next_level_xp = next_level_requirement(old_calculated_level + 1)
        if old_xp >= next_level_xp:
            old_calculated_level += 1
        else:
            break
    
    # Update XP in database
    await upsert_user_profile(guild_id, user_id, xp=current_xp, level=calculated_level)
    
    # Award coins: 1 coin per 10 XP (only for positive XP gains)
    if amount > 0:
        coins_earned = amount // 10
        if coins_earned > 0:
            await add_coins(user_id, coins_earned, guild_id=guild_id)
            print(f"  -> Awarded {coins_earned} coins ({amount} XP / 10)")
    
    # Only trigger level-up notification if:
    # 1. The calculated level is higher than the old calculated level (they actually leveled up in this addition)
    if calculated_level > old_calculated_level:
        # User actually crossed a threshold in this XP addition - send notification
        new_level = calculated_level
        
        # Award level up bonus coins for all levels gained
        for level in range(old_calculated_level + 1, new_level + 1):
            if level in LEVEL_COIN_BONUSES:
                bonus_coins = LEVEL_COIN_BONUSES[level]
                await add_coins(user_id, bonus_coins, guild_id=guild_id)
                print(f"  -> Level {level} bonus: {bonus_coins} coins")
        
        if member:
            await update_roles_on_level(member, new_level)
        # Only send one notification for the final level reached
        await send_level_up_message(user_id, guild_id)

async def send_level_up_message(user_id, guild_id=None):
    """Send level-up message to the level-up channel"""
    if not bot:
        return
    
    if guild_id is None:
        guild_id = 0
    
    try:
        user = await bot.fetch_user(user_id)
    except:
        print(f"Could not fetch user {user_id}")
        return
    
    # Get member from guild to access display_name (nickname)
    member = None
    if guild_id != 0:
        guild = bot.get_guild(guild_id)
        if guild:
            member = guild.get_member(user_id)
    else:
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            if member:
                break
    
    # Fallback to user name if member not found
    display_name = member.display_name if member else user.name
    
    level = await get_level(user_id, guild_id=guild_id)
    xp = await get_xp(user_id, guild_id=guild_id)

    # Get level role (milestone)
    from core.config import LEVEL_ROLE_MAP
    level_role = "None"
    level_role_mention = "None"
    for lvl, role_id in sorted(LEVEL_ROLE_MAP.items(), reverse=True):
        if level >= lvl:
            # Try to get role from any guild the bot is in
            for guild in bot.guilds:
                role = guild.get_role(role_id)
                if role:
                    level_role = role.name
                    level_role_mention = f"<@&{role_id}>"
                    break
            if level_role != "None":
                break
    
    # Calculate next level requirements
    next_level = level + 1
    next_level_xp_required = next_level_requirement(next_level)
    xp_needed = next_level_xp_required - xp
    
    embed = discord.Embed(
        title=f"{display_name} has leveled up <a:heartglitch:1449997688358572093>",
        description="Another level already? You're doing so well—it's hard not to notice.\n\u200b",
        color=0x58585f,
    )
    embed.add_field(name="Level", value=str(level), inline=True)
    embed.add_field(name="Milestone", value=level_role_mention if level_role != "None" else "None", inline=True)
    embed.add_field(name="XP", value=str(xp), inline=True)
    embed.add_field(name="Next Level", value=f"{xp_needed}/{next_level_xp_required}", inline=False)
    embed.add_field(name="\u200b", value="Keep progressing <:kisses:1449998044446593125>", inline=False)
    embed.set_thumbnail(url="https://i.imgur.com/BJPgVbQ.png")

    # Send level-up message only to the specified channel (1450107538019192832)
    LEVEL_UP_CHANNEL_ID = 1450107538019192832
    channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)
    if channel:
        try:
            await channel.send(content=f"<@{user_id}>", embed=embed)
        except Exception as e:
            print(f"Error sending level-up message: {e}")

