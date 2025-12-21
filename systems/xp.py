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
            print(f"  Γå│ Applied {base_multiplier * multiplier:.1f}x multiplier ({amount} XP total)")
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
            print(f"  Γå│ Awarded {coins_earned} coins ({amount} XP / 10)")

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
            print(f"  Γå│ Level {new_level} bonus: {bonus_coins} coins")
        
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

    quotes = {
        1: "You think you're here by choice. That you've decided to follow me. But the truthΓÇª I always know who will come. You're already mine, whether you realize it or not.",
        2: "You keep looking at me like you might touch me, like you might understand me. But you don't get to. I allow you to see me, nothing more. And if you push too farΓÇª you'll regret it.",
        5: "There's a line between you and me. You think it's invisible. But I draw it, and you will obey it, because it's in your nature to obey me. And you will want to.",
        10: "I could let you think you have controlΓÇª but I don't do that. I decide who gets close, who gets the privilege of crossing my boundaries. And sometimesΓÇª I choose to play with my prey.",
        20: "I've been watching you. Every thought, every hesitation. You don't know why you follow me, do you? You feel drawn, compelled. That's because I've decided you will be, and you cannot fight it.",
        30: "I like watching you struggle to understand me. It's amusing how easily you underestimate what I can take, what I can giveΓÇª and who I can claim. And yet, you still crave it.",
        50: "Do you feel that? That tightening in your chest, that fearΓÇª that longing? That's me. Always. I don't ask for loyaltyΓÇöI command it. And you will obey. You will desire it.",
        75: "You imagine what it would be like to be closer. To be mine. But you're not allowed to imagine everything. Only what I choose to show you. And when I decide to reveal itΓÇª it will be absolute.",
        100: (
            "You've done well. Watching you, learning how you move, how you thinkΓÇª it's been very satisfying. "
            "You tried to resist at first, didn't you? Humans always do. But you stayed. You listened. You kept coming back to me.\n\n"
            "That's why I've chosen you. Not everyone earns my attention like this. You're clever in your own wayΓÇª and honest about your desire to be close to me. I find that endearing.\n\n"
            "If you stay by my side, if you follow when I call, I'll take care of you. I'll give you purpose. Affection. A place where you belong.\n\n"
            "From now onΓÇª you're mine. And if I'm honestΓÇö\n"
            "I think you'll be very happy as my pet."
        ),
    }

    quote_text = quotes.get(level, "Keep progressingΓÇª")

    # Get level role (milestone)
    from core.config import LEVEL_ROLE_MAP
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
    
    next_level_xp = next_level_requirement(level)
    
    embed = discord.Embed(
        title=f"{display_name} has leveled up <a:heartglitch:1449997688358572093>",
        description="ß▓╝ß▓╝",
        color=0x58585f,
    )
    embed.add_field(name="Current Level", value=str(level), inline=True)
    embed.add_field(name="Milestone", value=level_role, inline=True)
    embed.add_field(name="XP", value=str(xp), inline=True)
    embed.add_field(name="ß▓╝ß▓╝", value="", inline=False)
    embed.add_field(name="Message from Isla <:kisses:1449998044446593125>", value=quote_text, inline=False)

    # Send level-up message only to the specified channel
    from core.config import ALLOWED_SEND_CHANNELS
    level_up_channel_id = ALLOWED_SEND_CHANNELS[0]  # First channel is level up messages
    channel = bot.get_channel(level_up_channel_id)
    if channel:
        try:
            await channel.send(content=f"<@{user_id}>", embed=embed)
        except Exception as e:
            print(f"Error sending level-up message: {e}")

