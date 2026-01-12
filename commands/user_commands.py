"""
User commands for the bot - balance, daily, give, gambling, etc.
"""
import discord
from discord import app_commands
import datetime

from core.config import (
    USER_COMMAND_CHANNEL_ID, ALLOWED_SEND_SET,
    EVENT_CHANNEL_ID
)
from core.data import (
    get_coins, add_coins, has_coins,
    get_activity_quote
)
from core.utils import get_timezone, USE_PYTZ
# Leaderboard imports removed - /leaderboard and /leaderboards commands deleted
from systems.gambling import (
    gamble, dice, slots_bet, slots_free, coinflip, allin, roulette, blackjack,
    build_casino_embed
)
from core.data import check_daily_cooldown, update_daily_cooldown, check_give_cooldown, update_give_cooldown

# Bot instance (set by main.py)
bot = None

def set_bot(bot_instance):
    """Set the bot instance for this module"""
    global bot
    bot = bot_instance

async def check_user_command_permissions(interaction_or_ctx) -> bool:
    """Check if user command can be used. Works with both Interaction and Context."""
    if isinstance(interaction_or_ctx, discord.Interaction):
        channel_id = interaction_or_ctx.channel.id
        user = interaction_or_ctx.user
        guild_id = interaction_or_ctx.guild.id if interaction_or_ctx.guild else 0
        is_interaction = True
    else:
        channel_id = interaction_or_ctx.channel.id
        user = interaction_or_ctx.author
        guild_id = interaction_or_ctx.guild.id if interaction_or_ctx.guild else 0
        is_interaction = False
    
    # Use configured usercommands channels (C1: allow multiple channels)
    from core.db import get_usercommands_channel_ids
    allowed_channels = await get_usercommands_channel_ids(guild_id)
    
    if channel_id not in allowed_channels:
        channels_mention = " ".join(f"<#{cid}>" for cid in allowed_channels)
        if is_interaction:
            await interaction_or_ctx.response.send_message(f"This command can only be used in: {channels_mention}", ephemeral=True, delete_after=5)
        else:
            await interaction_or_ctx.send(f"This command can only be used in: {channels_mention}", delete_after=5)
        return False
    
    if not isinstance(user, discord.Member):
        if is_interaction:
            await interaction_or_ctx.response.send_message("This command can only be used in a server.", ephemeral=True)
        else:
            await interaction_or_ctx.send("This command can only be used in a server.", delete_after=5)
        return False
    
    # Block Bad Pup users from using commands
    from systems.onboarding import has_bad_pup_role
    if has_bad_pup_role(user):
        if is_interaction:
            await interaction_or_ctx.response.send_message("You cannot use commands while you have the Bad Pup role. Type the required submission text to redeem yourself.", ephemeral=True, delete_after=10)
        else:
            await interaction_or_ctx.send("You cannot use commands while you have the Bad Pup role. Type the required submission text to redeem yourself.", delete_after=10)
        return False
    
    return True

# Legacy Level/XP system removed - V3 progression only

def register_commands(bot_instance):
    """Register all user commands with the bot"""
    global bot
    bot = bot_instance
    
    # /equip command deleted per D5
    # Old /leaderboards and /leaderboard commands deleted per D4
    
    # /info command deleted per D5
    
    @bot.tree.command(name="balance", description="Show your coin balance")
    async def balance(interaction: discord.Interaction):
        """Show user's coin balance."""
        if not await check_user_command_permissions(interaction):
            return
        
        user_id = interaction.user.id
        user = interaction.user
        guild_id = interaction.guild.id if interaction.guild else 0
        coins = await get_coins(user_id, guild_id=guild_id)
        
        # Get user's display name (nickname if available, otherwise username)
        display_name = user.display_name if hasattr(user, 'display_name') else user.name
        
        # Check if daily has been claimed
        on_cooldown, reset_timestamp = check_daily_cooldown(user_id)
        daily_status = "✅ Claimed" if on_cooldown else "❌ Not Claimed"
        
        embed = discord.Embed(
            title=f"{display_name}'s Total Balance",
            description=f"{coins} coins.\n\u200b",
            color=0xff9d14,
        )
        embed.add_field(name="Daily Coins", value=daily_status, inline=True)
        embed.set_thumbnail(url="https://i.imgur.com/yYBNX08.png")
        embed.set_footer(text="Use /daily to claim free coins. Use /profile to view full stats.")
        
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="daily", description="Claim your daily coins")
    async def daily(interaction: discord.Interaction):
        """Claim daily coins - always responds within 3s (D3)."""
        # Always respond immediately
        await interaction.response.defer()
        
        if not await check_user_command_permissions(interaction):
            return
        
        # Record command event
        if interaction.guild:
            guild_id = interaction.guild.id
            user_id = interaction.user.id
            channel_id = interaction.channel.id
            from core.db import record_command_event, bump_command
            await record_command_event(guild_id, user_id, "daily", channel_id)
            await bump_command(guild_id, user_id)
        
        user_id = interaction.user.id
        on_cooldown, reset_timestamp = check_daily_cooldown(user_id)
        
        if on_cooldown:
            embed = discord.Embed(
                title="Daily 🎁",
                description="You've already claimed your daily reward today.",
                color=0xff000d,
            )
            embed.set_footer(text="Resets at 6:00 PM GMT")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        guild_id = interaction.guild.id if interaction.guild else 0
        
        # Base amount is always 100 coins
        base_daily = 100
        
        # Check for weekend bonus
        uk_tz = get_timezone("Europe/London")
        if uk_tz:
            if USE_PYTZ:
                now_uk = datetime.datetime.now(uk_tz)
            else:
                now_uk = datetime.datetime.now(uk_tz)
            weekday = now_uk.weekday()
            if weekday >= 4:  # Friday (4), Saturday (5), Sunday (6)
                weekend_bonus = True
            else:
                weekend_bonus = False
        else:
            weekend_bonus = False
        
        # Calculate total daily amount
        daily_amount = base_daily
        if weekend_bonus:
            daily_amount += 25
        
        await add_coins(user_id, daily_amount, guild_id=guild_id)
        update_daily_cooldown(user_id)
        
        # Format weekend bonus field
        weekend_bonus_text = "✅ +25 coins" if weekend_bonus else "❌ Not Active"
        
        embed = discord.Embed(
            title="Daily Coins",
            description=f"Claimed {daily_amount} coins!\n\u200b",
            color=0xff9d14,
        )
        embed.add_field(name="Weekend Bonus", value=weekend_bonus_text, inline=True)
        embed.set_thumbnail(url="https://i.imgur.com/ZKq5nZ2.png")
        embed.set_footer(text="Resets daily at 6:00 PM GMT")
        
        await interaction.followup.send(embed=embed)
    
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
        
        guild_id = interaction.guild.id if interaction.guild else 0
        if not await has_coins(user_id, amount, guild_id=guild_id):
            await interaction.response.send_message("You don't have enough coins.", ephemeral=True, delete_after=5)
            return
        
        guild_id = interaction.guild.id if interaction.guild else 0
        await add_coins(user_id, -amount, guild_id=guild_id)
        await add_coins(member.id, amount, guild_id=guild_id)
        update_give_cooldown(user_id)
        # Data now stored in DB - no need to save JSON
        
        embed = discord.Embed(
            title="Gift 🎁",
            description=f"Gave **{amount}** coins to {member.mention}",
            color=0xff000d,
        )
        embed.set_footer(text="Gifts reset daily at 6:00 PM GMT")
        await interaction.response.send_message(content=member.mention, embed=embed)
    
    # Gambling commands - import from gambling module
    # /gamble command removed per A1
    
    @bot.tree.command(name="dice", description="Roll dice - win if your roll > dealer roll")
    @app_commands.describe(bet="The amount of coins to bet (minimum 50)")
    async def dice_command(interaction: discord.Interaction, bet: int):
        await dice(interaction, bet)
    
    @bot.tree.command(name="diceinfo", description="Show dice command info")
    async def diceinfo(interaction: discord.Interaction):
        """Show dice command info."""
        if not await check_user_command_permissions(interaction):
            return
        
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Dice Info",
            description="Roll 1–6 vs dealer. Higher roll wins.",
            fields=[
                {"name": "Min Bet", "value": "**50** coins", "inline": True},
                {"name": "Payout", "value": "**x2**", "inline": True},
                {"name": "Ties", "value": "Bet returned", "inline": True},
                {"name": "Cooldown", "value": "**10s**", "inline": True}
            ],
            footer_text="Use /dice <bet>"
        )
        await interaction.response.send_message(embed=embed)
    
    # Slots command group
    slots_group = app_commands.Group(name="slots", description="Play slots games")
    
    @slots_group.command(name="bet", description="Bet on slots")
    @app_commands.describe(bet="The amount of coins to bet (minimum 10)")
    async def slots_bet_command(interaction: discord.Interaction, bet: int):
        await slots_bet(interaction, bet)
    
    @slots_group.command(name="free", description="Use a free spin")
    async def slots_free_command(interaction: discord.Interaction):
        await slots_free(interaction)
    
    bot.tree.add_command(slots_group)
    
    @bot.tree.command(name="slotspaytable", description="Show slots paytable")
    async def slotspaytable(interaction: discord.Interaction):
        """Show slots paytable."""
        if not await check_user_command_permissions(interaction):
            return
        
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Slots Paytable",
            description="3-of-a-kind multipliers (weighted reels).",
            fields=[
                {"name": "Multipliers", "value": "🥝 x1.5 • 🍇 x2 • 🍋 x3 • 🍑 x5 • 🍉 x8 • 🍒 x15 • 👑 x30 (JACKPOT)", "inline": False},
                {"name": "Bonus 🎁", "value": "3x 🎁 → +5 free spins\n2x 🎁 → +2 free spins +250 coins\n🎁 + pair → x0.8 multiplier", "inline": False},
                {"name": "Safety Nets", "value": "2-of-a-kind → -50% loss\nFree spins: `/slots free`", "inline": False}
            ],
            footer_text="Cooldown: 15s • Min bet: 10"
        )
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="slotsinfo", description="Show slots info")
    async def slotsinfo(interaction: discord.Interaction):
        """Show slots info."""
        if not await check_user_command_permissions(interaction):
            return
        
        embed = build_casino_embed(
            kind="info",
            outcome=None,
            title="ℹ️ Slots Info",
            description="3 reel weighted symbols. Match 3-of-a-kind to win.",
            fields=[
                {"name": "Min Bet", "value": "**10** coins", "inline": True},
                {"name": "Cooldown", "value": "**15s**", "inline": True},
                {"name": "Free Spins", "value": "Use `/slots free`", "inline": True},
                {"name": "Streaks", "value": "🔥 Hot: 3+ wins • 🥶 Cold: 5+ losses", "inline": False}
            ],
            footer_text="See /slotspaytable for multipliers"
        )
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="casino", description="Show casino information")
    async def casino(interaction: discord.Interaction):
        """Show casino information."""
        if not await check_user_command_permissions(interaction):
            return
        
        user_id = interaction.user.id
        
        embed = discord.Embed(
            title="<a:A_shuffle:1451743595681026125> Isla's Casino",
            description="Welcome to my casino — where luck comes to play <:kisses:1449998044446593125>",
            colour=0x0fa3ff
        )
        embed.add_field(name="Games",
                        value="`/coinflip`\n`/dice`\n`/slots`\n`/roulette`\n`/blackjack`",
                        inline=True)
        embed.add_field(name="Cooldowns",
                        value="Coinflip 8s\nDice 10s\nSlots 15s\nRoulette 20s\nBlackjack 30s",
                        inline=True)
        embed.add_field(name="Streaks",
                        value="🔥 3+ wins\n🥶 5+ losses",
                        inline=True)
        embed.set_thumbnail(url="https://i.imgur.com/W30kCYP.png")
        embed.set_footer(text="Have fun losing~")
        
        content = f"<@{user_id}>"
        await interaction.response.send_message(content=content, embed=embed)
    
    @bot.tree.command(name="casinoinfo", description="Show detailed information about a specific game")
    async def casinoinfo(interaction: discord.Interaction):
        """Show casino game info - uses Select Menu."""
        if not await check_user_command_permissions(interaction):
            return
        
        # Create Select Menu view
        class CasinoInfoSelectView(discord.ui.View):
            def __init__(self, user_id):
                super().__init__(timeout=300)
                self.user_id = user_id
            
            @discord.ui.select(
                placeholder="Select a game to view info...",
                options=[
                    discord.SelectOption(label="Coinflip", value="coinflip", description="49/51 chance to double or lose"),
                    discord.SelectOption(label="Dice", value="dice", description="Roll 1–6 vs dealer. Higher roll wins."),
                    discord.SelectOption(label="Slots", value="slots", description="3 reel weighted symbols. Match 3-of-a-kind to win."),
                    discord.SelectOption(label="Roulette", value="roulette", description="Bet on red/black/green or a number"),
                    discord.SelectOption(label="Blackjack", value="blackjack", description="Get closer to 21 than the dealer"),
                ]
            )
            async def select_callback(self, select_interaction: discord.Interaction, select: discord.ui.Select):
                if select_interaction.user.id != self.user_id:
                    await select_interaction.response.send_message("This is not your menu.", ephemeral=True)
                    return
                
                game = select.values[0]
                await self.send_game_info(select_interaction, game)
            
            async def send_game_info(self, interaction: discord.Interaction, game: str):
                user_id = interaction.user.id
                content = f"<@{user_id}>"
                
                if game == "coinflip":
                    embed = discord.Embed(
                        title="ℹ️ Coinflip Info",
                        description="49/51 chance to double or lose.",
                        colour=0x0fa3ff
                    )
                    embed.add_field(name="Min Bet", value="**10** coins", inline=True)
                    embed.add_field(name="Payout", value="**x2**", inline=True)
                    embed.add_field(name="Cooldown", value="**8s**", inline=True)
                    embed.set_thumbnail(url="https://i.imgur.com/W30kCYP.png")
                    embed.set_footer(text="Use /coinflip <bet>")
                
                elif game == "dice":
                    embed = discord.Embed(
                        title="ℹ️ Dice Info",
                        description="Roll 1–6 vs dealer. Higher roll wins.",
                        colour=0x0fa3ff
                    )
                    embed.add_field(name="Min Bet", value="**50** coins", inline=True)
                    embed.add_field(name="Payout", value="**x2**", inline=True)
                    embed.add_field(name="Ties", value="Bet returned", inline=True)
                    embed.add_field(name="Cooldown", value="**10s**", inline=True)
                    embed.set_thumbnail(url="https://i.imgur.com/W30kCYP.png")
                    embed.set_footer(text="Use /dice <bet>")
                
                elif game == "slots":
                    embed = discord.Embed(
                        title="<a:A_shuffle:1451743595681026125> Isla's Casino",
                        description="Not all wins are equal. Some are worth waiting for.",
                        colour=0x0fa3ff
                    )
                    embed.add_field(name="Multipliers",
                                    value="🥝 x1.5\n🍇 x2\n🍋 x3\n🍑 x5\n🍉 x8\n🍒 x15\n👑 x30 **JACKPOT**",
                                    inline=True)
                    embed.add_field(name="Bonus",
                                    value="3x 🎁 +5 free spins\n2x 🎁 +2 free spins",
                                    inline=True)
                    embed.add_field(name="Extra",
                                    value="Cooldown: 15s\nMinimum bet: 10\nBonus: `/slots free`",
                                    inline=True)
                    embed.add_field(name="Safety Nets",
                                    value="2-of-a-kind -50% loss",
                                    inline=False)
                    embed.set_thumbnail(url="https://i.imgur.com/W30kCYP.png")
                    embed.set_footer(text="Good luck… and good losses~")
                
                elif game == "roulette":
                    embed = discord.Embed(
                        title="ℹ️ Roulette Info",
                        description="Bet on red/black/green or a number (0-36).",
                        colour=0x0fa3ff
                    )
                    embed.add_field(name="Bet Types", value="Red/Black: x2\nGreen: x14\nNumber: x36", inline=True)
                    embed.add_field(name="Cooldown", value="**20s**", inline=True)
                    embed.set_thumbnail(url="https://i.imgur.com/W30kCYP.png")
                    embed.set_footer(text="Use /roulette <bet> <choice>")
                
                elif game == "blackjack":
                    embed = discord.Embed(
                        title="ℹ️ Blackjack Info",
                        description="Get closer to 21 than the dealer without going over.",
                        colour=0x0fa3ff
                    )
                    embed.add_field(name="Actions", value="Hit, Stand, Double", inline=True)
                    embed.add_field(name="Payout", value="Blackjack: 3:2\nWin: x2\nTie: Refund", inline=True)
                    embed.add_field(name="Cooldown", value="**30s**", inline=True)
                    embed.set_thumbnail(url="https://i.imgur.com/W30kCYP.png")
                    embed.set_footer(text="Use /blackjack <bet>")
                
                await interaction.response.send_message(content=content, embed=embed)
        
        # Send public message with mention (A3: casinoinfo must be public)
        user_id = interaction.user.id
        content = f"<@{user_id}>"
        view = CasinoInfoSelectView(user_id)
        await interaction.response.send_message(content=content + "\nSelect a game to view information:", view=view)
    
    @bot.tree.command(name="coinflip", description="Coin flip - same as gamble (49/51 chance)")
    @app_commands.describe(bet="The amount of coins to bet (minimum 10)")
    async def coinflip_command(interaction: discord.Interaction, bet: int):
        await coinflip(interaction, bet)
    
    @bot.tree.command(name="coinflipinfo", description="Show coinflip info")
    async def coinflipinfo(interaction: discord.Interaction):
        """Show coinflip info."""
        if not await check_user_command_permissions(interaction):
            return
        
        user_id = interaction.user.id
        content = f"<@{user_id}>"
        
        embed = discord.Embed(
            title="ℹ️ Coinflip Info",
            description="49/51 chance to double or lose.",
            colour=0x0fa3ff
        )
        embed.add_field(name="Min Bet", value="**10** coins", inline=True)
        embed.add_field(name="Payout", value="**x2**", inline=True)
        embed.add_field(name="Cooldown", value="**8s**", inline=True)
        embed.set_thumbnail(url="https://i.imgur.com/W30kCYP.png")
        embed.set_footer(text="Use /coinflip <bet>")
        
        await interaction.response.send_message(content=content, embed=embed)
    
    @bot.tree.command(name="allin", description="Go all-in on a game (bet all coins)")
    @app_commands.describe(game="The game to play (coinflip, dice, slots, blackjack, or roulette)")
    async def allin_command(interaction: discord.Interaction, game: str):
        # Update game name from gamble to coinflip
        if game.lower() in ["gamble", "bet", "cf"]:
            game = "coinflip"
        await allin(interaction, game)
    
    @bot.tree.command(name="roulette", description="Play roulette - bet on red/black/green or a number")
    @app_commands.describe(
        bet="The amount of coins to bet",
        choice="Your choice: red, black, green, or a number (0-36)"
    )
    async def roulette_command(interaction: discord.Interaction, bet: int, choice: str):
        await roulette(interaction, bet, choice)
    
    @bot.tree.command(name="blackjack", description="Play blackjack - get closer to 21 than the dealer")
    @app_commands.describe(bet="The amount of coins to bet")
    async def blackjack_command(interaction: discord.Interaction, bet: int):
        await blackjack(interaction, bet)
    
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
    
    @bot.tree.command(name="rules", description="Show server rules")
    async def rules(interaction: discord.Interaction):
        """Show server rules"""
        if not await check_user_command_permissions(interaction):
            return
        
        from systems.onboarding import send_onboarding_rules
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        await send_onboarding_rules(interaction, member, is_reply=False)
    
    # Profile helpers
    def make_progress_bar(pct: int, segments: int = 12) -> str:
        """Create a progress bar using ▰ and ▱"""
        filled = int((pct / 100) * segments)
        filled = max(0, min(segments, filled))  # Clamp between 0 and segments
        return "▰" * filled + "▱" * (segments - filled)
    
    def format_vc_time(minutes: int) -> str:
        """Format voice chat minutes as 'Xh Ym' or 'Ym'"""
        hours = minutes // 60
        mins = minutes % 60
        if hours > 0:
            return f"{hours}h {mins}m"
        return f"{mins}m"
    
    def select_rank_quote(stats: dict) -> str:
        """Select rank advancement quote based on sentiment and stability"""
        # Rank advancement quotes based on sentiment and stability
        RANK_QUOTES = {
            ("positive", "stable"): "In Isla's favor. Keep this pace and advance.",
            ("positive", "neutral"): "In Isla's favor. Progress holds, but it isn't accelerating.",
            ("positive", "unstable"): "In Isla's favor. You are progressing, but not evenly.",
            ("neutral", "stable"): "In Isla's review. Your rank remains steady.",
            ("neutral", "neutral"): "In Isla's review. No significant change detected.",
            ("neutral", "unstable"): "In Isla's review. Minor fluctuations observed.",
            ("negative", "unstable"): "In Isla's disapproval. Instability detected.",
            ("negative", "neutral"): "In Isla's disapproval. Rank stability is failing.",
            ("negative", "stable"): "In Isla's disapproval. This rank is at risk.",
        }
        
        readiness_pct = stats.get("readiness_pct", 50)
        blocker_text = stats.get("blocker_text", "")
        blocker_locked = "🚧" in blocker_text
        
        # Check if at risk (holding_status == at_risk)
        holding_status = stats.get("holding_status", None)
        if holding_status == "at_risk":
            return RANK_QUOTES[("negative", "stable")]
        
        # Determine sentiment: positive if >= 60, neutral if 30-59, negative if < 30
        if readiness_pct >= 60:
            sentiment = "positive"
        elif readiness_pct >= 30:
            sentiment = "neutral"
        else:
            sentiment = "negative"
        
        # Determine stability: stable if failing_gates_count == 0, unstable if >= 2, else neutral
        failing_gates_count = stats.get("failing_gates_count", 0)
        if failing_gates_count == 0:
            stability = "stable"
        elif failing_gates_count >= 2:
            stability = "unstable"
        else:
            stability = "neutral"
        
        key = (sentiment, stability)
        return RANK_QUOTES.get(key, RANK_QUOTES[("neutral", "neutral")])
    
    # Profile embed builder
    def build_profile_embed(member: discord.Member, stats: dict) -> discord.Embed:
        """Build the main profile embed"""
        quote = select_rank_quote(stats)
        
        embed = discord.Embed(
            description=quote,
            color=0x58585f
        )
        
        embed.set_author(
            name=f"{member.display_name}'s Profile",
            icon_url=member.display_avatar.url
        )
        
        # Rank field
        progress_bar = make_progress_bar(stats.get("readiness_pct", 0))
        rank_value = f"🐾 {stats.get('rank', 'Stray')}\n⭐ {progress_bar} {stats.get('readiness_pct', 0)}%\n{stats.get('blocker_text', '🔓 Ready')}"
        embed.add_field(name="Rank", value=rank_value, inline=True)
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Wallet field
        wallet_value = f"🪙 {stats.get('coins', 0)} Coins\n💰 {stats.get('lifetime', 0)} Lifetime\n💸 {stats.get('tax', 0)} Tax\n💳 {stats.get('debt', 0)} Debt"
        embed.add_field(name="Wallet", value=wallet_value, inline=False)
        
        # Obedience field
        obedience_pct = stats.get("obedience_pct", 0)
        obedience_streak = stats.get("obedience_streak", 0)
        obedience_value = f"🧠 {obedience_pct}%\n🔥 {obedience_streak}d streak"
        embed.add_field(name="Obedience", value=obedience_value, inline=False)
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Orders (three inline fields)
        embed.add_field(name="Orders Done", value=f"🟢 {stats.get('orders_done', 0)}", inline=True)
        embed.add_field(name="Orders Late", value=f"🟡 {stats.get('orders_late', 0)}", inline=True)
        embed.add_field(name="Orders Failed", value=f"🔴 {stats.get('orders_failed', 0)}", inline=True)
        
        embed.set_footer(text="Use `/rank info` for rank system information.")
        
        return embed
    
    def build_collection_embed(member: discord.Member, stats: dict) -> discord.Embed:
        """Build the collection embed"""
        embed = discord.Embed(
            description="Inventory recorded.",
            color=0x58585f
        )
        
        embed.set_author(
            name=f"{member.display_name}'s Collection",
            icon_url=member.display_avatar.url
        )
        
        # Equipped
        equipped_items = []
        if stats.get("equipped_collar"):
            equipped_items.append(f"**Collar:** {stats['equipped_collar']}")
        if stats.get("equipped_badge"):
            equipped_items.append(f"**Badge:** {stats['equipped_badge']}")
        equipped_text = "\n".join(equipped_items) if equipped_items else "None equipped"
        embed.add_field(name="Equipped", value=equipped_text, inline=False)
        
        # Badges
        badges = stats.get("badges_owned", [])
        if badges:
            badges_text = ", ".join(badges[:10])
            if len(badges) > 10:
                badges_text += f" and {len(badges) - 10} more"
            embed.add_field(name="Badges", value=badges_text, inline=False)
        else:
            embed.add_field(name="Badges", value="No badges owned", inline=False)
        
        # Collars
        collars = stats.get("collars_owned", [])
        if collars:
            collars_text = ", ".join(collars[:10])
            if len(collars) > 10:
                collars_text += f" and {len(collars) - 10} more"
            embed.add_field(name="Collars", value=collars_text, inline=False)
        else:
            embed.add_field(name="Collars", value="No collars owned", inline=False)
        
        # Interfaces
        interfaces = stats.get("interfaces_owned", [])
        if interfaces:
            interfaces_text = ", ".join(interfaces[:10])
            if len(interfaces) > 10:
                interfaces_text += f" and {len(interfaces) - 10} more"
            embed.add_field(name="Interfaces", value=interfaces_text, inline=False)
        else:
            embed.add_field(name="Interfaces", value="No interfaces owned", inline=False)
        
        return embed
    
    # Rank embed builder
    def build_rank_embed(member: discord.Member, stats: dict) -> discord.Embed:
        """Build the rank progress embed with exact layout"""
        quote = select_rank_quote(stats)
        
        embed = discord.Embed(description=quote)
        embed.set_author(
            name=f"{member.display_name}'s Profile",
            icon_url=member.display_avatar.url
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Rank field (rank is already formatted with petname)
        current_rank = stats.get("rank", "Stray")
        readiness_pct = stats.get("readiness_pct", 0)
        progress_bar = make_progress_bar(readiness_pct, 12)
        blocker_text = stats.get("blocker_text", "🔓 Ready")
        rank_value = f"🐾 {current_rank}\n⭐ {progress_bar} {readiness_pct}%\n{blocker_text}"
        embed.add_field(name="Rank", value=rank_value, inline=False)
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Next Rank (format with petname if available)
        next_rank_prefix = stats.get("next_rank", "Max Rank")
        current_rank_formatted = stats.get("rank", "Stray")  # Already formatted
        petname = stats.get("petname", None)
        from systems.progression import format_rank_name
        if next_rank_prefix == "Max Rank":
            next_rank = "Max Rank"
        else:
            next_rank = format_rank_name(next_rank_prefix, petname)
        
        current_rank_prefix = stats.get("rank_prefix", "Stray")
        if next_rank_prefix == current_rank_prefix or next_rank_prefix == "Max Rank":
            next_rank = "Max Rank"
            readiness_pct = 100
            blocker_text = "🔓 Ready"
            progress_bar = make_progress_bar(100, 12)
            # Update rank field for max rank
            rank_value = f"🐾 {current_rank_formatted}\n⭐ {progress_bar} 100%\n{blocker_text}"
            embed.set_field_at(1, name="Rank", value=rank_value, inline=False)
        embed.add_field(name="Next Rank", value=f"⏫ {next_rank}", inline=False)
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Statistics, Requirements, Status (three inline fields)
        lce = stats.get("lifetime", 0)
        obedience_pct = stats.get("obedience_pct", 0)
        was = stats.get("was", 0)
        fail14 = stats.get("orders_failed", 0)
        late14 = stats.get("orders_late", 0)
        streak = stats.get("obedience_streak", 0)
        
        # Get next rank requirements (use rank_prefix for calculations)
        from systems.progression import RANK_LADDER, GATES
        rank_names = [r["name"] for r in RANK_LADDER]
        current_rank_prefix = stats.get("rank_prefix", "Stray")  # Use prefix, not formatted name
        current_idx = rank_names.index(current_rank_prefix) if current_rank_prefix in rank_names else 0
        next_idx = min(current_idx + 1, len(rank_names) - 1)
        next_rank_name = rank_names[next_idx] if next_idx > current_idx else current_rank_prefix
        
        # Get requirements for next rank
        next_gates = GATES.get(next_rank_name, [])
        req_lce = "—"
        req_obed = "—"
        req_activity = "—"
        req_fail = "—"
        req_late = "—"
        req_streak = "—"
        
        status_lce = "✅"
        status_obed = "✅"
        status_activity = "✅"
        status_fail = "✅"
        status_late = "✅"
        status_streak = "✅"
        
        # Find LCE requirement from ladder
        if next_rank_name != "Max Rank" and next_idx < len(RANK_LADDER):
            req_lce = str(RANK_LADDER[next_idx]["lce_min"])
            if lce < RANK_LADDER[next_idx]["lce_min"]:
                status_lce = "❌"
        
        # Check gates
        failing_count = 0
        for gate in next_gates:
            gate_type = gate["type"]
            gate_min = gate["min"]
            
            if gate_type == "messages_7d":
                req_activity = f"{gate_min} msgs"
                if stats.get("messages_sent", 0) < gate_min:
                    status_activity = "❌"
                    failing_count += 1
            elif gate_type == "was":
                req_activity = f"{gate_min} WAS"
                if was < gate_min:
                    status_activity = "❌"
                    failing_count += 1
            elif gate_type == "obedience14":
                req_obed = f"{gate_min}%"
                if obedience_pct < gate_min:
                    status_obed = "❌"
                    failing_count += 1
        
        # Fail/late requirements (typically <= 4 failed, <= 2 late)
        req_fail = "≤4"
        req_late = "≤2"
        if fail14 > 4:
            status_fail = "❌"
            failing_count += 1
        if late14 > 2:
            status_late = "❌"
            failing_count += 1
        
        # Statistics column
        stats_value = f"📈 `{lce}` Lifetime Coins\n"
        stats_value += f"🧠 `{obedience_pct}%` Obedience\n"
        stats_value += f"👁️ `{was}` Activity\n"
        stats_value += f"❌ `{fail14}` Failed Orders\n"
        stats_value += f"⏳ `{late14}` Late Orders\n"
        stats_value += f"🔥 `{streak}` Streak"
        
        # Requirements column
        req_value = f"{req_lce}\n{req_obed}\n{req_activity}\n{req_fail}\n{req_late}\n{req_streak}"
        
        # Status column
        status_value = f"{status_lce}\n{status_obed}\n{status_activity}\n{status_fail}\n{status_late}\n{status_streak}"
        
        embed.add_field(name="Statistics", value=stats_value, inline=True)
        embed.add_field(name="Requirements", value=req_value, inline=True)
        embed.add_field(name="Status", value=status_value, inline=True)
        
        return embed
    
    def build_rank_info_embed() -> discord.Embed:
        """Build the static rank system information embed"""
        embed = discord.Embed(
            description="Ranks are not earned by activity or coins alone.\nThey reflect consistency, obedience, and presence over time."
        )
        embed.set_author(
            name="Rank System Overview",
            icon_url="https://i.imgur.com/irmCXhw.gif"
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # How Ranks Work
        embed.add_field(
            name="How Ranks Work",
            value="• Coins determine which rank bracket you qualify for.\n• Obedience and Activity determine if you can hold it.\n• Failing requirements can put your rank at risk.",
            inline=True
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # What Affects Your Rank
        embed.add_field(
            name="What Affects Your Rank",
            value="📈 Lifetime Coins — long-term contribution.\n🧠 Obedience — order completion & streaks.\n👁️ Activity — weekly presence (messages & VC).\n❌ Failed Orders — missed responsibilities.\n⏳ Late Orders — delayed compliance.\n🔥 Streak — consecutive compliant days.",
            inline=False
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Progress & Blockers
        embed.add_field(
            name="Progress & Blockers",
            value="• Your progress bar shows readiness for the next rank\n• A blocker indicates the main requirement holding you back\n• Only one blocker is shown to keep focus clear",
            inline=False
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Stability & Risk
        embed.add_field(
            name="Stability & Risk",
            value="• Stable ranks meet all requirements\n• At-risk ranks fail one or more gates\n• Repeated instability can result in demotion",
            inline=True
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        embed.set_footer(text="Use /rank to check your progress.")
        
        return embed
    
    # Profile commands
    @bot.tree.command(name="profile", description="View your profile")
    async def profile(interaction: discord.Interaction):
        """View profile - always responds within 3s (D3)."""
        # Always respond immediately
        await interaction.response.defer()
        
        if not await check_user_command_permissions(interaction):
            return
        
        # Record command event
        if interaction.guild:
            guild_id = interaction.guild.id
            user_id = interaction.user.id
            channel_id = interaction.channel.id
            from core.db import record_command_event, bump_command
            await record_command_event(guild_id, user_id, "profile", channel_id)
            await bump_command(guild_id, user_id)
        
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.data import get_profile_stats
        from systems.handlers import get_user_petname
        from systems.progression import format_rank_name
        
        guild_id = interaction.guild.id if interaction.guild else 0
        stats = await get_profile_stats(guild_id, member.id)
        
        # Get petname and format rank name
        petname, has_petname = await get_user_petname(member)
        rank_prefix = stats.get("rank", "Stray")
        stats["rank"] = format_rank_name(rank_prefix, petname if has_petname else None)
        stats["petname"] = petname if has_petname else None
        
        embed = build_profile_embed(member, stats)
        
        if int(interaction.channel.id) in ALLOWED_SEND_SET:
            await interaction.followup.send(content=f"<@{member.id}>", embed=embed)
        else:
            await interaction.followup.send(content=f"<@{member.id}>", embed=embed, delete_after=15)
    
    # Rank commands - /rank view deleted per D1, now /rank shows only invoker
    rank_group = app_commands.Group(name="rank", description="Rank progress commands")
    
    @rank_group.command(name="info", description="View information about the rank system")
    async def rank_info(interaction: discord.Interaction):
        """View rank system information"""
        if not await check_user_command_permissions(interaction):
            return
        
        embed = build_rank_info_embed()
        
        if int(interaction.channel.id) in ALLOWED_SEND_SET:
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(embed=embed, delete_after=15)
    
    # Make /rank a subcommand instead of standalone to avoid CommandAlreadyRegistered
    @rank_group.command(name="view", description="View your personal rank progress")
    async def rank_view(interaction: discord.Interaction):
        """View personal rank progress - shows only invoker (D1)"""
        if not await check_user_command_permissions(interaction):
            return
        
        # Always use invoker, no member parameter
        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.data import get_profile_stats, get_rank
        
        guild_id = interaction.guild.id if interaction.guild else 0
        stats = await get_profile_stats(guild_id, member.id)
        
        # Get additional rank data
        rank_data = await get_rank(guild_id, member.id)
        stats.update(rank_data)
        
        # Get petname and format rank names
        from systems.handlers import get_user_petname
        from systems.progression import format_rank_name, GATES, RANK_LADDER
        petname, has_petname = await get_user_petname(member)
        rank_prefix = stats.get("rank", "Stray")
        stats["rank"] = format_rank_name(rank_prefix, petname if has_petname else None)
        stats["rank_prefix"] = rank_prefix  # Store prefix for calculations
        
        # Calculate failing gates count for quote selection
        rank_names = [r["name"] for r in RANK_LADDER]
        current_rank_name = rank_prefix  # Use prefix for calculations
        current_idx = rank_names.index(current_rank_name) if current_rank_name in rank_names else 0
        next_idx = min(current_idx + 1, len(rank_names) - 1)
        next_rank_name = rank_names[next_idx] if next_idx > current_idx else current_rank_name
        
        failing_gates_count = 0
        if next_rank_name != "Max Rank":
            next_gates = GATES.get(next_rank_name, [])
            for gate in next_gates:
                gate_type = gate["type"]
                gate_min = gate["min"]
                
                if gate_type == "messages_7d" and stats.get("messages_sent", 0) < gate_min:
                    failing_gates_count += 1
                elif gate_type == "was" and stats.get("was", 0) < gate_min:
                    failing_gates_count += 1
                elif gate_type == "obedience14" and stats.get("obedience_pct", 0) < gate_min:
                    failing_gates_count += 1
            
            if stats.get("orders_failed", 0) > 4:
                failing_gates_count += 1
            if stats.get("orders_late", 0) > 2:
                failing_gates_count += 1
        
        stats["failing_gates_count"] = failing_gates_count
        
        embed = build_rank_embed(member, stats)
        
        if int(interaction.channel.id) in ALLOWED_SEND_SET:
            await interaction.response.send_message(content=f"<@{member.id}>", embed=embed)
        else:
            await interaction.response.send_message(content=f"<@{member.id}>", embed=embed, delete_after=15)
    
    bot.tree.add_command(rank_group)
    
    # Coins commands group
    coins_group = app_commands.Group(name="coins", description="Coin management commands")
    
    @coins_group.command(name="weekly", description="Claim your weekly coins based on activity and obedience")
    async def coins_weekly(interaction: discord.Interaction):
        """Claim weekly coins - always responds within 3s (D3)."""
        # Always respond immediately
        await interaction.response.defer()
        
        if not await check_user_command_permissions(interaction):
            return
        
        if not isinstance(interaction.user, discord.Member):
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.data import get_profile_stats
        from systems.progression import weekly_claim_amount, compute_was
        from core.db import fetchone, execute, _now_iso
        
        guild_id = interaction.guild.id if interaction.guild else 0
        user_id = interaction.user.id
        
        # Check if user has already claimed this week
        claim_row = await fetchone(
            "SELECT last_claimed_at FROM weekly_claims WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        
        if claim_row and claim_row["last_claimed_at"]:
            last_claimed = datetime.datetime.fromisoformat(claim_row["last_claimed_at"].replace('Z', '+00:00'))
            now = datetime.datetime.now(datetime.UTC)
            days_since_claim = (now - last_claimed).days
            
            if days_since_claim < 7:
                days_remaining = 7 - days_since_claim
                await interaction.followup.send(
                    f"You can claim weekly coins again in {days_remaining} day(s).",
                    ephemeral=True,
                    delete_after=10
                )
                return
        
        # Get user stats
        stats = await get_profile_stats(guild_id, user_id)
        was = stats.get("was", 0)
        obedience_pct = stats.get("obedience_pct", 0)
        streak = stats.get("obedience_streak", 0)
        
        # Calculate weekly claim amount
        claim_data = await weekly_claim_amount(guild_id, user_id, was, obedience_pct, streak)
        claim_amount = claim_data["claim_amount"]
        garnish_amount = claim_data["garnish_amount"]
        
        # Award coins
        from core.data import add_coins
        await add_coins(guild_id, user_id, claim_amount, "weekly_claim", {
            "was": was,
            "obedience": obedience_pct,
            "streak": streak,
            "base": claim_data["base_amount"]
        })
        
        # If garnish to debt, update debt
        if garnish_amount > 0:
            await execute(
                """UPDATE discipline_state 
                   SET debt = debt - ?, updated_at = ?
                   WHERE guild_id = ? AND user_id = ?""",
                (garnish_amount, _now_iso(), guild_id, user_id)
            )
        
        # Record claim
        await execute(
            """INSERT OR REPLACE INTO weekly_claims (guild_id, user_id, last_claimed_at)
               VALUES (?, ?, ?)""",
            (guild_id, user_id, _now_iso())
        )
        
        # Build response embed
        embed = discord.Embed(
            title="Weekly Claim",
            description=f"🎁 **+{claim_amount} coins**",
            color=0x58585f
        )
        
        if garnish_amount > 0:
            embed.add_field(
                name="Debt Reduction",
                value=f"💳 **-{garnish_amount} coins** applied to debt",
                inline=False
            )
        
        embed.add_field(
            name="Breakdown",
            value=f"📊 WAS: {was}\n🧠 Obedience: {obedience_pct}%\n🔥 Streak: {streak} days",
            inline=False
        )
        
        embed.set_footer(text="Weekly claims reset every 7 days.")
        
        if int(interaction.channel.id) in ALLOWED_SEND_SET:
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(embed=embed, delete_after=15)
    
    bot.tree.add_command(coins_group)
    
    # Orders catalog
    ORDERS_CATALOG = {
        "presence_ping": {
            "title": "Presence Ping",
            "difficulty": "easy",
            "due_seconds": 21600,  # 6 hours
            "reward_coins": 40,
            "instructions": "Send a message to demonstrate you're here.",
            "steps_json": {"type": "message_count", "min_count": 1, "spacing_seconds": 0},
            "cooldown_type": "daily"
        },
        "profile_sync": {
            "title": "Profile Sync",
            "difficulty": "easy",
            "due_seconds": 21600,
            "reward_coins": 45,
            "instructions": "Update your profile information using /profile command.",
            "steps_json": {"type": "command_used", "command": "/profile"},
            "cooldown_type": "daily"
        },
        "gratitude_receipt": {
            "title": "Gratitude Receipt",
            "difficulty": "easy",
            "due_seconds": 28800,  # 8 hours
            "reward_coins": 50,
            "instructions": "Reply to another user's message with appreciation.",
            "steps_json": {"type": "reply_count", "min_count": 1, "exclude_bots": True},
            "cooldown_type": "daily"
        },
        "quiet_compliance": {
            "title": "Quiet Compliance",
            "difficulty": "medium",
            "due_seconds": 43200,  # 12 hours
            "reward_coins": 75,
            "instructions": "Send messages spaced apart to show measured engagement.",
            "steps_json": {"type": "message_count", "min_count": 3, "spacing_seconds": 1800},  # 30 min spacing
            "cooldown_type": "daily"
        },
        "voice_attendance": {
            "title": "Voice Attendance",
            "difficulty": "medium",
            "due_seconds": 86400,  # 24 hours
            "reward_coins": 100,
            "instructions": "Spend time in voice channels.",
            "steps_json": {"type": "vc_minutes", "min_minutes": 30},
            "cooldown_type": "daily"
        },
        "two_step_checkin": {
            "title": "Two-Step Check-in",
            "difficulty": "medium",
            "due_seconds": 43200,
            "reward_coins": 80,
            "instructions": "Send a message, then use a command within the time window.",
            "steps_json": {"type": "two_step", "message_first": True, "command_after": "/daily"},
            "cooldown_type": "daily"
        },
        "anime_post": {
            "title": "Community Contribution (Anime)",
            "difficulty": "hard",
            "due_seconds": 172800,  # 48 hours
            "reward_coins": 150,
            "instructions": "React to a post in the anime forum channel.",
            "steps_json": {"type": "forum_reaction_any_post", "channel_category": "anime"},
            "cooldown_type": "48h"
        },
        "games_post": {
            "title": "Community Contribution (Games)",
            "difficulty": "hard",
            "due_seconds": 172800,
            "reward_coins": 150,
            "instructions": "React to a post in the games forum channel.",
            "steps_json": {"type": "forum_reaction_any_post", "channel_category": "games"},
            "cooldown_type": "48h"
        },
        "discipline_deposit": {
            "title": "Discipline Deposit",
            "difficulty": "hard",
            "due_seconds": 86400,
            "reward_coins": 200,
            "instructions": "Burn coins through a discipline action (gambling, debt payment, etc.).",
            "steps_json": {"type": "ledger_event", "event_type": "burn", "min_amount": 100},
            "cooldown_type": "weekly"
        },
        "structured_hour": {
            "title": "Structured Hour",
            "difficulty": "hard",
            "due_seconds": 86400,
            "reward_coins": 180,
            "instructions": "Send a reaction to a recent message in a specified channel.",
            "steps_json": {"type": "reaction_on_channel_recent", "channel_id": None, "emoji": None, "hours_recent": 24},
            "cooldown_type": "weekly"
        }
    }
    
    # Order name mapping
    ORDER_NAME_TO_KEY = {
        "Presence Ping": "presence_ping",
        "Profile Sync": "profile_sync",
        "Gratitude Receipt": "gratitude_receipt",
        "Quiet Compliance": "quiet_compliance",
        "Voice Attendance": "voice_attendance",
        "Two-Step Check-in": "two_step_checkin",
        "Community Contribution (Anime)": "anime_post",
        "Community Contribution (Games)": "games_post",
        "Discipline Deposit": "discipline_deposit",
        "Structured Hour": "structured_hour"
    }
    
    # Daily availability tracking (in-memory, per guild)
    _orders_daily_available = {}  # {guild_id: {day_str: [order_keys]}}
    
    def _normalize_order_name(order_name: str) -> str:
        """Normalize order name to order_key"""
        return ORDER_NAME_TO_KEY.get(order_name, order_name.lower().replace(" ", "_").replace("(", "").replace(")", ""))
    
    def _get_difficulty_emoji(difficulty: str) -> str:
        """Get emoji for difficulty"""
        if difficulty == "easy":
            return "🟢"
        elif difficulty == "medium":
            return "🟡"
        elif difficulty == "hard":
            return "🔴"
        return "⚫"
    
    async def _get_available_orders(guild_id: int) -> list:
        """Get today's available orders for a guild"""
        today_str = datetime.datetime.now(datetime.UTC).date().isoformat()
        
        # Initialize if needed
        if guild_id not in _orders_daily_available:
            _orders_daily_available[guild_id] = {}
        
        guild_availability = _orders_daily_available[guild_id]
        
        # If today's selection doesn't exist, create it
        if today_str not in guild_availability:
            # Default: feature 2 easy, 2 medium, 1 hard (randomly selected)
            easy_orders = [k for k, v in ORDERS_CATALOG.items() if v["difficulty"] == "easy"]
            medium_orders = [k for k, v in ORDERS_CATALOG.items() if v["difficulty"] == "medium"]
            hard_orders = [k for k, v in ORDERS_CATALOG.items() if v["difficulty"] == "hard"]
            
            import random
            featured = random.sample(easy_orders, min(2, len(easy_orders)))
            featured.extend(random.sample(medium_orders, min(2, len(medium_orders))))
            featured.extend(random.sample(hard_orders, min(1, len(hard_orders))))
            
            guild_availability[today_str] = featured
        
        return guild_availability[today_str]
    
    def _format_due_window(seconds: int) -> str:
        """Format due window for display"""
        if seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h"
        else:
            days = seconds // 86400
            return f"{days}d"
    
    def _format_due_time(seconds: int) -> str:
        """Format due time for display (Xh Ym)"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0 and minutes > 0:
            return f"{hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h"
        elif minutes > 0:
            return f"{minutes}m"
        return "Now"
    
    def _generate_task_description(steps_json: dict) -> str:
        """Generate task description from steps_json (E2: update wording based on actual requirements)"""
        step_type = steps_json.get("type")
        
        if step_type == "message_count":
            min_count = steps_json.get("min_count", 1)
            spacing = steps_json.get("spacing_seconds", 0)
            if spacing > 0:
                spacing_min = spacing // 60
                return f"Send {min_count} message(s) with at least {spacing_min} minute(s) between each."
            else:
                return f"Send {min_count} message(s)."
        
        elif step_type == "command_used":
            cmd = steps_json.get("command", "/profile")
            return f"Use the {cmd} command."
        
        elif step_type == "reply_count":
            min_count = steps_json.get("min_count", 1)
            exclude_bots = steps_json.get("exclude_bots", False)
            if exclude_bots:
                return f"Reply to {min_count} message(s) from other users (not bots)."
            else:
                return f"Reply to {min_count} message(s)."
        
        elif step_type == "vc_minutes":
            min_minutes = steps_json.get("min_minutes", 30)
            return f"Spend at least {min_minutes} minute(s) in voice channels."
        
        elif step_type == "two_step":
            cmd = steps_json.get("command_after", "/daily")
            return f"Send a message, then use the {cmd} command within the time window."
        
        elif step_type == "forum_reaction_any_post":
            category = steps_json.get("channel_category", "forum")
            return f"React to any post in the {category} forum channel."
        
        elif step_type == "ledger_event":
            event_type = steps_json.get("event_type", "burn")
            min_amount = steps_json.get("min_amount", 100)
            if event_type == "burn":
                return f"Burn at least {min_amount} coin(s) through a discipline action (gambling, debt payment, etc.)."
            else:
                return f"Perform a ledger event of type '{event_type}' with amount at least {min_amount}."
        
        elif step_type == "reaction_on_channel_recent":
            hours = steps_json.get("hours_recent", 24)
            emoji = steps_json.get("emoji", "any emoji")
            return f"React with {emoji} to a message posted within the last {hours} hour(s) in the specified channel."
        
        # Fallback to generic description
        return "Complete the task as specified."
    
    # Orders embed builders
    def build_orders_embed(available_orders: list, guild_id: int, user_id: int) -> discord.Embed:
        """Build the /orders embed with exact layout"""
        embed = discord.Embed(
            description="Isla has issued new orders. Complete them on time."
        )
        embed.set_author(
            name="Orders",
            icon_url="https://i.imgur.com/irmCXhw.gif"
        )
        
        # Group orders by difficulty
        easy_orders = []
        medium_orders = []
        hard_orders = []
        
        for order_key in available_orders:
            if order_key in ORDERS_CATALOG:
                order = ORDERS_CATALOG[order_key]
                difficulty = order["difficulty"]
                title = order["title"]
                emoji = _get_difficulty_emoji(difficulty)
                
                if difficulty == "easy":
                    easy_orders.append(f"{emoji} {title}")
                elif difficulty == "medium":
                    medium_orders.append(f"{emoji} {title}")
                elif difficulty == "hard":
                    hard_orders.append(f"{emoji} {title}")
        
        # Add unavailable orders (all orders not in available)
        for order_key, order in ORDERS_CATALOG.items():
            if order_key not in available_orders:
                title = order["title"]
                difficulty = order["difficulty"]
                if difficulty == "easy":
                    easy_orders.append(f"⚫ ~~{title}~~")
                elif difficulty == "medium":
                    medium_orders.append(f"⚫ ~~{title}~~")
                elif difficulty == "hard":
                    hard_orders.append(f"⚫ ~~{title}~~")
        
        # Calculate info fields (due window and reward)
        def _get_section_info(order_keys: list, difficulty: str):
            """Get info for a difficulty section"""
            if not order_keys:
                return "—", "—"
            
            available_in_section = [k for k in order_keys if k in available_orders]
            if not available_in_section:
                return "—", "—"
            
            # Get min due and reward range
            due_windows = []
            rewards = []
            for key in available_in_section:
                if key in ORDERS_CATALOG:
                    order = ORDERS_CATALOG[key]
                    due_windows.append(order["due_seconds"])
                    rewards.append(order["reward_coins"])
            
            if due_windows:
                min_due = min(due_windows)
                max_due = max(due_windows)
                if min_due == max_due:
                    due_str = _format_due_window(min_due)
                else:
                    due_str = f"{_format_due_window(min_due)}–{_format_due_window(max_due)}"
            else:
                due_str = "—"
            
            if rewards:
                min_reward = min(rewards)
                max_reward = max(rewards)
                if min_reward == max_reward:
                    reward_str = f"{min_reward}"
                else:
                    reward_str = f"{min_reward}–{max_reward}"
            else:
                reward_str = "varies"
            
            return due_str, reward_str
        
        # Easy section
        easy_due, easy_reward = _get_section_info([k for k, v in ORDERS_CATALOG.items() if v["difficulty"] == "easy"], "easy")
        embed.add_field(
            name="Easy",
            value="\n".join(easy_orders) if easy_orders else "—",
            inline=True
        )
        embed.add_field(
            name="Information",
            value=f"⏳ {easy_due}\n💰 {easy_reward} coins" if easy_due != "—" else "—",
            inline=True
        )
        embed.add_field(name="", value="", inline=True)  # Spacer
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Medium section
        medium_due, medium_reward = _get_section_info([k for k, v in ORDERS_CATALOG.items() if v["difficulty"] == "medium"], "medium")
        embed.add_field(
            name="Medium",
            value="\n".join(medium_orders) if medium_orders else "—",
            inline=True
        )
        embed.add_field(
            name="Information",
            value=f"⏳ {medium_due}\n💰 {medium_reward} coins" if medium_due != "—" else "—",
            inline=True
        )
        embed.add_field(name="", value="", inline=True)  # Spacer
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Hard section
        hard_due, hard_reward = _get_section_info([k for k, v in ORDERS_CATALOG.items() if v["difficulty"] == "hard"], "hard")
        embed.add_field(
            name="Hard",
            value="\n".join(hard_orders) if hard_orders else "—",
            inline=True
        )
        embed.add_field(
            name="Information",
            value=f"⏳ {hard_due}\n💰 {hard_reward} coins" if hard_due != "—" else "—",
            inline=True
        )
        embed.add_field(name="", value="", inline=True)  # Spacer
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Remove "How Orders Work" field per A1 requirement
        return embed
    
    def build_order_info_embed(order_key: str, is_available: bool) -> discord.Embed:
        """Build the /order info embed"""
        if order_key not in ORDERS_CATALOG:
            return None
        
        order = ORDERS_CATALOG[order_key]
        
        embed = discord.Embed(
            description="Order details."
        )
        embed.set_author(
            name="Orders",
            icon_url="https://i.imgur.com/irmCXhw.gif"
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Order field
        difficulty_emoji = _get_difficulty_emoji(order["difficulty"])
        due_window = _format_due_window(order["due_seconds"])
        reward = order["reward_coins"]
        
        embed.add_field(
            name="Order",
            value=f"{difficulty_emoji} {order['title']}\n⏳ {due_window}\n💰 {reward} coins",
            inline=False
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Task field - generate description from steps_json (E2: update wording based on actual requirements)
        task_description = _generate_task_description(order["steps_json"])
        embed.add_field(
            name="Task",
            value=task_description,
            inline=False
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Completion field removed per E2
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Commands field - remove redundant line per E2
        # Field removed - buttons will handle actions
        
        # Status (optional)
        if not is_available:
            embed.add_field(
                name="Status",
                value="Not available today",
                inline=False
            )
        
        return embed
    
    def build_order_accept_embed(order_key: str, due_seconds: int) -> discord.Embed:
        """Build the /order accept embed"""
        if order_key not in ORDERS_CATALOG:
            return None
        
        order = ORDERS_CATALOG[order_key]
        
        import random
        descriptions = [
            "Accepted. Do not waste Isla's time.",
            "Order accepted."
        ]
        
        embed = discord.Embed(
            description=random.choice(descriptions)
        )
        embed.set_author(
            name="Orders",
            icon_url="https://i.imgur.com/irmCXhw.gif"
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Accepted field
        difficulty_emoji = _get_difficulty_emoji(order["difficulty"])
        due_time = _format_due_time(due_seconds)
        reward = order["reward_coins"]
        
        embed.add_field(
            name="Accepted",
            value=f"{difficulty_emoji} {order['title']}\n⏳ Due in: {due_time}\n💰 Reward: {reward} coins",
            inline=False
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Task field - generate description from steps_json (E2: update wording based on actual requirements)
        task_description = _generate_task_description(order["steps_json"])
        embed.add_field(
            name="Task",
            value=task_description,
            inline=False
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Next field
        embed.add_field(
            name="Next",
            value=f"When finished, use: `/order complete {order['title']}`",
            inline=False
        )
        
        return embed
    
    def build_order_complete_embed(order_key: str, is_late: bool, reward: int, completion_proof: str) -> discord.Embed:
        """Build the /order complete embed"""
        if order_key not in ORDERS_CATALOG:
            return None
        
        order = ORDERS_CATALOG[order_key]
        
        if is_late:
            description = "Completed late. Noted."
        else:
            description = "Completed. Good."
        
        embed = discord.Embed(
            description=description
        )
        embed.set_author(
            name="Orders",
            icon_url="https://i.imgur.com/irmCXhw.gif"
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Result field
        status_text = "Late" if is_late else "On time"
        embed.add_field(
            name="Result",
            value=f"✅ Completed: {order['title']}\n⏳ Status: {status_text}\n💰 Earned: {reward} coins",
            inline=False
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Progress field
        embed.add_field(
            name="Progress",
            value=completion_proof,
            inline=False
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Next field
        embed.add_field(
            name="Next",
            value="Check your rank progress: `/rank`",
            inline=False
        )
        
        return embed
    
    def build_order_complete_fail_embed(order_key: str, missing_requirements: list) -> discord.Embed:
        """Build the /order complete failure embed"""
        if order_key not in ORDERS_CATALOG:
            return None
        
        order = ORDERS_CATALOG[order_key]
        
        embed = discord.Embed(
            description="Not complete yet."
        )
        embed.set_author(
            name="Orders",
            icon_url="https://i.imgur.com/irmCXhw.gif"
        )
        
        # Spacer
        embed.add_field(name="", value="", inline=False)
        
        # Missing Requirements field
        embed.add_field(
            name="Missing Requirements",
            value="\n".join([f"• {req}" for req in missing_requirements]),
            inline=False
        )
        
        return embed
    
    def build_order_accept_fail_embed(reason: str) -> discord.Embed:
        """Build the /order accept failure embed"""
        embed = discord.Embed(
            description=reason
        )
        embed.set_author(
            name="Orders",
            icon_url="https://i.imgur.com/irmCXhw.gif"
        )
        return embed
    
    # Orders commands
    order_group = app_commands.Group(name="order", description="Order management commands")
    
    # Orders selection menu view (A1)
    class OrdersSelectView(discord.ui.View):
        def __init__(self, available_orders: list, guild_id: int, user_id: int):
            super().__init__(timeout=300)
            self.available_orders = available_orders
            self.guild_id = guild_id
            self.user_id = user_id
            
            # Create select menu with available orders
            options = []
            for order_key in available_orders:
                if order_key in ORDERS_CATALOG:
                    order = ORDERS_CATALOG[order_key]
                    options.append(discord.SelectOption(
                        label=order["title"],
                        description=f"{order['difficulty'].capitalize()} • {_format_due_window(order['due_seconds'])}",
                        value=order_key
                    ))
            
            if options:
                select = discord.ui.Select(
                    placeholder="Order Information",
                    options=options,
                    custom_id=f"orders_select_{guild_id}_{user_id}"
                )
                select.callback = self.on_select
                self.add_item(select)
        
        async def on_select(self, interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This is not your order menu.", ephemeral=True)
                return
            
            order_key = interaction.data["values"][0]
            await self.show_order_info(interaction, order_key)
        
        async def show_order_info(self, interaction: discord.Interaction, order_key: str):
            if order_key not in ORDERS_CATALOG:
                await interaction.response.send_message("Invalid order.", ephemeral=True)
                return
            
            order = ORDERS_CATALOG[order_key]
            embed = build_order_info_embed(order_key, True)
            
            view = OrderActionButtons(order_key, self.guild_id, self.user_id, parent_view=self)
            # Order detail view is PUBLIC
            await interaction.response.send_message(embed=embed, view=view)
    
    class OrderActionButtons(discord.ui.View):
        def __init__(self, order_key: str, guild_id: int, user_id: int, parent_view=None):
            super().__init__(timeout=300)
            self.order_key = order_key
            self.guild_id = guild_id
            self.user_id = user_id
            self.parent_view = parent_view  # Reference to OrdersSelectView for Back button
        
        @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary, custom_id="back_button")
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            """Back button - returns to /orders list view"""
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This is not your order.", ephemeral=True)
                return
            
            # Return to orders list
            available_orders = await _get_available_orders(self.guild_id)
            embed = build_orders_embed(available_orders, self.guild_id, self.user_id)
            view = OrdersSelectView(available_orders, self.guild_id, self.user_id)
            await interaction.response.edit_message(embed=embed, view=view)
        
        @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="✅")
        async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This is not your order.", ephemeral=True)
                return
            
            # Defer immediately to avoid "application did not respond"
            await interaction.response.defer()
            
            # Simulate /order accept logic
            from core.db import fetchone, execute
            order = ORDERS_CATALOG[self.order_key]
            
            # Check if already accepted
            active_run = await fetchone(
                """SELECT run_id FROM order_runs 
                   WHERE guild_id = ? AND user_id = ? AND status = 'accepted'
                   AND order_id IN (SELECT order_id FROM orders WHERE name = ?)""",
                (self.guild_id, self.user_id, order["title"])
            )
            
            if active_run:
                embed = build_order_accept_fail_embed("You already have this order accepted.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Check postponed/declined
            state = await fetchone(
                """SELECT postponed_until, declined_until FROM order_user_state 
                   WHERE guild_id = ? AND user_id = ? AND order_key = ?""",
                (self.guild_id, self.user_id, self.order_key)
            )
            
            now_ts = int(datetime.datetime.now(datetime.UTC).timestamp())
            if state:
                if state.get("postponed_until") and state["postponed_until"] > now_ts:
                    await interaction.followup.send("This order is postponed.", ephemeral=True)
                    return
                if state.get("declined_until") and state["declined_until"] > now_ts:
                    await interaction.followup.send("This order was declined. Wait 24 hours.", ephemeral=True)
                    return
            
            # Accept order (reuse existing logic from order_accept)
            available_orders = await _get_available_orders(self.guild_id)
            if self.order_key not in available_orders:
                embed = build_order_accept_fail_embed("This order is not available today.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Check cooldown/reset rules
            # Get order_id
            from core.db import fetchone as db_fetchone
            order_row = await db_fetchone(
                "SELECT order_id FROM orders WHERE guild_id = ? AND name = ?",
                (self.guild_id, order["title"])
            )
            
            if not order_row:
                # Create order if doesn't exist
                from core.db import execute, _now_iso
                await execute(
                    """INSERT INTO orders (guild_id, name, description, reward_coins, due_seconds, is_active, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?)""",
                    (self.guild_id, order["title"], order.get("instructions", ""), order["reward_coins"], order["due_seconds"], _now_iso())
                )
                order_row = await db_fetchone(
                    "SELECT order_id FROM orders WHERE guild_id = ? AND name = ?",
                    (self.guild_id, order["title"])
                )
            
            order_id = order_row["order_id"]
            
            # Get baseline VC minutes
            from core.db import get_activity_7d
            activity = await get_activity_7d(self.guild_id, self.user_id)
            vc_baseline = activity.get("vc_minutes", 0)
            import json
            progress_json = json.dumps({"vc_minutes_baseline": vc_baseline})
            
            # Call order_accept
            from core.data import order_accept
            run_id = await order_accept(self.guild_id, self.user_id, order_id, order["due_seconds"], self.order_key, progress_json)
            
            if run_id:
                embed = build_order_accept_embed(self.order_key, order["due_seconds"])
                # Edit original message to show accepted
                await interaction.message.edit(embed=embed, view=None)
                await interaction.followup.send("✅ Order accepted!", ephemeral=True)
            else:
                embed = build_order_accept_fail_embed("Failed to accept order. Please try again.")
                await interaction.followup.send(embed=embed, ephemeral=True)
        
        @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌")
        async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This is not your order.", ephemeral=True)
                return
            
            # Mark declined for 24 hours
            from core.db import execute
            now_ts = int(datetime.datetime.now(datetime.UTC).timestamp())
            decline_until = now_ts + (24 * 3600)
            
            await execute(
                """INSERT OR REPLACE INTO order_user_state (guild_id, user_id, order_key, declined_until)
                   VALUES (?, ?, ?, ?)""",
                (self.guild_id, self.user_id, self.order_key, decline_until)
            )
            
            # Edit original message to show declined
            await interaction.response.defer()
            embed = build_order_accept_fail_embed("Order declined. Wait 24 hours to accept again.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            await interaction.message.edit(embed=embed, view=None)
    
    @bot.tree.command(name="orders", description="View available orders")
    async def orders(interaction: discord.Interaction):
        """View available orders - PUBLIC (no ephemeral)"""
        if not await check_user_command_permissions(interaction):
            return
        
        guild_id = interaction.guild.id if interaction.guild else 0
        user_id = interaction.user.id
        
        available_orders = await _get_available_orders(guild_id)
        embed = build_orders_embed(available_orders, guild_id, user_id)
        
        view = OrdersSelectView(available_orders, guild_id, user_id)
        await interaction.response.send_message(embed=embed, view=view)
    
    @order_group.command(name="info", description="Get information about an order")
    @app_commands.describe(order_name="The order to get information about")
    @app_commands.choices(order_name=[
        app_commands.Choice(name="Presence Ping", value="Presence Ping"),
        app_commands.Choice(name="Profile Sync", value="Profile Sync"),
        app_commands.Choice(name="Gratitude Receipt", value="Gratitude Receipt"),
        app_commands.Choice(name="Quiet Compliance", value="Quiet Compliance"),
        app_commands.Choice(name="Voice Attendance", value="Voice Attendance"),
        app_commands.Choice(name="Two-Step Check-in", value="Two-Step Check-in"),
        app_commands.Choice(name="Community Contribution (Anime)", value="Community Contribution (Anime)"),
        app_commands.Choice(name="Community Contribution (Games)", value="Community Contribution (Games)"),
        app_commands.Choice(name="Discipline Deposit", value="Discipline Deposit"),
        app_commands.Choice(name="Structured Hour", value="Structured Hour"),
    ])
    async def order_info(interaction: discord.Interaction, order_name: str):
        """Get order information"""
        if not await check_user_command_permissions(interaction):
            return
        
        guild_id = interaction.guild.id if interaction.guild else 0
        order_key = _normalize_order_name(order_name)
        
        if order_key not in ORDERS_CATALOG:
            await interaction.response.send_message(
                f"Unknown order: {order_name}",
                ephemeral=True,
                delete_after=10
            )
            return
        
        available_orders = await _get_available_orders(guild_id)
        is_available = order_key in available_orders
        
        embed = build_order_info_embed(order_key, is_available)
        if embed:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "Error building order info embed.",
                ephemeral=True,
                delete_after=10
            )
    
    @order_group.command(name="accept", description="Accept an order")
    @app_commands.describe(order_name="The order to accept")
    @app_commands.choices(order_name=[
        app_commands.Choice(name="Presence Ping", value="Presence Ping"),
        app_commands.Choice(name="Profile Sync", value="Profile Sync"),
        app_commands.Choice(name="Gratitude Receipt", value="Gratitude Receipt"),
        app_commands.Choice(name="Quiet Compliance", value="Quiet Compliance"),
        app_commands.Choice(name="Voice Attendance", value="Voice Attendance"),
        app_commands.Choice(name="Two-Step Check-in", value="Two-Step Check-in"),
        app_commands.Choice(name="Community Contribution (Anime)", value="Community Contribution (Anime)"),
        app_commands.Choice(name="Community Contribution (Games)", value="Community Contribution (Games)"),
        app_commands.Choice(name="Discipline Deposit", value="Discipline Deposit"),
        app_commands.Choice(name="Structured Hour", value="Structured Hour"),
    ])
    async def order_accept(interaction: discord.Interaction, order_name: str):
        """Accept an order"""
        if not await check_user_command_permissions(interaction):
            return
        
        guild_id = interaction.guild.id if interaction.guild else 0
        user_id = interaction.user.id
        order_key = _normalize_order_name(order_name)
        
        if order_key not in ORDERS_CATALOG:
            await interaction.response.send_message(
                f"Unknown order: {order_name}",
                ephemeral=True,
                delete_after=10
            )
            return
        
        order = ORDERS_CATALOG[order_key]
        
        # Check if order is available today
        available_orders = await _get_available_orders(guild_id)
        if order_key not in available_orders:
            embed = build_order_accept_fail_embed("This order is not available today.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check if user already has this order active
        from core.db import fetchone
        active_run = await fetchone(
            """SELECT run_id, status FROM order_runs 
               WHERE guild_id = ? AND user_id = ? AND status IN ('accepted', 'completed')
               AND order_id IN (SELECT order_id FROM orders WHERE name = ?)""",
            (guild_id, user_id, order["title"])
        )
        
        if active_run and active_run["status"] == "accepted":
            embed = build_order_accept_fail_embed("You already have this order active. Complete it first.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check cooldown
        cooldown_type = order.get("cooldown_type", "daily")
        if cooldown_type == "daily":
            # Check if user accepted this order today
            today = datetime.datetime.now(datetime.UTC).date().isoformat()
            recent_accept = await fetchone(
                """SELECT accepted_at FROM order_runs 
                   WHERE guild_id = ? AND user_id = ? 
                   AND order_id IN (SELECT order_id FROM orders WHERE name = ?)
                   AND DATE(accepted_at) = ?""",
                (guild_id, user_id, order["title"], today)
            )
            if recent_accept:
                embed = build_order_accept_fail_embed("You can only accept this order once per day.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        elif cooldown_type == "48h":
            # Check if user accepted within last 48 hours
            from datetime import timedelta
            two_days_ago = (datetime.datetime.now(datetime.UTC) - timedelta(hours=48)).isoformat()
            recent_accept = await fetchone(
                """SELECT accepted_at FROM order_runs 
                   WHERE guild_id = ? AND user_id = ? 
                   AND order_id IN (SELECT order_id FROM orders WHERE name = ?)
                   AND accepted_at >= ?""",
                (guild_id, user_id, order["title"], two_days_ago)
            )
            if recent_accept:
                embed = build_order_accept_fail_embed("You can only accept this order once every 48 hours.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        elif cooldown_type == "weekly":
            # Check if user accepted within last 7 days
            from datetime import timedelta
            week_ago = (datetime.datetime.now(datetime.UTC) - timedelta(days=7)).isoformat()
            recent_accept = await fetchone(
                """SELECT accepted_at FROM order_runs 
                   WHERE guild_id = ? AND user_id = ? 
                   AND order_id IN (SELECT order_id FROM orders WHERE name = ?)
                   AND accepted_at >= ?""",
                (guild_id, user_id, order["title"], week_ago)
            )
            if recent_accept:
                embed = build_order_accept_fail_embed("You can only accept this order once per week.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        # Create order in DB if it doesn't exist
        from core.db import execute, _now_iso
        existing_order = await fetchone(
            "SELECT order_id FROM orders WHERE guild_id = ? AND name = ?",
            (guild_id, order["title"])
        )
        
        if not existing_order:
            # Create order in DB
            await execute(
                """INSERT INTO orders (guild_id, name, description, reward_coins, due_seconds, is_active, created_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (guild_id, order["title"], order["instructions"], order["reward_coins"], order["due_seconds"], _now_iso())
            )
            existing_order = await fetchone(
                "SELECT order_id FROM orders WHERE guild_id = ? AND name = ?",
                (guild_id, order["title"])
            )
        
        order_id = existing_order["order_id"]
        
        # Accept order (create run) - store baseline and order_key
        from core.data import order_accept
        import json
        # Get baseline VC minutes
        from core.db import get_activity_7d
        activity = await get_activity_7d(guild_id, user_id)
        vc_baseline = activity.get("vc_minutes", 0)
        progress_json = json.dumps({"vc_minutes_baseline": vc_baseline})
        
        run_id = await order_accept(guild_id, user_id, order_id, order["due_seconds"], order_key, progress_json)
        
        if run_id:
            embed = build_order_accept_embed(order_key, order["due_seconds"])
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "Failed to accept order. Please try again.",
                ephemeral=True,
                delete_after=10
            )
    
    @order_group.command(name="complete", description="Complete an accepted order")
    @app_commands.describe(order_name="The order to complete")
    @app_commands.choices(order_name=[
        app_commands.Choice(name="Presence Ping", value="Presence Ping"),
        app_commands.Choice(name="Profile Sync", value="Profile Sync"),
        app_commands.Choice(name="Gratitude Receipt", value="Gratitude Receipt"),
        app_commands.Choice(name="Quiet Compliance", value="Quiet Compliance"),
        app_commands.Choice(name="Voice Attendance", value="Voice Attendance"),
        app_commands.Choice(name="Two-Step Check-in", value="Two-Step Check-in"),
        app_commands.Choice(name="Community Contribution (Anime)", value="Community Contribution (Anime)"),
        app_commands.Choice(name="Community Contribution (Games)", value="Community Contribution (Games)"),
        app_commands.Choice(name="Discipline Deposit", value="Discipline Deposit"),
        app_commands.Choice(name="Structured Hour", value="Structured Hour"),
    ])
    async def order_complete(interaction: discord.Interaction, order_name: str):
        """Complete an order"""
        if not await check_user_command_permissions(interaction):
            return
        
        guild_id = interaction.guild.id if interaction.guild else 0
        user_id = interaction.user.id
        order_key = _normalize_order_name(order_name)
        
        if order_key not in ORDERS_CATALOG:
            await interaction.response.send_message(
                f"Unknown order: {order_name}",
                ephemeral=True,
                delete_after=10
            )
            return
        
        order = ORDERS_CATALOG[order_key]
        
        # Find active run for this order
        from core.db import fetchone
        active_run = await fetchone(
            """SELECT run_id, accepted_at, due_at, status, progress_json FROM order_runs 
               WHERE guild_id = ? AND user_id = ? AND status = 'accepted'
               AND order_id IN (SELECT order_id FROM orders WHERE name = ?)
               ORDER BY accepted_at DESC LIMIT 1""",
            (guild_id, user_id, order["title"])
        )
        
        if not active_run:
            embed = build_order_complete_fail_embed(order_key, ["You don't have this order accepted."])
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        run_id = active_run["run_id"]
        accepted_at = datetime.datetime.fromisoformat(active_run["accepted_at"].replace('Z', '+00:00'))
        due_at = datetime.datetime.fromisoformat(active_run["due_at"].replace('Z', '+00:00'))
        now = datetime.datetime.now(datetime.UTC)
        is_late = now > due_at
        
        # Verify completion
        steps = order["steps_json"]
        missing_requirements = []
        completion_proof_parts = []
        
        accepted_at_ts = int(accepted_at.timestamp())
        
        # Verify based on step type using event tables
        from core.db import fetchall
        if steps["type"] == "message_count":
            min_count = steps.get("min_count", 1)
            spacing = steps.get("spacing_seconds", 0)
            
            # Query message_events after accepted_at
            message_rows = await fetchall(
                """SELECT ts FROM message_events 
                   WHERE guild_id = ? AND user_id = ? AND ts >= ?
                   ORDER BY ts""",
                (guild_id, user_id, accepted_at_ts)
            )
            
            if spacing > 0:
                # Apply spacing rule: count messages with min spacing between them
                valid_messages = []
                for row in message_rows:
                    ts = row["ts"]
                    if not valid_messages or (ts - valid_messages[-1]) >= spacing:
                        valid_messages.append(ts)
                total_messages = len(valid_messages)
            else:
                total_messages = len(message_rows)
            
            if total_messages < min_count:
                missing_requirements.append(f"Send {min_count} message(s) with spacing (have {total_messages})")
            else:
                completion_proof_parts.append(f"💬 Messages: {total_messages}/{min_count}")
        
        elif steps["type"] == "command_used":
            cmd = steps.get("command", "/profile")
            cmd_name = cmd.replace("/", "")
            
            # Query command_events after accepted_at
            cmd_rows = await fetchall(
                """SELECT ts FROM command_events 
                   WHERE guild_id = ? AND user_id = ? AND command_name = ? AND ts >= ?""",
                (guild_id, user_id, cmd_name, accepted_at_ts)
            )
            
            if len(cmd_rows) == 0:
                missing_requirements.append(f"Use the {cmd} command")
            else:
                completion_proof_parts.append(f"✅ Command used: {cmd}")
        
        elif steps["type"] == "reply_count":
            min_count = steps.get("min_count", 1)
            
            # Query message_events for replies after accepted_at
            reply_rows = await fetchall(
                """SELECT ts FROM message_events 
                   WHERE guild_id = ? AND user_id = ? AND ts >= ?
                   AND is_reply = 1 AND replied_to_user_is_bot = 0""",
                (guild_id, user_id, accepted_at_ts)
            )
            
            total_replies = len(reply_rows)
            
            if total_replies < min_count:
                missing_requirements.append(f"Reply to {min_count} user message(s) (have {total_replies})")
            else:
                completion_proof_parts.append(f"💬 Replies: {total_replies}/{min_count}")
        
        elif steps["type"] == "vc_minutes":
            min_minutes = steps.get("min_minutes", 30)
            
            # Get baseline from progress_json
            import json
            progress_data = {}
            if active_run.get("progress_json"):
                try:
                    progress_data = json.loads(active_run["progress_json"])
                except:
                    pass
            
            vc_baseline = progress_data.get("vc_minutes_baseline", 0)
            
            # Get current VC minutes from activity_daily delta since accepted_at
            accepted_date = accepted_at.date().isoformat()
            activity_rows = await fetchall(
                """SELECT SUM(vc_minutes) as total FROM activity_daily 
                   WHERE guild_id = ? AND user_id = ? AND day >= ?""",
                (guild_id, user_id, accepted_date)
            )
            
            current_vc = activity_rows[0]["total"] if activity_rows and activity_rows[0]["total"] else 0
            delta_vc = current_vc - vc_baseline
            
            if delta_vc < min_minutes:
                missing_requirements.append(f"Spend {min_minutes} minutes in VC (have {delta_vc})")
            else:
                completion_proof_parts.append(f"🎧 VC: {delta_vc}/{min_minutes} min")
        
        elif steps["type"] == "two_step":
            cmd = steps.get("command_after", "/daily")
            cmd_name = cmd.replace("/", "")
            
            # Verify: message first, then command
            message_rows = await fetchall(
                """SELECT MIN(ts) as first_msg_ts FROM message_events 
                   WHERE guild_id = ? AND user_id = ? AND ts >= ?""",
                (guild_id, user_id, accepted_at_ts)
            )
            
            if not message_rows or not message_rows[0]["first_msg_ts"]:
                missing_requirements.append("Send a message first")
            else:
                first_msg_ts = message_rows[0]["first_msg_ts"]
                
                # Check if command was used after first message
                cmd_rows = await fetchall(
                    """SELECT ts FROM command_events 
                       WHERE guild_id = ? AND user_id = ? AND command_name = ? 
                       AND ts >= ? AND ts > ?""",
                    (guild_id, user_id, cmd_name, accepted_at_ts, first_msg_ts)
                )
                
                if len(cmd_rows) == 0:
                    missing_requirements.append(f"Use {cmd} command after sending a message")
                else:
                    completion_proof_parts.append(f"✅ Two-step: message + {cmd}")
        
        elif steps["type"] == "forum_reaction_any_post":
            category = steps.get("channel_category", "forum")
            
            # Query reaction_events for forum reactions after accepted_at
            # Note: Channel matching would require channel_id from config, simplified here
            reaction_rows = await fetchall(
                """SELECT ts FROM reaction_events 
                   WHERE guild_id = ? AND user_id = ? AND ts >= ?
                   AND is_forum = 1""",
                (guild_id, user_id, accepted_at_ts)
            )
            
            if len(reaction_rows) == 0:
                missing_requirements.append(f"React to a post in the {category} forum")
            else:
                completion_proof_parts.append(f"❤️ Reaction: detected in {category}")
        
        elif steps["type"] == "ledger_event":
            min_amount = steps.get("min_amount", 100)
            
            # Query ledger for burns after accepted_at
            ledger_rows = await fetchall(
                """SELECT amount FROM economy_ledger 
                   WHERE guild_id = ? AND user_id = ? AND ts >= ? 
                   AND type = 'burn' AND amount < 0
                   ORDER BY ts""",
                (guild_id, user_id, accepted_at.isoformat())
            )
            
            total_burned = abs(sum(row["amount"] for row in ledger_rows))
            
            if total_burned < min_amount:
                missing_requirements.append(f"Burn {min_amount} coins (have burned {total_burned})")
            else:
                completion_proof_parts.append(f"💰 Coins burned: {total_burned}/{min_amount}")
        
        elif steps["type"] == "reaction_on_channel_recent":
            hours = steps.get("hours_recent", 24)
            channel_id = steps.get("channel_id")
            emoji_str = steps.get("emoji")
            
            # Calculate recent threshold
            recent_threshold_ts = int((datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=hours)).timestamp())
            query_ts = max(accepted_at_ts, recent_threshold_ts)
            
            # Query reaction_events with channel and emoji matching
            if channel_id and emoji_str:
                reaction_rows = await fetchall(
                    """SELECT ts FROM reaction_events 
                       WHERE guild_id = ? AND user_id = ? AND ts >= ?
                       AND channel_id = ? AND emoji = ?""",
                    (guild_id, user_id, query_ts, channel_id, emoji_str)
                )
            else:
                # Fallback: any recent reaction
                reaction_rows = await fetchall(
                    """SELECT ts FROM reaction_events 
                       WHERE guild_id = ? AND user_id = ? AND ts >= ?""",
                    (guild_id, user_id, query_ts)
                )
            
            if len(reaction_rows) == 0:
                missing_requirements.append(f"React to a message within the last {hours} hours")
            else:
                completion_proof_parts.append(f"❤️ Reaction: detected (last {hours}h)")
        
        # Check if verification failed
        if missing_requirements:
            embed = build_order_complete_fail_embed(order_key, missing_requirements)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Complete the order
        from core.data import order_complete, add_coins
        result = await order_complete(guild_id, user_id, run_id, is_late)
        
        if result and result.get("success"):
            completion_proof = "\n".join(completion_proof_parts) if completion_proof_parts else "✅ Task completed"
            embed = build_order_complete_embed(order_key, is_late, order["reward_coins"], completion_proof)
            
            # Add streak bonus message if applicable
            if result.get("bonus_awarded"):
                streak_bonus = result.get("streak_bonus", 25)
                if embed.footer and embed.footer.text:
                    embed.set_footer(text=f"{embed.footer.text} | Streak bonus: +{streak_bonus} coins")
                else:
                    embed.set_footer(text=f"Streak bonus: +{streak_bonus} coins")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "Failed to complete order. Please try again.",
                ephemeral=True,
                delete_after=10
            )
    
    @order_group.command(name="status", description="View progress on your active orders")
    async def order_status(interaction: discord.Interaction):
        """View order progress status"""
        if not await check_user_command_permissions(interaction):
            return
        
        guild_id = interaction.guild.id if interaction.guild else 0
        user_id = interaction.user.id
        
        # Get all active orders
        from core.db import fetchall, fetchone
        active_runs = await fetchall(
            """SELECT run_id, order_id, accepted_at, due_at, progress_json 
               FROM order_runs 
               WHERE guild_id = ? AND user_id = ? AND status = 'accepted'
               ORDER BY accepted_at DESC""",
            (guild_id, user_id)
        )
        
        if not active_runs:
            embed = discord.Embed(
                description="You have no active orders."
            )
            embed.set_author(
                name="Order Progress Status",
                icon_url="https://i.imgur.com/irmCXhw.gif"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed()
        embed.set_author(
            name="Order Progress Status",
            icon_url="https://i.imgur.com/irmCXhw.gif"
        )
        
        accepted_at_ts_base = int(datetime.datetime.now(datetime.UTC).timestamp())
        
        for run in active_runs:
            # Get order info
            order_row = await fetchone(
                "SELECT name FROM orders WHERE order_id = ?",
                (run["order_id"],)
            )
            
            if not order_row:
                continue
            
            order_name = order_row["name"]
            order_key = _normalize_order_name(order_name)
            
            if order_key not in ORDERS_CATALOG:
                continue
            
            order = ORDERS_CATALOG[order_key]
            steps = order["steps_json"]
            accepted_at = datetime.datetime.fromisoformat(run["accepted_at"].replace('Z', '+00:00'))
            due_at = datetime.datetime.fromisoformat(run["due_at"].replace('Z', '+00:00'))
            now = datetime.datetime.now(datetime.UTC)
            accepted_at_ts = int(accepted_at.timestamp())
            
            # Calculate time left
            time_left_seconds = int((due_at - now).total_seconds())
            if time_left_seconds <= 0:
                time_left = "⏳ Overdue"
            else:
                hours = time_left_seconds // 3600
                minutes = (time_left_seconds % 3600) // 60
                if hours > 0:
                    time_left = f"⏳ {hours}h {minutes}min"
                else:
                    time_left = f"⏳ {minutes}min"
            
            # Calculate progress based on step type
            progress_lines = []
            
            if steps["type"] == "message_count":
                min_count = steps.get("min_count", 1)
                spacing = steps.get("spacing_seconds", 0)
                message_rows = await fetchall(
                    """SELECT ts FROM message_events 
                       WHERE guild_id = ? AND user_id = ? AND ts >= ?
                       ORDER BY ts""",
                    (guild_id, user_id, accepted_at_ts)
                )
                
                if spacing > 0:
                    valid_messages = []
                    for row in message_rows:
                        ts = row["ts"]
                        if not valid_messages or (ts - valid_messages[-1]) >= spacing:
                            valid_messages.append(ts)
                    total = len(valid_messages)
                else:
                    total = len(message_rows)
                
                progress_lines.append(f"Messages Sent: {total}/{min_count}")
            
            elif steps["type"] == "vc_minutes":
                min_minutes = steps.get("min_minutes", 30)
                progress_data = {}
                if run.get("progress_json"):
                    import json
                    try:
                        progress_data = json.loads(run["progress_json"])
                    except:
                        pass
                
                vc_baseline = progress_data.get("vc_minutes_baseline", 0)
                accepted_date = accepted_at.date().isoformat()
                activity_rows = await fetchall(
                    """SELECT SUM(vc_minutes) as total FROM activity_daily 
                       WHERE guild_id = ? AND user_id = ? AND day >= ?""",
                    (guild_id, user_id, accepted_date)
                )
                
                current_vc = activity_rows[0]["total"] if activity_rows and activity_rows[0]["total"] else 0
                delta_vc = current_vc - vc_baseline
                
                progress_lines.append(f"Voice Chat Time: {delta_vc}/{min_minutes} minutes")
            
            elif steps["type"] == "reply_count":
                min_count = steps.get("min_count", 1)
                reply_rows = await fetchall(
                    """SELECT ts FROM message_events 
                       WHERE guild_id = ? AND user_id = ? AND ts >= ?
                       AND is_reply = 1 AND replied_to_user_is_bot = 0""",
                    (guild_id, user_id, accepted_at_ts)
                )
                total = len(reply_rows)
                progress_lines.append(f"Replies: {total}/{min_count}")
            
            elif steps["type"] == "command_used":
                cmd = steps.get("command", "/profile")
                cmd_name = cmd.replace("/", "")
                cmd_rows = await fetchall(
                    """SELECT ts FROM command_events 
                       WHERE guild_id = ? AND user_id = ? AND command_name = ? AND ts >= ?""",
                    (guild_id, user_id, cmd_name, accepted_at_ts)
                )
                total = len(cmd_rows)
                progress_lines.append(f"Commands Used: {total}/1")
            
            elif steps["type"] == "reaction_on_channel_recent":
                hours = steps.get("hours_recent", 24)
                reaction_rows = await fetchall(
                    """SELECT ts FROM reaction_events 
                       WHERE guild_id = ? AND user_id = ? AND ts >= ?""",
                    (guild_id, user_id, accepted_at_ts)
                )
                total = len(reaction_rows)
                progress_lines.append(f"Reactions: {total}/1")
            
            # Add spacer between orders
            embed.add_field(name="", value="", inline=False)
            
            # Add order progress
            difficulty_emoji = _get_difficulty_emoji(order["difficulty"])
            progress_text = "\n".join(progress_lines) if progress_lines else "Progress tracking..."
            
            embed.add_field(
                name=f"{difficulty_emoji} {order_name}",
                value=progress_text,
                inline=True
            )
            
            embed.add_field(
                name="Time Left",
                value=time_left,
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    bot.tree.add_command(order_group)
    
    # /collection command deleted per D2
    
    # Notifyme command (B1)
    class NotifymeView(discord.ui.View):
        def __init__(self, guild_id: int, user_id: int):
            super().__init__(timeout=300)
            self.guild_id = guild_id
            self.user_id = user_id
        
        @discord.ui.button(label="Start", style=discord.ButtonStyle.green, emoji="✅")
        async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This is not your notification menu.", ephemeral=True)
                return
            
            from core.db import execute
            await execute(
                """INSERT OR REPLACE INTO user_notifications (guild_id, user_id, enabled)
                   VALUES (?, ?, 1)""",
                (self.guild_id, self.user_id)
            )
            
            await interaction.response.send_message("Notifications enabled. You will receive reminders for new orders and warnings when orders are close to expiring.", ephemeral=True)
        
        @discord.ui.button(label="Stop", style=discord.ButtonStyle.red, emoji="❌")
        async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This is not your notification menu.", ephemeral=True)
                return
            
            from core.db import execute
            await execute(
                """INSERT OR REPLACE INTO user_notifications (guild_id, user_id, enabled)
                   VALUES (?, ?, 0)""",
                (self.guild_id, self.user_id)
            )
            
            await interaction.response.send_message("Notifications disabled.", ephemeral=True)
    
    @bot.tree.command(name="notifyme", description="Enable or disable order notifications")
    async def notifyme(interaction: discord.Interaction):
        """Notification preferences - always responds within 3s (D3)."""
        # Always respond immediately
        await interaction.response.defer()
        
        if not await check_user_command_permissions(interaction):
            return
        
        guild_id = interaction.guild.id if interaction.guild else 0
        user_id = interaction.user.id
        
        embed = discord.Embed(
            description="Get notified whenever IslaBot posts new updates."
        )
        embed.set_author(name="Notifications")
        
        view = NotifymeView(guild_id, user_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

