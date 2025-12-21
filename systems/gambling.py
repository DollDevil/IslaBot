"""
Gambling system for coins - gamble, dice, slots, coinflip, allin
"""
import discord
from discord import app_commands
import random
import secrets
import re
import datetime
import asyncio

from core.config import EVENT_CHANNEL_ID
from core.data import (
    get_coins, add_coins, has_coins, save_xp_data,
    increment_gambling_attempt, increment_gambling_win, add_gambling_spent
)

# Global state
gambling_cooldowns = {}
gambling_streaks = {}  # {user_id: {"streak": int, "last_activity": datetime}}
slots_free_spins = {}  # {user_id: {"count": int, "total_winnings": int}}

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

# Bot instance and events_enabled flag (set by main.py)
bot = None
events_enabled = True

def set_bot(bot_instance):
    """Set the bot instance for this module"""
    global bot
    bot = bot_instance

def set_events_enabled(enabled: bool):
    """Set events_enabled flag (used as gambling enabled flag)"""
    global events_enabled
    events_enabled = enabled

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

def spin_slots_reels():
    """Spin the slots reels and return [symbol1, symbol2, symbol3]."""
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
            return (0, "mega_bonus", "🎁 You gained 5 Free Spins")
        
        multiplier = SLOTS_SYMBOLS[symbol]["multiplier"]
        payout = int(bet * multiplier)
        return (payout, "win", f"Win x{multiplier}")
    
    # Check for 2-of-a-kind (small win)
    if reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
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
        return (250, "big_bonus", "🎁 You gained 2 Free Spins\n\nBonus payout: +250 chips")
    elif bonus_count == 1:
        other_symbols = [s for s in reels if s != "🎁"]
        if len(set(other_symbols)) == 1:
            symbol = other_symbols[0]
            if symbol in SLOTS_SYMBOLS and SLOTS_SYMBOLS[symbol]["multiplier"] > 0:
                multiplier = 0.8
                payout = int(bet * multiplier)
                return (payout, "bonus_win", f"Win x{multiplier}")
        else:
            return (0, "mini_bonus", "🎁 Bonus payout: +0 coins")
    
    # No win
    return (0, "loss", None)

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

# Note: Commands will be registered in commands/user_commands.py
# These are the command functions that will be imported there

async def gamble(interaction: discord.Interaction, bet: int):
    """Gamble coins - 49/51 chance to double or lose."""
    from commands.user_commands import check_user_command_permissions
    
    if not await check_user_command_permissions(interaction):
        return
    
    if not events_enabled:
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
        await asyncio.sleep(1)
    else:
        await interaction.response.defer()
    
    increment_gambling_attempt(user_id)
    add_gambling_spent(user_id, bet)
    won = random.random() < 0.49
    update_gambling_cooldown(user_id)
    streak = update_gambling_streak(user_id, won)
    
    if won:
        increment_gambling_win(user_id)
        winnings = bet * 2
        add_coins(user_id, bet)
        save_xp_data()
        
        win_messages = [
            "Huh… look at that.\nLuck actually noticed you this time.",
            "Interesting.\nYou pulled that off better than I expected.",
            "Well well…\nEven you can surprise me sometimes.",
            "Looks like luck leaned your way.\nJust this once.",
            "Cute.\nYou look proud — don't worry, I'll allow it.",
            "That worked out for you.\nI wonder if you can do it again.",
            "A win.\nNot bad… I might even be impressed.",
            "Looks like the game was kind to you.\nYou should thank me for that.",
        ]
        
        embed = discord.Embed(
            title="🎉 You Won",
            description=random.choice(win_messages),
            color=0x4ec200,
        )
        embed.set_thumbnail(url="https://i.imgur.com/VdlEKfp.png")
        embed.set_footer(text=f"+{bet} coins")
        await interaction.followup.send(embed=embed)
        
        # Big bet bonus: send DM with image
        if is_big_bet:
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
        add_coins(user_id, -bet)
        save_xp_data()
        
        loss_messages = [
            "You really thought luck was on your side this time?\nThat was cute.",
            "It's alright—loss looks good on you too.\nKeeps you humble.",
            "You took a chance for me—and failed.\nI won't say I'm surprised.",
            "Luck didn't land this time.\nMaybe the next round treats you better.",
            "Not a win this time.\nYou can always try again when you're ready.",
            "No win this round.\nThe game's still waiting for you though.",
            "No payout this time.\nYou'll get it eventually—if you keep playing.",
            "Didn't hit.\nBut I like that you tried.",
        ]
        
        embed = discord.Embed(
            title="💔 Lost Gamble",
            description=random.choice(loss_messages),
            color=0xa80000,
        )
        embed.set_thumbnail(url="https://i.imgur.com/EuS7WME.png")
        embed.set_footer(text=f"-{bet} coins")
        await interaction.followup.send(embed=embed)

async def dice(interaction: discord.Interaction, bet: int):
    """Roll dice - win if your roll > dealer roll."""
    from commands.user_commands import check_user_command_permissions
    
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
    
    increment_gambling_attempt(user_id)
    add_gambling_spent(user_id, bet)
    user_roll = random.randint(1, 6)
    dealer_roll = random.randint(1, 6)
    
    update_gambling_cooldown(user_id)
    
    if user_roll > dealer_roll:
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
        embed = discord.Embed(
            title="It's a Tie! 🎲",
            description=f"Both rolled {user_roll}.\n\nYour bet has been returned.",
            color=0xffae00,
        )
        await interaction.followup.send(embed=embed)

async def slots_bet(interaction: discord.Interaction, bet: int):
    """Play slots with a bet."""
    from commands.user_commands import check_user_command_permissions
    
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
    
    increment_gambling_attempt(user_id)
    add_coins(user_id, -bet)
    add_gambling_spent(user_id, bet)
    save_xp_data()
    
    reels = spin_slots_reels()
    payout, win_type, message = calculate_slots_payout(reels, bet)
    
    if win_type == "loss" and message and "Lost" in message:
        loss_match = re.search(r"Lost (\d+) coins", message)
        if loss_match:
            loss_amount = int(loss_match.group(1))
            refund = bet - loss_amount
            if refund > 0:
                add_coins(user_id, refund)
            save_xp_data()
    
    if win_type in ["win", "bonus_win"]:
        increment_gambling_win(user_id)
        streak = update_gambling_streak(user_id, True)
    elif win_type == "loss":
        streak = update_gambling_streak(user_id, False)
    else:
        streak = 0
    
    if payout > 0:
        add_coins(user_id, payout)
        save_xp_data()
    
    if win_type == "loss":
        if message and "Lost" in message:
            loss_match = re.search(r"Lost (\d+) coins", message)
            if loss_match:
                loss_amount = int(loss_match.group(1))
                embed = discord.Embed(
                    title="🎰 Lucky Loss",
                    description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n\n❌ You lost {loss_amount} coins.",
                    color=0xaf0808,
                )
            else:
                embed = discord.Embed(
                    title="🎰 Loss",
                    description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n\n❌ You lost {bet} coins.",
                    color=0xaf0808,
                )
        else:
            embed = discord.Embed(
                title="🎰 Loss",
                description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n\n❌ You lost {bet} coins.",
                color=0xaf0808,
            )
    elif win_type == "win":
        multiplier = payout // bet if bet > 0 else 0
        if multiplier == 8:
            embed = discord.Embed(
                title="🎰 Nice Hit!",
                description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n\n✅ Win x{multiplier}  💵 {payout} coins received.",
                color=0x1bbe19,
            )
        elif multiplier == 15:
            embed = discord.Embed(
                title="🎰 BIG WIN!",
                description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n\n✅ Win x{multiplier}  💰 {payout} coins received.",
                color=0x1bbe19,
            )
        elif multiplier == 30:
            embed = discord.Embed(
                title="🎰 JACKPOT! 🎉",
                description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n\n✅ Win x{multiplier}  👑 {payout} coins received.\n\n*Oh? A jackpot. Good doggy—remember how rare this is.*",
                color=0x1bbe19,
            )
            embed.set_image(url="https://i.imgur.com/ZQOOc9n.png")
            
            if interaction.guild:
                try:
                    await send_jackpot_announcement(interaction.guild, interaction.user)
                except Exception as e:
                    print(f"Failed to send jackpot announcement: {e}")
        else:
            embed = discord.Embed(
                title="🎰 Lucky Spin",
                description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n\n✅ {message}  🪙 {payout} coins received.",
                color=0x1bbe19,
            )
        streak_flair = get_streak_flair(streak)
        if streak_flair:
            embed.set_footer(text=streak_flair)
    elif win_type == "bonus_win":
        embed = discord.Embed(
            title="🎰 BONUS ACTIVATED!",
            description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n\n✅ {message}  🪙 {payout} coins received.",
            color=0x1bbe19,
        )
    elif win_type == "mini_bonus":
        embed = discord.Embed(
            title="🎰 Mini Bonus!",
            description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n\n🎁 Bonus payout: {payout} coins.",
            color=0x1bbe19,
        )
    elif win_type == "big_bonus":
        free_spin_data = slots_free_spins.get(user_id, {"count": 0, "total_winnings": 0})
        free_spin_data["count"] = free_spin_data.get("count", 0) + 2
        slots_free_spins[user_id] = free_spin_data
        embed = discord.Embed(
            title="🎰 BIG BONUS!",
            description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n\n{message}",
            color=0x1bbe19,
        )
        embed.set_footer(text="Use /slots free")
    elif win_type == "mega_bonus":
        free_spin_data = slots_free_spins.get(user_id, {"count": 0, "total_winnings": 0})
        free_spin_data["count"] = free_spin_data.get("count", 0) + 5
        slots_free_spins[user_id] = free_spin_data
        embed = discord.Embed(
            title="🎰 MEGA BONUS ACTIVATED!",
            description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n\n🎁 You gained 5 Free Spins",
            color=0x1bbe19,
        )
        embed.set_footer(text="Use /slots free")
    
    await interaction.followup.send(embed=embed)

async def slots_free(interaction: discord.Interaction):
    """Use a free spin."""
    from commands.user_commands import check_user_command_permissions
    
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
    
    free_spin_data["count"] = free_spins - 1
    remaining = free_spin_data["count"]
    
    reels = spin_slots_reels()
    payout, win_type, message = calculate_slots_payout(reels, 0)
    
    if payout > 0:
        free_spin_data["total_winnings"] = free_spin_data.get("total_winnings", 0) + payout
    
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
    
    slots_free_spins[user_id] = free_spin_data
    
    if payout > 0:
        add_coins(user_id, payout)
        save_xp_data()
    
    if remaining == 0:
        total_winnings = free_spin_data.get("total_winnings", 0)
        embed = discord.Embed(
            title="🎰 BONUS COMPLETE",
            description=f"Total Bonus Winnings: {total_winnings:,} coins.",
            color=0x1bbe19 if total_winnings > 0 else 0xffae00,
        )
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
                description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n\n🎁 {bonus_messages[bonus_count]}",
                color=0x1bbe19,
            )
            embed.set_footer(text=f"Free Spins Remaining: {remaining}")
        else:
            embed = discord.Embed(
                title="🎰 FREE SPIN",
                description=f"\n[{reels[0]}] [{reels[1]}] [{reels[2]}]\n",
                color=0x1bbe19 if payout > 0 else 0xffae00,
            )
            if payout > 0:
                embed.description += f"\n\n✅ Win +{payout} coins"
            embed.set_footer(text=f"Free Spins Remaining: {remaining}")
            
            if reels[0] == reels[1] == reels[2] == "👑":
                if interaction.guild:
                    try:
                        await send_jackpot_announcement(interaction.guild, interaction.user)
                    except Exception as e:
                        print(f"Failed to send jackpot announcement from free spin: {e}")
    
    await interaction.followup.send(embed=embed)

async def coinflip(interaction: discord.Interaction, bet: int):
    """Coin flip - same as gamble (49/51 chance)."""
    await gamble(interaction, bet)

async def allin(interaction: discord.Interaction, game: str):
    """Go all-in on a game (bet all coins)."""
    from commands.user_commands import check_user_command_permissions
    
    if not await check_user_command_permissions(interaction):
        return
    
    user_id = interaction.user.id
    all_coins = get_coins(user_id)
    
    if all_coins < 10:
        await interaction.response.send_message("You need at least 10 coins to gamble.", ephemeral=True, delete_after=5)
        return
    
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

