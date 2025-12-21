"""
XP system - leveling, XP calculation, and level-up messages
"""
import discord
from core.config import MULTIPLIER_ROLE_SET, LEVEL_COIN_BONUSES
from core.data import xp_data, add_coins, save_xp_data, get_level, get_xp
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
            print(f"  -> Applied {base_multiplier * multiplier:.1f}x multiplier ({amount} XP total)")
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
            print(f"  -> Awarded {coins_earned} coins ({amount} XP / 10)")

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
            print(f"  -> Level {new_level} bonus: {bonus_coins} coins")
        
        if member:
            await update_roles_on_level(member, new_level)
        save_xp_data()
        await send_level_up_message(user_id)
    else:
        save_xp_data()

async def send_level_up_message(user_id):
    """Send level-up message to the level-up channel"""
    if not bot:
        return
        
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

