"""
User commands for the bot - level, leaderboard, balance, daily, give, gambling, etc.
"""
import discord
from discord import app_commands
import datetime

from core.config import (
    USER_COMMAND_CHANNEL_ID, ALLOWED_SEND_SET, LEVEL_COIN_BONUSES,
    LEVEL_ROLE_MAP, EVENT_CHANNEL_ID
)
from core.data import (
    xp_data, get_coins, get_level, get_xp, add_coins, has_coins, save_xp_data,
    get_activity_quote
)
from core.utils import next_level_requirement, get_timezone, USE_PYTZ
from systems.leaderboards import (
    build_levels_leaderboard_embed, build_coins_leaderboard_embed,
    build_activity_leaderboard_embed, LeaderboardView
)
from systems.gambling import (
    gamble, dice, slots_bet, slots_free, coinflip, allin,
    check_gambling_cooldown
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
        is_interaction = True
    else:
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
    
    return True

# Create level group for subcommands
level_group = None

def register_commands(bot_instance):
    """Register all user commands with the bot"""
    global bot, level_group
    bot = bot_instance
    
    level_group = app_commands.Group(name="level", description="Level-related commands")
    
    @level_group.command(name="check", description="Check your current level")
    @app_commands.describe(member="The member to check (optional, defaults to you)")
    async def level_check(interaction: discord.Interaction, member: discord.Member = None):
        if not await check_user_command_permissions(interaction):
            return
        
        member = member or interaction.user
        user_id = member.id
        uid = str(user_id)
        
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
        
        level_role = "None"
        for lvl, role_id in sorted(LEVEL_ROLE_MAP.items(), reverse=True):
            if level_val >= lvl:
                role = interaction.guild.get_role(role_id)
                if role:
                    level_role = role.name
                break
        
        equipped_collar = user_data.get("equipped_collar")
        collar_display = f" {equipped_collar}" if equipped_collar else ""
        
        activity_quote = get_activity_quote(user_id, interaction.guild)
        
        vc_minutes = user_data.get("vc_minutes", 0)
        vc_hours = vc_minutes // 60
        vc_mins = vc_minutes % 60
        vc_time_str = f"{vc_hours}h {vc_mins}m" if vc_hours > 0 else f"{vc_mins}m"
        
        badges_owned = user_data.get("badges_owned", [])
        collars_owned = user_data.get("collars_owned", [])
        interfaces_owned = user_data.get("interfaces_owned", [])
        
        badges_display = ", ".join(badges_owned) if badges_owned else "No badges owned."
        collars_display = ", ".join(collars_owned) if collars_owned else "No collars owned."
        interfaces_display = ", ".join(interfaces_owned) if interfaces_owned else "No interfaces/themes owned."
        
        showcased_badge = user_data.get("equipped_badge")
        if not showcased_badge and badges_owned:
            showcased_badge = badges_owned[0]
        thumbnail_url = None
        
        embed = discord.Embed(
            title=f"{member.display_name}'s Server Profile{collar_display}",
            description=f"*{activity_quote}*\n",
            color=0x58585f
        )
        
        embed.add_field(name="Current Level", value=str(level_val), inline=True)
        embed.add_field(name="Milestone", value=level_role, inline=True)
        embed.add_field(name="XP", value=str(xp), inline=True)
        embed.add_field(name="", value="", inline=False)
        embed.add_field(name="Messages Sent", value=f"💬 {user_data.get('messages_sent', 0)}", inline=True)
        embed.add_field(name="Voice Chat Time", value=f"🎙️ {vc_time_str}", inline=True)
        embed.add_field(name="Event Participations", value=f"🎫 {user_data.get('event_participations', 0)}", inline=True)
        embed.add_field(name="", value="", inline=False)
        embed.add_field(name="Balance", value=f"💵 {coins}", inline=True)
        embed.add_field(name="Times Gambled", value=f"🎲 {user_data.get('times_gambled', 0)}", inline=True)
        embed.add_field(name="Total Wins", value=f"🏆 {user_data.get('total_wins', 0)}", inline=True)
        embed.add_field(name="", value="", inline=False)
        embed.add_field(name="Badge Collection", value=badges_display, inline=False)
        embed.add_field(name="Collar Collection", value=collars_display, inline=False)
        embed.add_field(name="Interface Collection", value=interfaces_display, inline=False)
        
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        if int(interaction.channel.id) in ALLOWED_SEND_SET:
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(embed=embed, delete_after=10)
    
    bot.tree.add_command(level_group)
    
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
    
    # Standalone leaderboards command (plural) - shows menu
    @bot.tree.command(name="leaderboards", description="View available leaderboards")
    async def leaderboards_menu(interaction: discord.Interaction):
        """Show leaderboard menu"""
        if not await check_user_command_permissions(interaction):
            return
        
        embed = discord.Embed(
            title="Leaderboards",
            description="Which leaderboard would you like to check?\n",
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
            name="",
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
        
        from core.data import xp_data
        
        guild = interaction.guild
        if guild:
            guild_member_ids = {str(member.id) for member in guild.members}
            filtered_xp_data = {uid: data for uid, data in xp_data.items() if uid in guild_member_ids}
        else:
            filtered_xp_data = xp_data
        
        lb_type = leaderboard_type.value if isinstance(leaderboard_type, app_commands.Choice) else leaderboard_type
        
        if lb_type == "levels":
            sorted_users = sorted(filtered_xp_data.items(), key=lambda x: x[1].get("xp", 0), reverse=True)
            if not sorted_users:
                embed = discord.Embed(
                    title="💋 Levels Leaderboard",
                    description="No users found in this server.",
                    color=0x58585f,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            embed = build_levels_leaderboard_embed(sorted_users, page=0, users_per_page=20)
            view = LeaderboardView(sorted_users, build_levels_leaderboard_embed, users_per_page=20)
            
            try:
                if int(interaction.channel.id) in ALLOWED_SEND_SET:
                    await interaction.response.send_message(embed=embed, view=view)
                else:
                    await interaction.response.send_message(embed=embed, view=view, delete_after=15)
            except Exception as e:
                print(f"Error sending leaderboard: {e}")
                if int(interaction.channel.id) in ALLOWED_SEND_SET:
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message(embed=embed, delete_after=15)
            return
            
        elif lb_type == "coins":
            sorted_users = sorted(filtered_xp_data.items(), key=lambda x: x[1].get("coins", 0), reverse=True)
            if not sorted_users:
                embed = discord.Embed(
                    title="💵 Coin Leaderboard",
                    description="No users found in this server.",
                    color=0x58585f,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            embed = build_coins_leaderboard_embed(sorted_users, page=0, users_per_page=20)
            view = LeaderboardView(sorted_users, build_coins_leaderboard_embed, users_per_page=20)
            
            try:
                if int(interaction.channel.id) in ALLOWED_SEND_SET:
                    await interaction.response.send_message(embed=embed, view=view)
                else:
                    await interaction.response.send_message(embed=embed, view=view, delete_after=15)
            except Exception as e:
                print(f"Error sending leaderboard: {e}")
                if int(interaction.channel.id) in ALLOWED_SEND_SET:
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message(embed=embed, delete_after=15)
            return
            
        elif lb_type == "activity":
            sorted_users = sorted(
                filtered_xp_data.items(),
                key=lambda x: (x[1].get("messages_sent", 0) + x[1].get("vc_minutes", 0)),
                reverse=True
            )
            if not sorted_users:
                embed = discord.Embed(
                    title="🎀 Activity Leaderboard",
                    description="No users found in this server.",
                    color=0x58585f,
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            embed = build_activity_leaderboard_embed(sorted_users, page=0, users_per_page=20)
            view = LeaderboardView(sorted_users, build_activity_leaderboard_embed, users_per_page=20)
            
            try:
                if int(interaction.channel.id) in ALLOWED_SEND_SET:
                    await interaction.response.send_message(embed=embed, view=view)
                else:
                    await interaction.response.send_message(embed=embed, view=view, delete_after=15)
            except Exception as e:
                print(f"Error sending leaderboard: {e}")
                if int(interaction.channel.id) in ALLOWED_SEND_SET:
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message(embed=embed, delete_after=15)
            return
        
        else:
            embed = discord.Embed(
                title="Leaderboards",
                description="Which leaderboard would you like to check?\n",
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
                name="",
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
    
    @bot.tree.command(name="balance", description="Show your coin balance and level info")
    async def balance(interaction: discord.Interaction):
        """Show user's coin balance and level info."""
        if not await check_user_command_permissions(interaction):
            return
        
        user_id = interaction.user.id
        user = interaction.user
        coins = get_coins(user_id)
        level = get_level(user_id)
        
        # Get user's display name (nickname if available, otherwise username)
        display_name = user.display_name if hasattr(user, 'display_name') else user.name
        
        # Check if daily has been claimed
        on_cooldown, reset_timestamp = check_daily_cooldown(user_id)
        daily_status = "✅ Claimed" if on_cooldown else "❌ Not Claimed"
        
        # Find next bonus level
        next_bonus_level = None
        for bonus_level in sorted(LEVEL_COIN_BONUSES.keys()):
            if bonus_level > level:
                next_bonus_level = bonus_level
                break
        
        next_bonus_text = f"Level {next_bonus_level} ({LEVEL_COIN_BONUSES[next_bonus_level]} coins)" if next_bonus_level else "Max level reached"
        
        embed = discord.Embed(
            title=f"{display_name}'s Total Balance",
            description=f"{coins} coins.\n\u200b",
            color=0xff9d14,
        )
        embed.add_field(name="Next Bonus", value=next_bonus_text, inline=True)
        embed.add_field(name="Daily Coins", value=daily_status, inline=True)
        embed.set_thumbnail(url="https://i.imgur.com/yYBNX08.png")
        embed.set_footer(text="Use /daily to claim free coins.")
        
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
        
        level = get_level(user_id)
        base_daily = min(500, int(100 + (level * 4.5)))
        level_bonus = 100 if level >= 100 else 0
        daily_amount = base_daily + level_bonus
        
        uk_tz = get_timezone("Europe/London")
        if uk_tz:
            if USE_PYTZ:
                now_uk = datetime.datetime.now(uk_tz)
            else:
                now_uk = datetime.datetime.now(uk_tz)
            weekday = now_uk.weekday()
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
        
        # Format level bonus field
        level_bonus_text = f"+{level_bonus} coins" if level_bonus > 0 else "❌ No Bonus"
        
        # Format weekend bonus field
        weekend_bonus_text = "✅ +25 coins" if weekend_bonus else "❌ Not Active"
        
        embed = discord.Embed(
            title="Daily Coins",
            description=f"Claimed {daily_amount} coins!\n\u200b",
            color=0xff9d14,
        )
        embed.add_field(name="Level Bonus", value=level_bonus_text, inline=True)
        embed.add_field(name="Weekend Bonus", value=weekend_bonus_text, inline=True)
        embed.set_thumbnail(url="https://i.imgur.com/ZKq5nZ2.png")
        embed.set_footer(text="Resets daily at 6:00 PM GMT")
        
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
    
    # Gambling commands - import from gambling module
    @bot.tree.command(name="gamble", description="Gamble coins - 49/51 chance to double or lose")
    @app_commands.describe(bet="The amount of coins to bet (minimum 10)")
    async def gamble_command(interaction: discord.Interaction, bet: int):
        await gamble(interaction, bet)
    
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
    async def dice_command(interaction: discord.Interaction, bet: int):
        await dice(interaction, bet)
    
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
    async def coinflip_command(interaction: discord.Interaction, bet: int):
        await coinflip(interaction, bet)
    
    @bot.tree.command(name="coinflipinfo", description="Show coinflip info")
    async def coinflipinfo(interaction: discord.Interaction):
        """Show coinflip info."""
        await gambleinfo(interaction)
    
    @bot.tree.command(name="allin", description="Go all-in on a game (bet all coins)")
    @app_commands.describe(game="The game to play (gamble, dice, or slots)")
    async def allin_command(interaction: discord.Interaction, game: str):
        await allin(interaction, game)
    
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

