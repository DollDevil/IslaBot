"""
Gambling system for coins - V3-style with debt blocking, rank caps, and casino channel enforcement
"""
import discord
import random
import re
import datetime
import asyncio

from core.config import (
    EVENT_CHANNEL_ID, CASINO_CHANNEL_ID, DEBT_BLOCK_AT, MAX_BET_ABS, 
    GAMBLING_COOLDOWNS
)
from core.db import get_casino_channel_id, get_announcements_channel_id
from core.data import (
    increment_gambling_attempt, increment_gambling_win, add_gambling_spent,
    get_user_economy, take_bet, payout_winnings, get_coins
)

# Global state
gambling_cooldowns = {}  # {(user_id, game): last_time}
gambling_streaks = {}  # {user_id: {"streak": int, "last_activity": datetime}}
slots_free_spins = {}  # {user_id: {"count": int, "total_winnings": int}}

# ===== CASINO EMBED SYSTEM =====
# Thumbnail URLs
CASINO_THUMBNAILS = {
    "green": "https://i.imgur.com/RxOcBVn.png",      # Win
    "yellow": "https://i.imgur.com/Y3Wd7cz.png",     # Draw/Tie
    "red": "https://imgur.com/KZCfRty.png",          # Loss (user specified format)
    "blue": "https://i.imgur.com/W30kCYP.png",       # Info
    "orange": "https://imgur.com/MZqblpm.png",       # Neutral/Base (user specified format)
    "purple": "https://i.imgur.com/8yYurzA.png",     # Announcements
}

def get_streak_flair_text(streak):
    """Get streak flair text for footer. Returns empty string if no flair."""
    if streak >= 3:
        return "🔥 Hot streak"
    elif streak <= -5:
        return "🥶 Cold streak"
    return ""

def build_casino_embed(kind, outcome, title, description, fields=None, footer_text="", user_mention=None, **kwargs):
    """
    Centralized casino embed builder.
    
    Args:
        kind: "win", "loss", "draw", "info", "neutral", "announcement"
        outcome: Used to determine thumbnail (net positive/negative/zero)
        title: Embed title with icon
        description: 1-2 line description
        fields: List of dicts with name, value, inline keys
        footer_text: Footer text (cooldown/streak will be appended)
        user_mention: User mention string (for public messages)
        **kwargs: Additional embed properties
    
    Returns:
        discord.Embed
    """
    # Determine thumbnail based on outcome/kind
    if kind == "win" or (outcome is not None and outcome > 0):
        thumb = CASINO_THUMBNAILS["green"]
    elif kind == "loss" or (outcome is not None and outcome < 0):
        thumb = CASINO_THUMBNAILS["red"]
    elif kind == "draw" or (outcome is not None and outcome == 0):
        thumb = CASINO_THUMBNAILS["yellow"]
    elif kind == "info":
        thumb = CASINO_THUMBNAILS["blue"]
    elif kind == "announcement":
        thumb = CASINO_THUMBNAILS["purple"]
    else:  # neutral/base
        thumb = CASINO_THUMBNAILS["orange"]
    
    # Apply embed color rules
    if kind == "win" or (outcome is not None and outcome > 0):
        embed_color = 0x0fff2b  # WIN: green
    elif kind == "loss" or (outcome is not None and outcome < 0):
        embed_color = 0xff0f0f  # LOSS: red
    elif kind == "draw" or (outcome is not None and outcome == 0):
        embed_color = 0xffdf0f  # DRAW: yellow
    elif kind == "info":
        embed_color = 0x0fa3ff  # Blue thumbnails/info
    elif kind == "announcement":
        embed_color = 0x930fff  # Purple thumbnails/info
    elif kind == "neutral":
        embed_color = 0xff830f  # Orange thumbnails/info
    else:
        embed_color = kwargs.get("color", 0x58585f)
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=embed_color
    )
    embed.set_thumbnail(url=thumb)
    
    # Add fields
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", True)
            )
    
    # Build footer
    footer_parts = []
    if footer_text:
        footer_parts.append(footer_text)
    if "streak" in kwargs and kwargs["streak"] is not None:
        streak_flair = get_streak_flair_text(kwargs["streak"])
        if streak_flair:
            footer_parts.append(streak_flair)
    if "cooldown" in kwargs:
        footer_parts.append(f"Cooldown: {kwargs['cooldown']}s")
    
    if footer_parts:
        embed.set_footer(text=" • ".join(footer_parts))
    
    return embed

# ===== V3-STYLE VALIDATION HELPERS =====

async def enforce_casino_channel(interaction):
    """
    Enforce casino channel for gambling.
    Returns (ok, channel_name) tuple.
    If not in casino channel, respond ephemerally and return False.
    """
    if not interaction.guild:
        return True, None
    
    casino_channel_id = await get_casino_channel_id(interaction.guild.id)
    if not casino_channel_id:
        return True, None  # No restriction if not configured
    
    if interaction.channel_id != casino_channel_id:
        casino_channel = interaction.guild.get_channel(casino_channel_id)
        channel_mention = casino_channel.mention if casino_channel else f"<#{casino_channel_id}>"
        
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Casino Channel Only",
            description=f"Use casino commands in {channel_mention}.",
            fields=[
                {"name": "Blocked Here", "value": "This command is restricted to the configured casino channel.", "inline": False}
            ],
            footer_text="Ask staff if the casino channel was moved."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False, None
    
    return True, None

async def ensure_ok_to_bet(guild_id, user_id, bet, game):
    """
    V3-style bet validation.
    Returns (ok: bool, error_embed: discord.Embed or None)
    Checks: bet > 0, debt < DEBT_BLOCK_AT, bet <= min(MAX_BET_ABS, rank_cap), bet <= bal
    """
    # Get user economy
    econ = await get_user_economy(guild_id, user_id)
    bal = econ["bal"]
    debt = econ["debt"]
    rank = econ["rank"]
    rank_cap = econ["rank_cap"]
    
    # Check bet > 0
    if bet <= 0:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Invalid Bet",
            description="You must bet at least 1 coin.",
            fields=[
                {"name": "Minimum", "value": "**1** coin", "inline": True}
            ],
            footer_text="Bets must be positive integers."
        )
        return False, embed
    
    # Debt block
    if debt >= DEBT_BLOCK_AT:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Gambling Locked",
            description="Gambling is disabled while your **Debt ≥ 5000** coins.",
            fields=[
                {"name": "Current Debt", "value": f"**{debt}**", "inline": True},
                {"name": "Requirement", "value": "Debt must be **< 5000**", "inline": True}
            ],
            footer_text="Clear debt to regain casino access."
        )
        return False, embed
    
    # Rank bet cap
    effective_cap = min(MAX_BET_ABS, rank_cap)
    if bet > effective_cap:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Bet Limit Reached",
            description="Your bet exceeds your allowed maximum.",
            fields=[
                {"name": "Your Rank Cap", "value": f"**{rank_cap}**", "inline": True},
                {"name": "Absolute Max", "value": "**25000**", "inline": True},
                {"name": "Your Bet", "value": f"**{bet}**", "inline": True}
            ],
            footer_text="Caps are based on Lifetime Coins Earned (LCE)."
        )
        return False, embed
    
    # Insufficient funds
    if bet > bal:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Insufficient Funds",
            description=f"You only have **{bal}** coins.",
            fields=[
                {"name": "Required", "value": f"**{bet}**", "inline": True},
                {"name": "Available", "value": f"**{bal}**", "inline": True}
            ],
            footer_text="Earn more coins to place larger bets."
        )
        return False, embed
    
    return True, None

def check_game_cooldown(user_id, game):
    """
    Check if user is on cooldown for a specific game.
    Returns (on_cooldown, seconds_remaining).
    """
    key = (user_id, game)
    if key not in gambling_cooldowns:
        return False, 0
    
    last_time = gambling_cooldowns[key]
    cooldown_seconds = GAMBLING_COOLDOWNS.get(game, 10)
    time_since = (datetime.datetime.now(datetime.UTC) - last_time).total_seconds()
    
    if time_since >= cooldown_seconds:
        return False, 0
    
    return True, int(cooldown_seconds - time_since)

def update_game_cooldown(user_id, game):
    """Update cooldown for a specific game."""
    key = (user_id, game)
    gambling_cooldowns[key] = datetime.datetime.now(datetime.UTC)

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

def update_gambling_streak(user_id, won):
    """Update gambling streak for user. Returns streak count.
    Streaks do not reset after inactivity - they persist until broken by opposite outcome.
    """
    now = datetime.datetime.now(datetime.UTC)
    
    if user_id not in gambling_streaks:
        gambling_streaks[user_id] = {"streak": 0, "last_activity": now}
    
    streak_data = gambling_streaks[user_id]
    
    # Streaks persist - do NOT reset after inactivity
    
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

async def send_jackpot_announcement(guild, user, reels=None, bet=None, payout=None, net=None):
    """
    Send NEW Purple jackpot announcement to the announcements channel.
    Replaces old public announcement. DM messages unchanged (handled elsewhere).
    """
    channel_id = await get_announcements_channel_id(guild.id)
    event_channel = guild.get_channel(channel_id)
    if not event_channel:
        print(f"Announcements channel not found (ID: {channel_id})")
        return False
    
    # NEW Purple embed format
    if reels and bet is not None and payout is not None and net is not None:
        embed = build_casino_embed(
            kind="announcement",
            outcome=net,
            title="📣 JACKPOT HIT",
            description=f"**{user.mention}** just landed **👑 x30** on Slots.",
            fields=[
                {"name": "Spin", "value": f"{reels[0]} │ {reels[1]} │ {reels[2]}", "inline": False},
                {"name": "Bet", "value": f"**{bet}**", "inline": True},
                {"name": "Payout", "value": f"**{payout}**", "inline": True},
                {"name": "Net Gain", "value": f"**{net}**", "inline": True}
            ],
            footer_text="Casino • Slots • Big win broadcast"
        )
    else:
        # Fallback format if details not provided
        embed = build_casino_embed(
            kind="announcement",
            outcome=None,
            title="📣 JACKPOT HIT",
            description=f"**{user.mention}** just landed **👑 x30** on Slots.",
            footer_text="Casino • Slots • Big win broadcast"
        )
    
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
    """Gamble coins - 49/51 chance to double or lose (V3-compliant)."""
    from commands.user_commands import check_user_command_permissions
    
    if not await check_user_command_permissions(interaction):
        return
    
    # V3: Enforce casino channel
    ok, _ = await enforce_casino_channel(interaction)
    if not ok:
        return
    
    if not events_enabled:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Gambling Disabled",
            description="Gambling is currently disabled.",
            footer_text="Check back later."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = interaction.user.id
    guild_id = interaction.guild.id if interaction.guild else 0
    
    # V3: Check cooldown (per-game)
    on_cooldown, seconds_left = check_game_cooldown(user_id, "coinflip")
    if on_cooldown:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Cooldown Active",
            description=f"You can gamble again in {seconds_left} seconds.",
            cooldown=GAMBLING_COOLDOWNS.get("coinflip", 8)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # V3: Validate bet (debt, rank cap, balance)
    ok, error_embed = await ensure_ok_to_bet(guild_id, user_id, bet, "coinflip")
    if not ok:
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return
    
    big_bet_messages = [
        "So confident. If luck favors you, I'll have a little present ready.",
        "Big gamble. Impress me, and I won't let it go unnoticed.",
        "That's a lot for someone like you. Win, and maybe I'll be generous.",
        "Such confidence… or desperation. Either way, win and I'll give you something.",
    ]
    
    is_big_bet = bet > 10000
    if is_big_bet:
        # Big bet pre-message (neutral/orange)
        embed = build_casino_embed(
            kind="neutral",
            outcome=None,
            title="🪙 Coinflip",
            description=f"*{random.choice(big_bet_messages)}*"
        )
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(1)
    else:
        await interaction.response.defer()
    
    # V3: Subtract bet immediately
    await take_bet(guild_id, user_id, bet)
    await increment_gambling_attempt(user_id, guild_id=guild_id)
    await add_gambling_spent(user_id, bet, guild_id=guild_id)
    
    # V3: Determine outcome (49/51 house edge)
    won = random.random() < 0.49
    update_game_cooldown(user_id, "coinflip")
    streak = update_gambling_streak(user_id, won)
    
    # Get new balance for display
    econ = await get_user_economy(guild_id, user_id)
    new_balance = econ["bal"]
    
    if won:
        await increment_gambling_win(user_id, guild_id=guild_id)
        # V3: Payout adds to balance AND lifetime earned
        payout = bet * 2
        await payout_winnings(guild_id, user_id, payout)
        net_gain = payout - bet
        
        embed = build_casino_embed(
            kind="win",
            outcome=net_gain,
            title="🪙 Coinflip — WIN",
            description=f"**{interaction.user.display_name}** wins **{net_gain}** coins.",
            fields=[
                {"name": "Bet", "value": f"**{bet}**", "inline": True},
                {"name": "Multiplier", "value": "`x2`", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            streak=streak,
            cooldown=GAMBLING_COOLDOWNS.get("coinflip", 8)
        )
        # V3: Public output in casino with ping
        await interaction.followup.send(content=f"<@{user_id}>", embed=embed)
        
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
        # V3: Loss already handled by take_bet at start
        embed = build_casino_embed(
            kind="loss",
            outcome=-bet,
            title="🪙 Coinflip — LOSS",
            description=f"**{interaction.user.display_name}** loses **{bet}** coins.",
            fields=[
                {"name": "Bet", "value": f"**{bet}**", "inline": True},
                {"name": "Result", "value": "`Lose`", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            streak=streak,
            cooldown=GAMBLING_COOLDOWNS.get("coinflip", 8)
        )
        # V3: Public output in casino with ping
        await interaction.followup.send(content=f"<@{user_id}>", embed=embed)

async def dice(interaction: discord.Interaction, bet: int):
    """Roll dice - win if your roll > dealer roll (V3-compliant)."""
    from commands.user_commands import check_user_command_permissions
    
    if not await check_user_command_permissions(interaction):
        return
    
    # V3: Enforce casino channel
    ok, _ = await enforce_casino_channel(interaction)
    if not ok:
        return
    
    if not events_enabled:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Gambling Disabled",
            description="Gambling is currently disabled.",
            footer_text="Check back later."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = interaction.user.id
    guild_id = interaction.guild.id if interaction.guild else 0
    
    # V3: Check cooldown
    on_cooldown, seconds_left = check_game_cooldown(user_id, "dice")
    if on_cooldown:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Cooldown Active",
            description=f"You can roll the dice again in {seconds_left} seconds.",
            cooldown=GAMBLING_COOLDOWNS.get("dice", 10)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # V3: Validate bet
    ok, error_embed = await ensure_ok_to_bet(guild_id, user_id, bet, "dice")
    if not ok:
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    
    # V3: Take bet immediately
    await take_bet(guild_id, user_id, bet)
    await increment_gambling_attempt(user_id, guild_id=guild_id)
    await add_gambling_spent(user_id, bet, guild_id=guild_id)
    
    user_roll = random.randint(1, 6)
    dealer_roll = random.randint(1, 6)
    
    update_game_cooldown(user_id, "dice")
    
    # Get new balance for display
    econ = await get_user_economy(guild_id, user_id)
    new_balance = econ["bal"]
    
    if user_roll > dealer_roll:
        await increment_gambling_win(user_id, guild_id=guild_id)
        # V3: Payout
        payout = bet * 2
        await payout_winnings(guild_id, user_id, payout)
        streak = update_gambling_streak(user_id, True)
        net_gain = payout - bet
        
        embed = build_casino_embed(
            kind="win",
            outcome=net_gain,
            title="🎲 Dice — WIN",
            description=f"**{interaction.user.display_name}** wins.",
            fields=[
                {"name": "Rolls", "value": f"`You: {user_roll}` • `Dealer: {dealer_roll}`", "inline": False},
                {"name": "Bet", "value": f"**{bet}**", "inline": True},
                {"name": "Net", "value": f"**+{net_gain}**", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            streak=streak,
            cooldown=GAMBLING_COOLDOWNS.get("dice", 10)
        )
        await interaction.followup.send(content=f"<@{user_id}>", embed=embed)
    elif user_roll < dealer_roll:
        # V3: Loss already handled by take_bet
        streak = update_gambling_streak(user_id, False)
        
        embed = build_casino_embed(
            kind="loss",
            outcome=-bet,
            title="🎲 Dice — LOSS",
            description=f"**{interaction.user.display_name}** loses.",
            fields=[
                {"name": "Rolls", "value": f"`You: {user_roll}` • `Dealer: {dealer_roll}`", "inline": False},
                {"name": "Bet", "value": f"**{bet}**", "inline": True},
                {"name": "Net", "value": f"**-{bet}**", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            streak=streak,
            cooldown=GAMBLING_COOLDOWNS.get("dice", 10)
        )
        await interaction.followup.send(content=f"<@{user_id}>", embed=embed)
    else:
        # V3: Tie - refund bet
        await payout_winnings(guild_id, user_id, bet)
        streak = update_gambling_streak(user_id, False)  # Tie doesn't count as win for streak
        
        embed = build_casino_embed(
            kind="draw",
            outcome=0,
            title="🎲 Dice — DRAW",
            description=f"**{interaction.user.display_name}** ties.",
            fields=[
                {"name": "Rolls", "value": f"`You: {user_roll}` • `Dealer: {dealer_roll}`", "inline": False},
                {"name": "Bet", "value": f"**{bet}**", "inline": True},
                {"name": "Net", "value": "**0** (refunded)", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            streak=streak,
            cooldown=GAMBLING_COOLDOWNS.get("dice", 10)
        )
        await interaction.followup.send(content=f"<@{user_id}>", embed=embed)

async def slots_bet(interaction: discord.Interaction, bet: int):
    """Play slots with a bet (V3-compliant)."""
    from commands.user_commands import check_user_command_permissions
    
    if not await check_user_command_permissions(interaction):
        return
    
    # V3: Enforce casino channel
    ok, _ = await enforce_casino_channel(interaction)
    if not ok:
        return
    
    if not events_enabled:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Gambling Disabled",
            description="Gambling is currently disabled.",
            footer_text="Check back later."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = interaction.user.id
    guild_id = interaction.guild.id if interaction.guild else 0
    
    # V3: Check cooldown
    on_cooldown, seconds_left = check_game_cooldown(user_id, "slots")
    if on_cooldown:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Cooldown Active",
            description=f"You can spin again in {seconds_left} seconds.",
            cooldown=GAMBLING_COOLDOWNS.get("slots", 15)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # V3: Validate bet
    ok, error_embed = await ensure_ok_to_bet(guild_id, user_id, bet, "slots")
    if not ok:
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    
    # V3: Take bet immediately
    await take_bet(guild_id, user_id, bet)
    await increment_gambling_attempt(user_id, guild_id=guild_id)
    await add_gambling_spent(user_id, bet, guild_id=guild_id)
    
    reels = spin_slots_reels()
    payout, win_type, message = calculate_slots_payout(reels, bet)
    
    update_game_cooldown(user_id, "slots")
    
    # Get new balance for display
    econ = await get_user_economy(guild_id, user_id)
    new_balance = econ["bal"]
    
    # V3: Handle payouts
    if win_type in ["win", "bonus_win"]:
        await increment_gambling_win(user_id, guild_id=guild_id)
        await payout_winnings(guild_id, user_id, payout)
        streak = update_gambling_streak(user_id, True)
    elif win_type == "loss":
        # V3: Loss already handled by take_bet
        streak = update_gambling_streak(user_id, False)
    elif payout > 0:
        # Bonus payouts
        await payout_winnings(guild_id, user_id, payout)
        streak = 0
    else:
        streak = 0
    
    if win_type == "loss":
        if message and "Lost" in message:
            loss_match = re.search(r"Lost (\d+) coins", message)
            if loss_match:
                loss_amount = int(loss_match.group(1))
                net_loss = -loss_amount
            else:
                net_loss = -bet
        else:
            net_loss = -bet
        
        embed = build_casino_embed(
            kind="loss",
            outcome=net_loss,
            title="🎰 Slots",
            description=f"**{interaction.user.display_name}** spins for **{bet}** coins.",
            fields=[
                {"name": "Reels", "value": f"{reels[0]} │ {reels[1]} │ {reels[2]}", "inline": False},
                {"name": "Outcome", "value": "Loss", "inline": True},
                {"name": "Net", "value": f"**{net_loss}**", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            streak=streak,
            cooldown=GAMBLING_COOLDOWNS.get("slots", 15)
        )
    elif win_type == "win":
        multiplier = payout // bet if bet > 0 else 0
        net_gain = payout - bet
        
        if multiplier == 30:
            # JACKPOT - use new embed format
            embed = build_casino_embed(
                kind="win",
                outcome=net_gain,
                title="🎰 Slots",
                description=f"**{interaction.user.display_name}** spins for **{bet}** coins.",
                fields=[
                    {"name": "Reels", "value": f"{reels[0]} │ {reels[1]} │ {reels[2]}", "inline": False},
                    {"name": "Outcome", "value": f"Win x{multiplier} 👑", "inline": True},
                    {"name": "Net", "value": f"**+{net_gain}**", "inline": True},
                    {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
                ],
                streak=streak,
                cooldown=GAMBLING_COOLDOWNS.get("slots", 15)
            )
            # Send NEW public jackpot announcement
            if interaction.guild:
                try:
                    await send_jackpot_announcement(interaction.guild, interaction.user, reels, bet, payout, net_gain)
                except Exception as e:
                    print(f"Failed to send jackpot announcement: {e}")
        else:
            # Regular win (all multipliers use same format)
            embed = build_casino_embed(
                kind="win",
                outcome=net_gain,
                title="🎰 Slots",
                description=f"**{interaction.user.display_name}** spins for **{bet}** coins.",
                fields=[
                    {"name": "Reels", "value": f"{reels[0]} │ {reels[1]} │ {reels[2]}", "inline": False},
                    {"name": "Outcome", "value": f"Win x{multiplier}", "inline": True},
                    {"name": "Net", "value": f"**+{net_gain}**", "inline": True},
                    {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
                ],
                streak=streak,
                cooldown=GAMBLING_COOLDOWNS.get("slots", 15)
            )
    elif win_type == "bonus_win":
        net_gain = payout - bet
        embed = build_casino_embed(
            kind="win",
            outcome=net_gain,
            title="🎰 Slots",
            description=f"**{interaction.user.display_name}** spins for **{bet}** coins.",
            fields=[
                {"name": "Reels", "value": f"{reels[0]} │ {reels[1]} │ {reels[2]}", "inline": False},
                {"name": "Outcome", "value": message, "inline": True},
                {"name": "Net", "value": f"**+{net_gain}**", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            streak=streak,
            cooldown=GAMBLING_COOLDOWNS.get("slots", 15)
        )
    elif win_type == "mini_bonus":
        # Net is 0 (bonus payout but no win)
        embed = build_casino_embed(
            kind="neutral",
            outcome=0,
            title="🎰 Slots",
            description=f"**{interaction.user.display_name}** spins for **{bet}** coins.",
            fields=[
                {"name": "Reels", "value": f"{reels[0]} │ {reels[1]} │ {reels[2]}", "inline": False},
                {"name": "Outcome", "value": f"🎁 Bonus: {payout} coins", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            cooldown=GAMBLING_COOLDOWNS.get("slots", 15)
        )
    elif win_type == "big_bonus":
        free_spin_data = slots_free_spins.get(user_id, {"count": 0, "total_winnings": 0})
        free_spin_data["count"] = free_spin_data.get("count", 0) + 2
        slots_free_spins[user_id] = free_spin_data
        net_gain = payout - bet
        embed = build_casino_embed(
            kind="win",
            outcome=net_gain,
            title="🎰 Slots",
            description=f"**{interaction.user.display_name}** spins for **{bet}** coins.",
            fields=[
                {"name": "Reels", "value": f"{reels[0]} │ {reels[1]} │ {reels[2]}", "inline": False},
                {"name": "Outcome", "value": message, "inline": False},
                {"name": "Net", "value": f"**+{net_gain}**", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            footer_text="Use /slots free",
            cooldown=GAMBLING_COOLDOWNS.get("slots", 15)
        )
    elif win_type == "mega_bonus":
        free_spin_data = slots_free_spins.get(user_id, {"count": 0, "total_winnings": 0})
        free_spin_data["count"] = free_spin_data.get("count", 0) + 5
        slots_free_spins[user_id] = free_spin_data
        net_loss = -bet  # Lost bet, got free spins
        embed = build_casino_embed(
            kind="neutral",
            outcome=net_loss,
            title="🎰 Slots",
            description=f"**{interaction.user.display_name}** spins for **{bet}** coins.",
            fields=[
                {"name": "Reels", "value": f"{reels[0]} │ {reels[1]} │ {reels[2]}", "inline": False},
                {"name": "Outcome", "value": "🎁 +5 Free Spins", "inline": False},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            footer_text="Use /slots free",
            cooldown=GAMBLING_COOLDOWNS.get("slots", 15)
        )
    
    # V3: Public output in casino with ping
    await interaction.followup.send(content=f"<@{user_id}>", embed=embed)

async def slots_free(interaction: discord.Interaction):
    """Use a free spin (V3-compliant)."""
    from commands.user_commands import check_user_command_permissions
    
    if not await check_user_command_permissions(interaction):
        return
    
    # V3: Enforce casino channel
    ok, _ = await enforce_casino_channel(interaction)
    if not ok:
        return
    
    if not events_enabled:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Gambling Disabled",
            description="Gambling is currently disabled.",
            footer_text="Check back later."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = interaction.user.id
    
    free_spin_data = slots_free_spins.get(user_id, {"count": 0, "total_winnings": 0})
    free_spins = free_spin_data.get("count", 0)
    if free_spins <= 0:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ No Free Spins",
            description="You don't have any free spins right now.",
            footer_text="Earn free spins from slots bonuses."
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
    
    guild_id = interaction.guild.id if interaction.guild else 0
    # V3: Payout for free spins also adds to LCE
    if payout > 0:
        await payout_winnings(guild_id, user_id, payout)
    
    # Get new balance for display
    econ = await get_user_economy(guild_id, user_id)
    new_balance = econ["bal"]
    
    if remaining == 0:
        total_winnings = free_spin_data.get("total_winnings", 0)
        embed = build_casino_embed(
            kind="win" if total_winnings > 0 else "neutral",
            outcome=total_winnings,
            title="🎰 Slots",
            description=f"**{interaction.user.display_name}** completes free spins.",
            fields=[
                {"name": "Total Winnings", "value": f"**{total_winnings:,}** coins", "inline": False},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            cooldown=GAMBLING_COOLDOWNS.get("slots", 15)
        )
        slots_free_spins.pop(user_id, None)
    else:
        if bonus_count > 0:
            bonus_messages = {
                1: "+1 Free Spin",
                2: "+2 Free Spins",
                3: "+3 Free Spins",
            }
            embed = build_casino_embed(
                kind="neutral",
                outcome=0,
                title="🎰 Slots",
                description=f"**{interaction.user.display_name}** uses a free spin.",
                fields=[
                    {"name": "Reels", "value": f"{reels[0]} │ {reels[1]} │ {reels[2]}", "inline": False},
                    {"name": "Bonus", "value": f"🎁 {bonus_messages[bonus_count]}", "inline": False},
                    {"name": "Remaining", "value": f"**{remaining}** free spins", "inline": True}
                ],
                footer_text=f"Free Spins Remaining: {remaining}",
                cooldown=GAMBLING_COOLDOWNS.get("slots", 15)
            )
        else:
            outcome_kind = "win" if payout > 0 else "neutral"
            embed = build_casino_embed(
                kind=outcome_kind,
                outcome=payout,
                title="🎰 Slots",
                description=f"**{interaction.user.display_name}** uses a free spin.",
                fields=[
                    {"name": "Reels", "value": f"{reels[0]} │ {reels[1]} │ {reels[2]}", "inline": False},
                    {"name": "Outcome", "value": f"Win +{payout} coins" if payout > 0 else "No win", "inline": True},
                    {"name": "Remaining", "value": f"**{remaining}** free spins", "inline": True}
                ],
                footer_text=f"Free Spins Remaining: {remaining}",
                cooldown=GAMBLING_COOLDOWNS.get("slots", 15)
            )
            
            if reels[0] == reels[1] == reels[2] == "👑":
                # Jackpot on free spin - need bet=0, payout is the jackpot amount
                if interaction.guild:
                    try:
                        await send_jackpot_announcement(interaction.guild, interaction.user, reels, 0, payout, payout)
                    except Exception as e:
                        print(f"Failed to send jackpot announcement from free spin: {e}")
    
    # V3: Public output in casino with ping
    await interaction.followup.send(content=f"<@{user_id}>", embed=embed)

async def roulette(interaction: discord.Interaction, bet: int, choice: str):
    """Roulette - bet on red/black/green/number (V3-compliant)."""
    from commands.user_commands import check_user_command_permissions
    
    if not await check_user_command_permissions(interaction):
        return
    
    # V3: Enforce casino channel
    ok, _ = await enforce_casino_channel(interaction)
    if not ok:
        return
    
    if not events_enabled:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Gambling Disabled",
            description="Gambling is currently disabled.",
            footer_text="Check back later."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = interaction.user.id
    guild_id = interaction.guild.id if interaction.guild else 0
    
    # V3: Check cooldown
    on_cooldown, seconds_left = check_game_cooldown(user_id, "roulette")
    if on_cooldown:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Cooldown Active",
            description=f"You can play roulette again in {seconds_left} seconds.",
            cooldown=GAMBLING_COOLDOWNS.get("roulette", 20)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # V3: Validate bet
    ok, error_embed = await ensure_ok_to_bet(guild_id, user_id, bet, "roulette")
    if not ok:
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return
    
    # Validate choice
    choice_lower = choice.lower()
    valid_choices = ["red", "black", "green", "0"]
    valid_numbers = [str(i) for i in range(37)]
    
    if choice_lower not in valid_choices and choice not in valid_numbers:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Invalid Choice",
            description="Choose: red, black, green, or a number (0-36).",
            footer_text="Red/Black: x2 • Green: x14 • Number: x36"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    
    # V3: Take bet immediately
    await take_bet(guild_id, user_id, bet)
    await increment_gambling_attempt(user_id, guild_id=guild_id)
    await add_gambling_spent(user_id, bet, guild_id=guild_id)
    
    # Spin roulette
    outcome_num = random.randint(0, 36)
    
    # Determine color
    if outcome_num == 0:
        outcome_color = "green"
        outcome_display = "🟢 0"
    else:
        # European roulette: reds are 1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36
        reds = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        if outcome_num in reds:
            outcome_color = "red"
            outcome_display = f"🔴 {outcome_num}"
        else:
            outcome_color = "black"
            outcome_display = f"⚫ {outcome_num}"
    
    update_game_cooldown(user_id, "roulette")
    
    # Get new balance for display
    econ = await get_user_economy(guild_id, user_id)
    new_balance = econ["bal"]
    
    won = False
    payout = 0
    
    # Check win conditions
    if choice_lower == outcome_color:
        # Color match
        won = True
        if outcome_color == "green":
            payout = bet * 14  # Green pays 14x
        else:
            payout = bet * 2  # Red/Black pays 2x
    elif choice == str(outcome_num):
        # Number match
        won = True
        payout = bet * 36
    
    if won:
        await increment_gambling_win(user_id, guild_id=guild_id)
        await payout_winnings(guild_id, user_id, payout)
        streak = update_gambling_streak(user_id, True)
        net_gain = payout - bet
        multiplier = payout // bet if bet > 0 else 0
        
        embed = build_casino_embed(
            kind="win",
            outcome=net_gain,
            title="🎡 Roulette",
            description=f"**{interaction.user.display_name}** bets **{bet}** coins.",
            fields=[
                {"name": "Bet Type", "value": f"`{choice}`", "inline": True},
                {"name": "Spin", "value": f"`{outcome_display}`", "inline": True},
                {"name": "Payout", "value": f"x{multiplier}", "inline": True},
                {"name": "Net", "value": f"**+{net_gain}**", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            streak=streak,
            cooldown=GAMBLING_COOLDOWNS.get("roulette", 20)
        )
    else:
        # V3: Loss already handled by take_bet
        streak = update_gambling_streak(user_id, False)
        
        embed = build_casino_embed(
            kind="loss",
            outcome=-bet,
            title="🎡 Roulette",
            description=f"**{interaction.user.display_name}** bets **{bet}** coins.",
            fields=[
                {"name": "Bet Type", "value": f"`{choice}`", "inline": True},
                {"name": "Spin", "value": f"`{outcome_display}`", "inline": True},
                {"name": "Net", "value": f"**-{bet}**", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            streak=streak,
            cooldown=GAMBLING_COOLDOWNS.get("roulette", 20)
        )
    
    await interaction.followup.send(content=f"<@{user_id}>", embed=embed)

async def coinflip(interaction: discord.Interaction, bet: int):
    """Coin flip - same as gamble (49/51 chance, V3-compliant)."""
    await gamble(interaction, bet)

async def allin(interaction: discord.Interaction, game: str):
    """Go all-in on a game (bet all coins)."""
    from commands.user_commands import check_user_command_permissions
    
    if not await check_user_command_permissions(interaction):
        return
    
    user_id = interaction.user.id
    guild_id = interaction.guild.id if interaction.guild else 0
    all_coins = await get_coins(user_id, guild_id=guild_id)
    
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
    elif game_lower in ["blackjack", "bj"]:
        await blackjack(interaction, all_coins)
    elif game_lower == "roulette":
        await interaction.response.send_message("Roulette requires a choice. Use: /roulette <bet> <red/black/green/number>", ephemeral=True, delete_after=5)
    else:
        await interaction.response.send_message("Invalid game. Use: gamble, dice, slots, blackjack, or roulette", ephemeral=True, delete_after=5)

# ===== BLACKJACK =====

class BlackjackView(discord.ui.View):
    """Interactive blackjack view with Hit/Stand/Double buttons"""
    
    def __init__(self, user_id, guild_id, bet, dealer_hand, player_hand):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.guild_id = guild_id
        self.bet = bet
        self.dealer_hand = dealer_hand
        self.player_hand = player_hand
        self.settled = False
    
    def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only the invoking user can interact"""
        return interaction.user.id == self.user_id
    
    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary, emoji="🎯")
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.settled:
            await interaction.response.defer()
            return
        
        # Draw card
        self.player_hand.append(draw_card())
        player_value = calculate_hand_value(self.player_hand)
        
        if player_value > 21:
            # Bust - loss already handled by take_bet
            self.settled = True
            await increment_gambling_attempt(self.user_id, guild_id=self.guild_id)
            
            # Get balance for display
            econ = await get_user_economy(self.guild_id, self.user_id)
            new_balance = econ["bal"]
            
            embed = build_casino_embed(
                kind="loss",
                outcome=-self.bet,
                title="🃏 Blackjack — LOSS",
                description=f"**{interaction.user.display_name}** loses.",
                fields=[
                    {"name": "Your Hand", "value": f"{format_hand(self.player_hand)}  (**{player_value}**)", "inline": False},
                    {"name": "Dealer Hand", "value": f"{format_hand(self.dealer_hand)}", "inline": False},
                    {"name": "Net", "value": f"**-{self.bet}**", "inline": True},
                    {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
                ],
                cooldown=GAMBLING_COOLDOWNS.get("blackjack", 30)
            )
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            embed = build_casino_embed(
                kind="neutral",
                outcome=None,
                title="🃏 Blackjack",
                description=f"**{interaction.user.display_name}** plays **{self.bet}** coins. Choose an action below.",
                fields=[
                    {"name": "Your Hand", "value": f"{format_hand(self.player_hand)}  (**{player_value}**)", "inline": False},
                    {"name": "Dealer", "value": f"{format_hand([self.dealer_hand[0]])}  (`?`)", "inline": False}
                ],
                footer_text="Timeout: 60s (auto-stand)",
                cooldown=GAMBLING_COOLDOWNS.get("blackjack", 30)
            )
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Stand", style=discord.ButtonStyle.success, emoji="✋")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.settled:
            await interaction.response.defer()
            return
        
        self.settled = True
        await settle_blackjack(interaction, self.guild_id, self.user_id, self.bet, self.dealer_hand, self.player_hand)
    
    @discord.ui.button(label="Double", style=discord.ButtonStyle.secondary, emoji="💰")
    async def double_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.settled:
            await interaction.response.defer()
            return
        
        # Check if can double (need enough balance)
        bal = (await get_user_economy(self.guild_id, self.user_id))["bal"]
        if bal < self.bet:
            embed = build_casino_embed(
                kind="info",
                outcome=None,
                title="ℹ️ Insufficient Funds",
                description=f"Not enough coins to double. You need **{self.bet}** more coins.",
                footer_text="Double requires matching your original bet."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Take additional bet
        await take_bet(self.guild_id, self.user_id, self.bet)
        self.bet *= 2
        
        # Draw one card and auto-stand
        self.player_hand.append(draw_card())
        self.settled = True
        
        await settle_blackjack(interaction, self.guild_id, self.user_id, self.bet, self.dealer_hand, self.player_hand)
    
    async def on_timeout(self):
        """Auto-stand on timeout"""
        if not self.settled:
            self.settled = True

def draw_card():
    """Draw a random card (1-11)"""
    return random.choice([2,3,4,5,6,7,8,9,10,10,10,10,11])

def calculate_hand_value(hand):
    """Calculate hand value with ace handling"""
    value = sum(hand)
    aces = hand.count(11)
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    return value

def format_hand(hand):
    """Format hand for display"""
    return " + ".join(str(c) for c in hand)

async def settle_blackjack(interaction, guild_id, user_id, bet, dealer_hand, player_hand):
    """Settle blackjack game"""
    # Dealer draws
    while calculate_hand_value(dealer_hand) < 17:
        dealer_hand.append(draw_card())
    
    player_value = calculate_hand_value(player_hand)
    dealer_value = calculate_hand_value(dealer_hand)
    
    await increment_gambling_attempt(user_id, guild_id=guild_id)
    
    # Get balance for display
    econ = await get_user_economy(guild_id, user_id)
    new_balance = econ["bal"]
    
    if dealer_value > 21:
        # Dealer bust - player wins
        await increment_gambling_win(user_id, guild_id=guild_id)
        payout = bet * 2
        await payout_winnings(guild_id, user_id, payout)
        net_gain = payout - bet
        econ = await get_user_economy(guild_id, user_id)
        new_balance = econ["bal"]
        
        embed = build_casino_embed(
            kind="win",
            outcome=net_gain,
            title="🃏 Blackjack — WIN",
            description=f"**{interaction.user.display_name}** wins.",
            fields=[
                {"name": "Your Hand", "value": f"{format_hand(player_hand)}  (**{player_value}**)", "inline": False},
                {"name": "Dealer Hand", "value": f"{format_hand(dealer_hand)}  (**{dealer_value}** - Bust)", "inline": False},
                {"name": "Net", "value": f"**+{net_gain}**", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            cooldown=GAMBLING_COOLDOWNS.get("blackjack", 30)
        )
    elif player_value > dealer_value:
        # Player wins
        await increment_gambling_win(user_id, guild_id=guild_id)
        payout = bet * 2
        await payout_winnings(guild_id, user_id, payout)
        net_gain = payout - bet
        econ = await get_user_economy(guild_id, user_id)
        new_balance = econ["bal"]
        
        embed = build_casino_embed(
            kind="win",
            outcome=net_gain,
            title="🃏 Blackjack — WIN",
            description=f"**{interaction.user.display_name}** wins.",
            fields=[
                {"name": "Your Hand", "value": f"{format_hand(player_hand)}  (**{player_value}**)", "inline": False},
                {"name": "Dealer Hand", "value": f"{format_hand(dealer_hand)}  (**{dealer_value}**)", "inline": False},
                {"name": "Net", "value": f"**+{net_gain}**", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            cooldown=GAMBLING_COOLDOWNS.get("blackjack", 30)
        )
    elif player_value < dealer_value:
        # Dealer wins - loss already handled
        embed = build_casino_embed(
            kind="loss",
            outcome=-bet,
            title="🃏 Blackjack — LOSS",
            description=f"**{interaction.user.display_name}** loses.",
            fields=[
                {"name": "Your Hand", "value": f"{format_hand(player_hand)}  (**{player_value}**)", "inline": False},
                {"name": "Dealer Hand", "value": f"{format_hand(dealer_hand)}  (**{dealer_value}**)", "inline": False},
                {"name": "Net", "value": f"**-{bet}**", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            cooldown=GAMBLING_COOLDOWNS.get("blackjack", 30)
        )
    else:
        # Push - refund bet
        await payout_winnings(guild_id, user_id, bet)
        econ = await get_user_economy(guild_id, user_id)
        new_balance = econ["bal"]
        
        embed = build_casino_embed(
            kind="draw",
            outcome=0,
            title="🃏 Blackjack — DRAW",
            description=f"**{interaction.user.display_name}** pushes.",
            fields=[
                {"name": "Your Hand", "value": f"{format_hand(player_hand)}  (**{player_value}**)", "inline": False},
                {"name": "Dealer Hand", "value": f"{format_hand(dealer_hand)}  (**{dealer_value}**)", "inline": False},
                {"name": "Net", "value": "**0** (bet returned)", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            cooldown=GAMBLING_COOLDOWNS.get("blackjack", 30)
        )
    
    await interaction.response.edit_message(embed=embed, view=None)

async def blackjack(interaction: discord.Interaction, bet: int):
    """Play blackjack (V3-compliant)."""
    from commands.user_commands import check_user_command_permissions
    
    if not await check_user_command_permissions(interaction):
        return
    
    # V3: Enforce casino channel
    ok, _ = await enforce_casino_channel(interaction)
    if not ok:
        return
    
    if not events_enabled:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Gambling Disabled",
            description="Gambling is currently disabled.",
            footer_text="Check back later."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    user_id = interaction.user.id
    guild_id = interaction.guild.id if interaction.guild else 0
    
    # V3: Check cooldown
    on_cooldown, seconds_left = check_game_cooldown(user_id, "blackjack")
    if on_cooldown:
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Cooldown Active",
            description=f"You can play blackjack again in {seconds_left} seconds.",
            cooldown=GAMBLING_COOLDOWNS.get("blackjack", 30)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # V3: Validate bet
    ok, error_embed = await ensure_ok_to_bet(guild_id, user_id, bet, "blackjack")
    if not ok:
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        return
    
    # V3: Take bet immediately
    await take_bet(guild_id, user_id, bet)
    await add_gambling_spent(user_id, bet, guild_id=guild_id)
    
    # Deal initial hands
    dealer_hand = [draw_card(), draw_card()]
    player_hand = [draw_card(), draw_card()]
    
    player_value = calculate_hand_value(player_hand)
    
    update_game_cooldown(user_id, "blackjack")
    
    # Get balance for display
    econ = await get_user_economy(guild_id, user_id)
    new_balance = econ["bal"]
    
    # Check for instant blackjack
    if player_value == 21:
        await increment_gambling_win(user_id, guild_id=guild_id)
        payout = int(bet * 2.5)  # Blackjack pays 3:2
        await payout_winnings(guild_id, user_id, payout)
        net_gain = payout - bet
        econ = await get_user_economy(guild_id, user_id)
        new_balance = econ["bal"]
        
        embed = build_casino_embed(
            kind="win",
            outcome=net_gain,
            title="🃏 Blackjack — WIN",
            description=f"**{interaction.user.display_name}** wins.",
            fields=[
                {"name": "Your Hand", "value": f"{format_hand(player_hand)}  (**21**)", "inline": False},
                {"name": "Dealer Hand", "value": f"{format_hand(dealer_hand)}", "inline": False},
                {"name": "Net", "value": f"**+{net_gain}** (3:2 payout)", "inline": True},
                {"name": "New Balance", "value": f"**{new_balance}**", "inline": True}
            ],
            cooldown=GAMBLING_COOLDOWNS.get("blackjack", 30)
        )
        await interaction.response.send_message(content=f"<@{user_id}>", embed=embed)
        return
    
    # Show initial state with buttons (Orange/neutral)
    embed = build_casino_embed(
        kind="neutral",
        outcome=None,
        title="🃏 Blackjack",
        description=f"**{interaction.user.display_name}** plays **{bet}** coins. Choose an action below.",
        fields=[
            {"name": "Your Hand", "value": f"{format_hand(player_hand)}  (**{player_value}**)", "inline": False},
            {"name": "Dealer", "value": f"{format_hand([dealer_hand[0]])}  (`?`)", "inline": False}
        ],
        footer_text="Timeout: 60s (auto-stand)",
        cooldown=GAMBLING_COOLDOWNS.get("blackjack", 30)
    )
    
    view = BlackjackView(user_id, guild_id, bet, dealer_hand, player_hand)
    await interaction.response.send_message(content=f"<@{user_id}>", embed=embed, view=view)

