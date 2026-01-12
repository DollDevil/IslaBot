"""
Admin commands for the bot - config, obedience, testembeds, throne, killevent, sync, etc.
"""
import discord
from discord import app_commands
import datetime

from core.config import (
    ADMIN_COMMAND_CHANNEL_ID, ADMIN_ROLE_IDS, EVENT_CHANNEL_ID,
    XP_TRACK_SET, ALLOWED_SEND_SET, MULTIPLIER_ROLE_SET, EXCLUDED_ROLE_SET,
    NON_XP_CATEGORY_IDS, NON_XP_CHANNEL_IDS, CHANNEL_MULTIPLIERS,
    MESSAGE_COOLDOWN, VC_XP, HEART_GIF
)
from core.utils import get_timezone, USE_PYTZ
from systems.gambling import build_casino_embed
# Legacy event system imports removed

# Central message registry: {message_id: {"kind": str, "visibility": str, "impact": str}}
# kind: "single" or "flow-step"
# visibility: "ephemeral", "public", or "dm"
# impact: "positive", "neutral", or "negative"
MESSAGES = {
    # Onboarding messages
    "onboarding.welcome": {"kind": "single", "visibility": "dm", "impact": "neutral"},
    "onboarding.rules": {"kind": "single", "visibility": "ephemeral", "impact": "neutral"},
    "onboarding.rules_accept_1": {"kind": "flow-step", "visibility": "ephemeral", "impact": "positive"},
    "onboarding.rules_decline_1": {"kind": "flow-step", "visibility": "ephemeral", "impact": "negative"},
    "onboarding.rules_accept_2": {"kind": "flow-step", "visibility": "ephemeral", "impact": "positive"},
    "onboarding.rules_decline_2": {"kind": "flow-step", "visibility": "ephemeral", "impact": "negative"},
    "onboarding.rules_submission_false": {"kind": "single", "visibility": "ephemeral", "impact": "negative"},
    "onboarding.rules_submission_correct": {"kind": "single", "visibility": "public", "impact": "positive"},
    # Profile messages
    "profile.profile": {"kind": "single", "visibility": "public", "impact": "neutral"},
    "profile.collection": {"kind": "single", "visibility": "public", "impact": "neutral"},
    # Rank messages
    "rank.rank": {"kind": "single", "visibility": "public", "impact": "neutral"},
    "rank.rank_info": {"kind": "single", "visibility": "public", "impact": "neutral"},
    # Order messages
    "orders.orders": {"kind": "single", "visibility": "ephemeral", "impact": "neutral"},
    "orders.order_info": {"kind": "single", "visibility": "ephemeral", "impact": "neutral"},
    "orders.order_accept": {"kind": "flow-step", "visibility": "ephemeral", "impact": "positive"},
    "orders.order_complete": {"kind": "flow-step", "visibility": "ephemeral", "impact": "positive"},
    "orders.order_status": {"kind": "single", "visibility": "ephemeral", "impact": "neutral"},
    # Notification messages
    "notifyme.start": {"kind": "single", "visibility": "ephemeral", "impact": "positive"},
    "notifyme.stop": {"kind": "single", "visibility": "ephemeral", "impact": "neutral"},
    # Announcement messages
    "announcements.orders_drop": {"kind": "single", "visibility": "public", "impact": "neutral"},
    "announcements.throne": {"kind": "single", "visibility": "public", "impact": "neutral"},
    "announcements.coffee": {"kind": "single", "visibility": "public", "impact": "neutral"},
    # Bank messages
    "bank.balance": {"kind": "single", "visibility": "ephemeral", "impact": "neutral"},
    "bank.transfer": {"kind": "single", "visibility": "ephemeral", "impact": "neutral"},
    "bank.tax": {"kind": "single", "visibility": "ephemeral", "impact": "negative"},
    "bank.debt": {"kind": "single", "visibility": "ephemeral", "impact": "negative"},
    # Misc messages
    "misc.help": {"kind": "single", "visibility": "ephemeral", "impact": "neutral"},
}

# Bot instance (set by main.py)
bot = None

def set_bot(bot_instance):
    """Set the bot instance for this module"""
    global bot
    bot = bot_instance

async def check_admin_command_permissions(interaction_or_ctx) -> bool:
    """Check if admin command can be used. Works with both Interaction and Context."""
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
    
    # Use configured logs channel (C2: restrict to logs channel only)
    from core.db import get_logs_channel_id
    logs_channel_id = await get_logs_channel_id(guild_id)
    
    if channel_id != logs_channel_id:
        if is_interaction:
            await interaction_or_ctx.response.send_message(f"This command can only be used in <#{logs_channel_id}>.", ephemeral=True, delete_after=5)
        else:
            await interaction_or_ctx.send(f"This command can only be used in <#{logs_channel_id}>.", delete_after=5)
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
    
    # Block Bad Pup users from using commands (even admins)
    from systems.onboarding import has_bad_pup_role
    if has_bad_pup_role(user):
        if is_interaction:
            await interaction_or_ctx.response.send_message("You cannot use commands while you have the Bad Pup role. Type the required submission text to redeem yourself.", ephemeral=True, delete_after=10)
        else:
            await interaction_or_ctx.send("You cannot use commands while you have the Bad Pup role. Type the required submission text to redeem yourself.", delete_after=10)
        return False
    
    return True

def register_commands(bot_instance):
    """Register all admin commands with the bot"""
    global bot
    bot = bot_instance
    
    # Check if commands are already registered to avoid duplicate registration
    registered_names = {cmd.name for cmd in bot.tree.get_commands()}
    
    if "config" in registered_names:
        return  # Commands already registered, skip
    
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
    
    # Legacy event commands removed - event system disabled
    
    # /testembeds command deleted per B1
    
    @bot.tree.command(name="throne", description="Send a Throne message with quote variations. Admin only.")
    async def throne(interaction: discord.Interaction):
        """Send a Throne message with quote variations."""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        from systems.tasks import send_throne_announcement
        success = await send_throne_announcement(interaction.guild)
        if success:
            await interaction.response.send_message("✅ Throne message sent!", ephemeral=True, delete_after=5)
        else:
            await interaction.response.send_message(f"Failed to send Throne message. Check bot logs.", ephemeral=True, delete_after=10)
    
    @bot.tree.command(name="killevent", description="Kill any currently running event and set a 30-minute cooldown. Admin only.")
    async def killevent(interaction: discord.Interaction):
        """Kill any currently running event and set a 30-minute cooldown."""
        import systems.events as events
        
        if not await check_admin_command_permissions(interaction):
            return
        
        if not events.active_event:
            await interaction.response.send_message("No event is currently running.", ephemeral=True, delete_after=5)
            return
        
        # Clear active event first (so clear_event_roles will work)
        events.active_event = None
        
        # Clear event roles
        await clear_event_roles()
        
        # Set 30-minute cooldown
        events.event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=1800)
        
        await interaction.response.send_message("✅ Event killed. 30-minute cooldown activated.", ephemeral=True, delete_after=10)
        print(f"Event killed by {interaction.user.name}. Cooldown until {events.event_cooldown_until.strftime('%H:%M:%S UTC')}")
    
    @bot.tree.command(name="sync", description="Sync slash commands. Admin only.")
    @app_commands.describe(clear_commands="Dangerous: Clear all commands before syncing (default: false)")
    async def sync_commands(interaction: discord.Interaction, clear_commands: bool = False):
        """Sync slash commands (Admin only)"""
        if not await check_admin_command_permissions(interaction):
            return
        
        from core.config import ALLOWED_GUILDS
        
        # Count commands before sync
        commands_before = list(bot.tree.get_commands())
        commands_count_before = len(commands_before)
        
        sync_results = {}
        
        # Optional: Clear commands (dangerous)
        if clear_commands:
            try:
                # Clear global commands
                bot.tree.clear_commands(guild=None)
                # Clear per-guild commands
                for guild_id in ALLOWED_GUILDS:
                    bot.tree.clear_commands(guild=discord.Object(id=guild_id))
                sync_results["cleared"] = True
            except Exception as e:
                sync_results["cleared"] = f"ERROR: {e}"
                await interaction.response.send_message(f"❌ Failed to clear commands: {e}", ephemeral=True)
                return
        
        # Global sync
        try:
            synced_global = await bot.tree.sync()
            sync_results["global"] = len(synced_global)
        except Exception as e:
            sync_results["global"] = f"ERROR: {e}"
        
        # Per-guild sync for faster propagation
        for guild_id in ALLOWED_GUILDS:
            try:
                synced_guild = await bot.tree.sync(guild=discord.Object(id=guild_id))
                sync_results[f"guild_{guild_id}"] = len(synced_guild)
            except Exception as e:
                sync_results[f"guild_{guild_id}"] = f"ERROR: {e}"
        
        # Build response embed
        embed = discord.Embed(
            title="🔄 Command Sync Results",
            color=0x4ec200 if all(isinstance(v, int) for v in sync_results.values() if v != True) else 0xff000d
        )
        
        embed.add_field(name="Commands Before Sync", value=str(commands_count_before), inline=True)
        
        if clear_commands:
            embed.add_field(name="Commands Cleared", value="✅ Yes" if sync_results.get("cleared") == True else f"❌ {sync_results.get('cleared', 'Unknown')}", inline=True)
        
        embed.add_field(name="Global Sync", value=str(sync_results.get("global", "N/A")), inline=True)
        
        for guild_id in ALLOWED_GUILDS:
            key = f"guild_{guild_id}"
            if key in sync_results:
                embed.add_field(name=f"Guild {guild_id}", value=str(sync_results[key]), inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        print(f"✅ Manual sync by {interaction.user.name}: {sync_results}")
    
    # Legacy Level/XP admin commands removed - V3 progression system only
    
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
        
        uk_tz = get_timezone("Europe/London")
        if uk_tz is None:
            await interaction.response.send_message("Timezone support not available. Cannot calculate schedule.", ephemeral=True)
            return
        
        tier1_times = []
        for hour, minute in EVENT_SCHEDULE[1]:
            timestamp = get_next_scheduled_time(hour, minute)
            tier1_times.append(f"<t:{timestamp}:F> (<t:{timestamp}:R>)")
        embed.add_field(
            name="🎯 Tier 1 Events",
            value="\n".join(tier1_times) or "No scheduled times",
            inline=False
        )
        
        tier2_times = []
        for hour, minute in EVENT_SCHEDULE[2]:
            timestamp = get_next_scheduled_time(hour, minute)
            tier2_times.append(f"<t:{timestamp}:F> (<t:{timestamp}:R>)")
        embed.add_field(
            name="🎯 Tier 2 Events",
            value="\n".join(tier2_times) or "No scheduled times",
            inline=False
        )
        
        tier3_times = []
        for hour, minute in EVENT_SCHEDULE[3]:
            timestamp = get_next_scheduled_time(hour, minute)
            tier3_times.append(f"<t:{timestamp}:F> (<t:{timestamp}:R>)")
        embed.add_field(
            name="🎯 Tier 3 Events",
            value="\n".join(tier3_times) or "No scheduled times",
            inline=False
        )
        
        throne_times = []
        for hour in [7, 19]:
            timestamp = get_next_scheduled_time(hour, 0)
            throne_times.append(f"<t:{timestamp}:F> (<t:{timestamp}:R>)")
        embed.add_field(
            name="👑 Throne Messages",
            value="\n".join(throne_times) or "No scheduled times",
            inline=False
        )
        
        slots_timestamp = get_next_scheduled_time(20, 0)
        embed.add_field(
            name="🎰 Slots Announcement",
            value=f"<t:{slots_timestamp}:F> (<t:{slots_timestamp}:R>)",
            inline=False
        )
        
        import systems.events as events
        if events.active_event:
            event_type = events.active_event.get("type", "Unknown")
            embed.add_field(
                name="⚡ Current Status",
                value=f"Event {event_type} is currently active",
                inline=False
            )
        elif events.event_cooldown_until and datetime.datetime.now(datetime.UTC) < events.event_cooldown_until:
            cooldown_timestamp = int(events.event_cooldown_until.timestamp())
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
    
    # Legacy stopevents/startevents commands removed - event system disabled
    
    # /askgifts command deleted per D5
    
    # Main configure command - interactive menu system
    @bot.tree.command(name="configure", description="Configure bot settings with interactive menu. Admin only.")
    async def configure(interaction: discord.Interaction):
        """Main configure command with interactive menu"""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="⚙️ Configuration Menu",
            description="Select a category to configure:",
            color=0x4ec200
        )
        
        view = ConfigureCategoryView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    class ConfigureCategoryView(discord.ui.View):
        """Main category selection view"""
        def __init__(self):
            super().__init__(timeout=300)
        
        @discord.ui.select(
            placeholder="Select a configuration category...",
            options=[
                discord.SelectOption(label="📝 Onboarding", value="onboarding", description="Configure onboarding channel and roles"),
                discord.SelectOption(label="🎭 Roles", value="roles", description="Configure role selection messages"),
                discord.SelectOption(label="👋 Introductions", value="introductions", description="Configure introductions channel"),
                discord.SelectOption(label="🎰 Casino", value="casino", description="Configure casino channel"),
                discord.SelectOption(label="📢 Announcements", value="announcements", description="Configure announcements channel"),
                discord.SelectOption(label="📋 Logs", value="logs", description="Configure logs channel (admin commands)"),
                discord.SelectOption(label="💬 User Commands", value="usercommands", description="Configure user commands channels"),
                discord.SelectOption(label="📦 Orders", value="orders", description="Configure orders system"),
            ]
        )
        async def category_select(self, select_interaction: discord.Interaction, select: discord.ui.Select):
            category = select.values[0]
            
            if category == "onboarding":
                embed = discord.Embed(
                    title="📝 Onboarding Configuration",
                    description="Select what to configure:",
                    color=0x4ec200
                )
                view = OnboardingConfigView()
                await select_interaction.response.edit_message(embed=embed, view=view)
            
            elif category == "roles":
                embed = discord.Embed(
                    title="🎭 Roles Configuration",
                    description="Select an action:",
                    color=0x4ec200
                )
                view = RolesConfigView()
                await select_interaction.response.edit_message(embed=embed, view=view)
            
            elif category == "introductions":
                embed = discord.Embed(
                    title="👋 Introductions Configuration",
                    description="Select an action:",
                    color=0x4ec200
                )
                view = ChannelConfigView("introductions", "Introductions channel")
                await select_interaction.response.edit_message(embed=embed, view=view)
            
            elif category == "casino":
                embed = discord.Embed(
                    title="🎰 Casino Configuration",
                    description="Select an action:",
                    color=0x4ec200
                )
                view = ChannelConfigView("casino", "Casino channel")
                await select_interaction.response.edit_message(embed=embed, view=view)
            
            elif category == "announcements":
                embed = discord.Embed(
                    title="📢 Announcements Configuration",
                    description="Select an action:",
                    color=0x4ec200
                )
                view = ChannelConfigView("announcements", "Announcements channel")
                await select_interaction.response.edit_message(embed=embed, view=view)
            
            elif category == "logs":
                embed = discord.Embed(
                    title="📋 Logs Configuration",
                    description="Select an action:",
                    color=0x4ec200
                )
                view = ChannelConfigView("logs", "Logs channel (admin commands)")
                await select_interaction.response.edit_message(embed=embed, view=view)
            
            elif category == "usercommands":
                embed = discord.Embed(
                    title="💬 User Commands Configuration",
                    description="Select an action:",
                    color=0x4ec200
                )
                view = UserCommandsConfigView()
                await select_interaction.response.edit_message(embed=embed, view=view)
            
            elif category == "orders":
                embed = discord.Embed(
                    title="📦 Orders Configuration",
                    description="Select an action:",
                    color=0x4ec200
                )
                view = OrdersConfigView()
                await select_interaction.response.edit_message(embed=embed, view=view)
    
    class OnboardingConfigView(discord.ui.View):
        """Onboarding configuration view"""
        def __init__(self):
            super().__init__(timeout=300)
        
        @discord.ui.select(
            placeholder="Select what to configure...",
            options=[
                discord.SelectOption(label="📝 Channel", value="channel", description="Set onboarding channel"),
                discord.SelectOption(label="🔐 Unverified Role", value="unverified", description="Set Unverified role"),
                discord.SelectOption(label="✅ Verified Role", value="verified", description="Set Verified role"),
                discord.SelectOption(label="🐾 Bad Pup Role", value="badpup", description="Set Bad Pup role"),
            ]
        )
        async def onboarding_select(self, select_interaction: discord.Interaction, select: discord.ui.Select):
            action = select.values[0]
            
            if action == "channel":
                embed = discord.Embed(
                    title="📝 Set Onboarding Channel",
                    description="Select the channel to use for onboarding:",
                    color=0x4ec200
                )
                view = ChannelSelectView("onboarding_channel", "onboarding")
                await select_interaction.response.edit_message(embed=embed, view=view)
            else:
                role_name_map = {
                    "unverified": "Unverified",
                    "verified": "Verified",
                    "badpup": "Bad Pup"
                }
                role_name = role_name_map[action]
                embed = discord.Embed(
                    title=f"🔐 Set {role_name} Role",
                    description=f"Select the role to use for {role_name}:",
                    color=0x4ec200
                )
                view = RoleSelectView("onboarding_role", role_name)
                await select_interaction.response.edit_message(embed=embed, view=view)
        
        @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title="⚙️ Configuration Menu",
                description="Select a category to configure:",
                color=0x4ec200
            )
            view = ConfigureCategoryView()
            await interaction.response.edit_message(embed=embed, view=view)
    
    class RolesConfigView(discord.ui.View):
        """Roles configuration view"""
        def __init__(self):
            super().__init__(timeout=300)
        
        @discord.ui.select(
            placeholder="Select a role message type...",
            options=[
                discord.SelectOption(label="Pronouns", value="pronouns", description="Configure pronouns selection message"),
                discord.SelectOption(label="Petnames", value="petnames", description="Configure petnames selection message"),
                discord.SelectOption(label="Region", value="region", description="Configure region selection message"),
                discord.SelectOption(label="Preferences", value="preferences", description="Configure preferences selection message"),
            ]
        )
        async def role_type_select(self, select_interaction: discord.Interaction, select: discord.ui.Select):
            message_type = select.values[0]
            embed = discord.Embed(
                title=f"🎭 Configure {message_type.capitalize()} Role Message",
                description="Select an action:",
                color=0x4ec200
            )
            view = RoleMessageActionView(message_type)
            await select_interaction.response.edit_message(embed=embed, view=view)
        
        @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title="⚙️ Configuration Menu",
                description="Select a category to configure:",
                color=0x4ec200
            )
            view = ConfigureCategoryView()
            await interaction.response.edit_message(embed=embed, view=view)
    
    class ChannelConfigView(discord.ui.View):
        """Generic channel configuration view"""
        def __init__(self, config_type: str, display_name: str):
            super().__init__(timeout=300)
            self.config_type = config_type
            self.display_name = display_name
        
        @discord.ui.select(
            placeholder="Select an action...",
            options=[
                discord.SelectOption(label="Set Channel", value="set", description=f"Set {display_name.lower()}"),
                discord.SelectOption(label="Show Current", value="show", description="Show current configuration"),
            ]
        )
        async def action_select(self, select_interaction: discord.Interaction, select: discord.ui.Select):
            action = select.values[0]
            
            if action == "set":
                embed = discord.Embed(
                    title=f"⚙️ Set {self.display_name}",
                    description=f"Select the channel to use for {self.display_name.lower()}:",
                    color=0x4ec200
                )
                view = ChannelSelectView(f"{self.config_type}_channel", self.config_type)
                await select_interaction.response.edit_message(embed=embed, view=view)
            else:  # show
                await select_interaction.response.defer(ephemeral=True)
                await self.show_config(select_interaction)
        
        async def show_config(self, interaction: discord.Interaction):
            """Show current configuration"""
            from core.db import get_casino_channel_id, get_announcements_channel_id, get_logs_channel_id, get_usercommands_channel_ids, fetchone
            from core.config import CASINO_CHANNEL_ID, EVENT_CHANNEL_ID, ADMIN_COMMAND_CHANNEL_ID, USER_COMMAND_CHANNEL_ID
            
            channel_id = None
            default_id = None
            
            if self.config_type == "casino":
                channel_id = await get_casino_channel_id(interaction.guild.id)
                default_id = CASINO_CHANNEL_ID
            elif self.config_type == "announcements":
                channel_id = await get_announcements_channel_id(interaction.guild.id)
                default_id = EVENT_CHANNEL_ID
            elif self.config_type == "logs":
                channel_id = await get_logs_channel_id(interaction.guild.id)
                default_id = ADMIN_COMMAND_CHANNEL_ID
            elif self.config_type == "introductions":
                row = await fetchone(
                    "SELECT channel_id FROM introductions_config WHERE guild_id = ?",
                    (interaction.guild.id,)
                )
                channel_id = row["channel_id"] if row else None
            
            channel = bot.get_channel(channel_id) if channel_id else None
            
            if channel:
                embed = discord.Embed(
                    title=f"📋 {self.display_name} Configuration",
                    description=f"Current channel: {channel.mention}",
                    color=0x4ec200
                )
            else:
                if default_id:
                    default_channel = bot.get_channel(default_id)
                    embed = discord.Embed(
                        title=f"📋 {self.display_name} Configuration",
                        description=f"No custom channel configured.\nUsing default: {default_channel.mention if default_channel else f'<#{default_id}>'}",
                        color=0xff000d
                    )
                else:
                    embed = discord.Embed(
                        title=f"📋 {self.display_name} Configuration",
                        description="No channel configured.",
                        color=0xff000d
                    )
            
            view = ChannelConfigView(self.config_type, self.display_name)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title="⚙️ Configuration Menu",
                description="Select a category to configure:",
                color=0x4ec200
            )
            view = ConfigureCategoryView()
            await interaction.response.edit_message(embed=embed, view=view)
    
    class UserCommandsConfigView(discord.ui.View):
        """User commands configuration view"""
        def __init__(self):
            super().__init__(timeout=300)
        
        @discord.ui.select(
            placeholder="Select an action...",
            options=[
                discord.SelectOption(label="Set Channels", value="set", description="Set user commands channels"),
                discord.SelectOption(label="Show Current", value="show", description="Show current channels"),
            ]
        )
        async def action_select(self, select_interaction: discord.Interaction, select: discord.ui.Select):
            action = select.values[0]
            
            if action == "set":
                embed = discord.Embed(
                    title="💬 Set User Commands Channels",
                    description="**Note:** This will replace all current channels.\n\nPlease type the channel mentions or IDs (comma-separated) in a message, then click the button below.",
                    color=0x4ec200
                )
                view = UserCommandsSetView()
                await select_interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                await select_interaction.delete_original_response()
            else:  # show
                await select_interaction.response.defer(ephemeral=True)
                from core.db import get_usercommands_channel_ids
                from core.config import USER_COMMAND_CHANNEL_ID
                
                channel_ids = await get_usercommands_channel_ids(select_interaction.guild.id)
                channel_mentions = []
                for channel_id in channel_ids:
                    channel = bot.get_channel(channel_id) or select_interaction.guild.get_channel(channel_id)
                    if channel:
                        channel_mentions.append(channel.mention)
                    else:
                        channel_mentions.append(f"<#{channel_id}> (not found)")
                
                if channel_mentions:
                    embed = discord.Embed(
                        title="📋 User Commands Configuration",
                        description=f"Current channels: {' '.join(channel_mentions)}",
                        color=0x4ec200
                    )
                else:
                    default_channel = bot.get_channel(USER_COMMAND_CHANNEL_ID)
                    embed = discord.Embed(
                        title="📋 User Commands Configuration",
                        description=f"Using default: {default_channel.mention if default_channel else f'<#{USER_COMMAND_CHANNEL_ID}>'}",
                        color=0xff000d
                    )
                
                view = UserCommandsConfigView()
                await select_interaction.followup.send(embed=embed, view=view, ephemeral=True)
        
        @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title="⚙️ Configuration Menu",
                description="Select a category to configure:",
                color=0x4ec200
            )
            view = ConfigureCategoryView()
            await interaction.response.edit_message(embed=embed, view=view)
    
    class UserCommandsSetView(discord.ui.View):
        """View for setting user commands channels via modal"""
        @discord.ui.button(label="Open Channel Input", style=discord.ButtonStyle.primary)
        async def open_modal_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            modal = UserCommandsChannelModal()
            await interaction.response.send_modal(modal)
    
    class UserCommandsChannelModal(discord.ui.Modal, title="Set User Commands Channels"):
        """Modal for entering channel IDs/mentions"""
        channels_input = discord.ui.TextInput(
            label="Channel Mentions or IDs",
            placeholder="<#123456789>, <#987654321> or 123456789, 987654321",
            required=True,
            max_length=500
        )
        
        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            
            # Parse channel mentions/IDs
            channels_text = self.channels_input.value
            channel_ids = []
            parts = [p.strip() for p in channels_text.split(",")]
            
            for part in parts:
                # Try to extract channel ID from mention (<#123456789>)
                if part.startswith("<#") and part.endswith(">"):
                    try:
                        channel_id = int(part[2:-1])
                        channel_ids.append(channel_id)
                    except ValueError:
                        pass
                else:
                    # Try as direct ID
                    try:
                        channel_id = int(part)
                        channel_ids.append(channel_id)
                    except ValueError:
                        pass
            
            if not channel_ids:
                await interaction.followup.send("No valid channel IDs found. Please provide channel mentions or IDs (comma-separated).", ephemeral=True)
                return
            
            from core.db import execute, _now_iso
            now = _now_iso()
            guild_id = interaction.guild.id
            
            # Remove existing channels for this guild
            await execute(
                "DELETE FROM usercommands_channel_config WHERE guild_id = ?",
                (guild_id,)
            )
            
            # Add new channels
            for channel_id in channel_ids:
                channel = bot.get_channel(channel_id) or interaction.guild.get_channel(channel_id)
                if channel:
                    await execute(
                        """INSERT INTO usercommands_channel_config (guild_id, channel_id, updated_at)
                           VALUES (?, ?, ?)""",
                        (guild_id, channel_id, now)
                    )
            
            channel_mentions = " ".join(f"<#{cid}>" for cid in channel_ids if bot.get_channel(cid) or interaction.guild.get_channel(cid))
            embed = discord.Embed(
                title="✅ Configuration Updated",
                description=f"Usercommands channels set to: {channel_mentions}",
                color=0x4ec200
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    class OrdersConfigView(discord.ui.View):
        """Orders configuration view"""
        def __init__(self):
            super().__init__(timeout=300)
        
        @discord.ui.select(
            placeholder="Select an action...",
            options=[
                discord.SelectOption(label="Announcements Channel", value="announcements", description="Set channel for new orders announcements"),
            ]
        )
        async def action_select(self, select_interaction: discord.Interaction, select: discord.ui.Select):
            action = select.values[0]
            
            if action == "announcements":
                embed = discord.Embed(
                    title="📦 Set Orders Announcements Channel",
                    description="Select the channel to use for new orders announcements:",
                    color=0x4ec200
                )
                view = ChannelSelectView("orders_announcements", "orders")
                await select_interaction.response.edit_message(embed=embed, view=view)
        
        @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title="⚙️ Configuration Menu",
                description="Select a category to configure:",
                color=0x4ec200
            )
            view = ConfigureCategoryView()
            await interaction.response.edit_message(embed=embed, view=view)
    
    class ChannelSelectView(discord.ui.View):
        """Channel selector view"""
        def __init__(self, action_type: str, config_category: str):
            super().__init__(timeout=300)
            self.action_type = action_type
            self.config_category = config_category
        
        @discord.ui.channel_select(
            placeholder="Select a channel...",
            channel_types=[discord.ChannelType.text]
        )
        async def channel_select(self, select_interaction: discord.Interaction, select: discord.ui.ChannelSelect):
            channel = select.values[0]
            await select_interaction.response.defer(ephemeral=True)
            
            if self.action_type == "onboarding_channel":
                from systems.onboarding import set_onboarding_channel
                set_onboarding_channel(channel.id)
                embed = discord.Embed(
                    title="✅ Configuration Updated",
                    description=f"Onboarding channel set to {channel.mention}",
                    color=0x4ec200
                )
            
            elif self.config_category == "casino":
                from core.db import execute, _now_iso
                now = _now_iso()
                await execute(
                    """INSERT OR REPLACE INTO casino_channel_config (guild_id, channel_id, updated_at)
                       VALUES (?, ?, ?)""",
                    (select_interaction.guild.id, channel.id, now)
                )
                embed = discord.Embed(
                    title="✅ Configuration Updated",
                    description=f"Casino channel set to {channel.mention}",
                    color=0x4ec200
                )
            
            elif self.config_category == "announcements":
                from core.db import execute, _now_iso
                now = _now_iso()
                await execute(
                    """INSERT OR REPLACE INTO announcements_channel_config (guild_id, channel_id, updated_at)
                       VALUES (?, ?, ?)""",
                    (select_interaction.guild.id, channel.id, now)
                )
                embed = discord.Embed(
                    title="✅ Configuration Updated",
                    description=f"Announcements channel set to {channel.mention}",
                    color=0x4ec200
                )
            
            elif self.config_category == "logs":
                from core.db import execute, _now_iso
                now = _now_iso()
                await execute(
                    """INSERT OR REPLACE INTO logs_channel_config (guild_id, channel_id, updated_at)
                       VALUES (?, ?, ?)""",
                    (select_interaction.guild.id, channel.id, now)
                )
                embed = discord.Embed(
                    title="✅ Configuration Updated",
                    description=f"Logs channel set to {channel.mention}\n\nAdmin commands can now only be used in this channel.",
                    color=0x4ec200
                )
            
            elif self.config_category == "introductions":
                from core.db import execute
                now = datetime.datetime.now(datetime.UTC).isoformat()
                await execute(
                    """INSERT OR REPLACE INTO introductions_config (guild_id, channel_id, updated_at)
                       VALUES (?, ?, ?)""",
                    (select_interaction.guild.id, channel.id, now)
                )
                embed = discord.Embed(
                    title="✅ Configuration Updated",
                    description=f"Introductions channel set to {channel.mention}",
                    color=0x4ec200
                )
            
            elif self.action_type == "orders_announcements":
                from core.db import execute
                now = datetime.datetime.now(datetime.UTC).isoformat()
                await execute(
                    """INSERT OR REPLACE INTO orders_announcement_config (guild_id, channel_id, updated_at)
                       VALUES (?, ?, ?)""",
                    (select_interaction.guild.id, channel.id, now)
                )
                embed = discord.Embed(
                    title="✅ Configuration Updated",
                    description=f"Orders announcements channel set to {channel.mention}",
                    color=0x4ec200
                )
            
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Unknown configuration type.",
                    color=0xff000d
                )
            
            await select_interaction.followup.send(embed=embed, ephemeral=True)
            
            # Return to main menu
            main_embed = discord.Embed(
                title="⚙️ Configuration Menu",
                description="Select a category to configure:",
                color=0x4ec200
            )
            view = ConfigureCategoryView()
            await select_interaction.followup.send(embed=main_embed, view=view, ephemeral=True)
        
        @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title="⚙️ Configuration Menu",
                description="Select a category to configure:",
                color=0x4ec200
            )
            view = ConfigureCategoryView()
            await interaction.response.edit_message(embed=embed, view=view)
    
    class RoleSelectView(discord.ui.View):
        """Role selector view"""
        def __init__(self, action_type: str, role_name: str):
            super().__init__(timeout=300)
            self.action_type = action_type
            self.role_name = role_name
        
        @discord.ui.role_select(
            placeholder="Select a role..."
        )
        async def role_select(self, select_interaction: discord.Interaction, select: discord.ui.RoleSelect):
            role = select.values[0]
            await select_interaction.response.defer(ephemeral=True)
            
            from systems.onboarding import set_role
            set_role(self.role_name, role.id)
            
            embed = discord.Embed(
                title="✅ Configuration Updated",
                description=f"Onboarding role '{self.role_name}' set to {role.mention}",
                color=0x4ec200
            )
            await select_interaction.followup.send(embed=embed, ephemeral=True)
            
            # Return to main menu
            main_embed = discord.Embed(
                title="⚙️ Configuration Menu",
                description="Select a category to configure:",
                color=0x4ec200
            )
            view = ConfigureCategoryView()
            await select_interaction.followup.send(embed=main_embed, view=view, ephemeral=True)
        
        @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title="⚙️ Configuration Menu",
                description="Select a category to configure:",
                color=0x4ec200
            )
            view = ConfigureCategoryView()
            await interaction.response.edit_message(embed=embed, view=view)
    
    class RoleMessageActionView(discord.ui.View):
        """View for role message actions (send/update)"""
        def __init__(self, message_type: str):
            super().__init__(timeout=300)
            self.message_type = message_type
        
        @discord.ui.select(
            placeholder="Select an action...",
            options=[
                discord.SelectOption(label="Send New Message", value="send", description="Send a new role selection message"),
                discord.SelectOption(label="Update Existing", value="update", description="Update existing role message"),
            ]
        )
        async def action_select(self, select_interaction: discord.Interaction, select: discord.ui.Select):
            action = select.values[0]
            
            if action == "send":
                embed = discord.Embed(
                    title=f"🎭 Send {self.message_type.capitalize()} Role Message",
                    description="Select the channel to send the message to:",
                    color=0x4ec200
                )
                view = RoleMessageChannelView(self.message_type, "send")
                await select_interaction.response.edit_message(embed=embed, view=view)
            else:  # update
                await select_interaction.response.defer(ephemeral=True)
                # Check if message exists
                from core.db import fetchone
                # Get roles config - function is defined in this module
                config = await get_roles_config(select_interaction.guild.id, self.message_type)
                if not config:
                    await select_interaction.followup.send(f"❌ No {self.message_type} role message found. Please send one first.", ephemeral=True)
                    return
                
                # Fetch and update existing message
                try:
                    channel = bot.get_channel(config["channel_id"])
                    if not channel:
                        await select_interaction.followup.send(f"❌ Channel not found. Message may have been deleted.", ephemeral=True)
                        return
                    
                    existing_msg = await channel.fetch_message(config["message_id"])
                    
                    # Build embed and view
                    embed_builder = {
                        "pronouns": build_pronouns_embed,
                        "petnames": build_petnames_embed,
                        "region": build_region_embed,
                        "preferences": build_preferences_embed,
                    }
                    view_builder = {
                        "pronouns": PronounsSelectView,
                        "petnames": PetnamesSelectView,
                        "region": RegionSelectView,
                        "preferences": PreferencesSelectView,
                    }
                    
                    embed = embed_builder[self.message_type]()
                    view = view_builder[self.message_type]()
                    
                    await existing_msg.edit(embed=embed, view=view)
                    await save_roles_config(select_interaction.guild.id, self.message_type, config["channel_id"], config["message_id"])
                    await select_interaction.followup.send(f"✅ Roles message for {self.message_type} has been updated.", ephemeral=True)
                except discord.NotFound:
                    await select_interaction.followup.send(f"❌ Message not found. It may have been deleted. Use Send New Message to create a new one.", ephemeral=True)
                except Exception as e:
                    await select_interaction.followup.send(f"❌ Failed to edit message: {e}", ephemeral=True)
        
        @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title="🎭 Roles Configuration",
                description="Select a role message type:",
                color=0x4ec200
            )
            view = RolesConfigView()
            await interaction.response.edit_message(embed=embed, view=view)
    
    class RoleMessageChannelView(discord.ui.View):
        """View for selecting channel for role message"""
        def __init__(self, message_type: str, action: str):
            super().__init__(timeout=300)
            self.message_type = message_type
            self.action = action
        
        @discord.ui.channel_select(
            placeholder="Select a channel...",
            channel_types=[discord.ChannelType.text]
        )
        async def channel_select(self, select_interaction: discord.Interaction, select: discord.ui.ChannelSelect):
            channel = select.values[0]
            await select_interaction.response.defer(ephemeral=True)
            
            # Build embed and view
            embed_builder = {
                "pronouns": build_pronouns_embed,
                "petnames": build_petnames_embed,
                "region": build_region_embed,
                "preferences": build_preferences_embed,
            }
            view_builder = {
                "pronouns": PronounsSelectView,
                "petnames": PetnamesSelectView,
                "region": RegionSelectView,
                "preferences": PreferencesSelectView,
            }
            
            embed = embed_builder[self.message_type]()
            view = view_builder[self.message_type]()
            
            message = await channel.send(embed=embed, view=view)
            # Save roles config - function is defined in this module
            await save_roles_config(select_interaction.guild.id, self.message_type, channel.id, message.id)
            
            result_embed = discord.Embed(
                title="✅ Message Sent",
                description=f"Role selection message for {self.message_type} sent to {channel.mention}",
                color=0x4ec200
            )
            await select_interaction.followup.send(embed=result_embed, ephemeral=True)
            
            # Return to main menu
            main_embed = discord.Embed(
                title="⚙️ Configuration Menu",
                description="Select a category to configure:",
                color=0x4ec200
            )
            view = ConfigureCategoryView()
            await select_interaction.followup.send(embed=main_embed, view=view, ephemeral=True)
        
        @discord.ui.button(label="⬅️ Back", style=discord.ButtonStyle.secondary)
        async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title=f"🎭 Configure {self.message_type.capitalize()} Role Message",
                description="Select an action:",
                color=0x4ec200
            )
            view = RoleMessageActionView(self.message_type)
            await interaction.response.edit_message(embed=embed, view=view)
    
    # Legacy subcommand groups - kept for reference but not registered
    # Define dummy group so old subcommand definitions don't cause errors
    _dummy_configure_group = app_commands.Group(name="_dummy_configure", description="[NOT REGISTERED]")
    configure_group = _dummy_configure_group  # Old subcommands reference this but it's never added to tree
    @app_commands.choices(config_type=[
        app_commands.Choice(name="channel", value="channel"),
        app_commands.Choice(name="role", value="role")
    ])
    @app_commands.describe(
        config_type="Type of configuration",
        name="For channel: channel name/ID. For role: role type (Unverified/Verified/Bad Pup)",
        serverrole="For role: the server role to use"
    )
    async def configure_onboarding(interaction: discord.Interaction, config_type: str, name: str, serverrole: discord.Role = None):
        """Configure onboarding channel or roles - always responds within 3s (C3)"""
        # Always defer to avoid timeout (C3)
        await interaction.response.defer(ephemeral=True)
        
        if not await check_admin_command_permissions(interaction):
            await interaction.followup.send("Permission check failed.", ephemeral=True)
            return
        
        from systems.onboarding import set_onboarding_channel, set_role
        
        config_type_value = config_type
        
        if config_type_value == "channel":
            # Try to parse as channel ID first, then try to find by name
            channel = None
            try:
                channel_id = int(name)
                channel = bot.get_channel(channel_id) or interaction.guild.get_channel(channel_id)
            except ValueError:
                # Try to find by name
                for ch in interaction.guild.channels:
                    if ch.name.lower() == name.lower():
                        channel = ch
                        break
            
            if not channel:
                await interaction.followup.send(f"Channel '{name}' not found. Please provide a channel mention, ID, or name.", ephemeral=True, delete_after=5)
                return
            
            set_onboarding_channel(channel.id)
            embed = discord.Embed(
                title="✅ Configuration Updated",
                description=f"Onboarding channel set to {channel.mention}",
                color=0x4ec200
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        elif config_type_value == "role":
            valid_roles = ["Unverified", "Verified", "Bad Pup"]
            if name not in valid_roles:
                await interaction.followup.send(f"Invalid role type. Must be one of: {', '.join(valid_roles)}", ephemeral=True, delete_after=5)
                return
            
            if not serverrole:
                await interaction.followup.send("Please provide a server role.", ephemeral=True, delete_after=5)
                return
            
            set_role(name, serverrole.id)
            embed = discord.Embed(
                title="✅ Configuration Updated",
                description=f"Onboarding role '{name}' set to {serverrole.mention}",
                color=0x4ec200
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Roles configuration embed builders
    def build_pronouns_embed() -> discord.Embed:
        """Build pronouns selection embed"""
        embed = discord.Embed(
            description="Identification required.\n\nSelect the terms Isla will use to address you.",
            color=0x58585f
        )
        embed.set_author(
            name="✧ TRANSMISSION ✧",
            icon_url="https://i.imgur.com/irmCXhw.gif"
        )
        return embed
    
    def build_petnames_embed() -> discord.Embed:
        """Build petnames selection embed"""
        embed = discord.Embed(
            description="Classification pending.\n\nChoose how you will be recognized.",
            color=0x58585f
        )
        embed.set_author(
            name="✧ TRANSMISSION ✧",
            icon_url="https://i.imgur.com/irmCXhw.gif"
        )
        return embed
    
    def build_region_embed() -> discord.Embed:
        """Build region selection embed"""
        embed = discord.Embed(
            description="Isla observes across many regions.\n\nIdentify where you primarily exist.",
            color=0x58585f
        )
        embed.set_author(
            name="✧ TRANSMISSION ✧",
            icon_url="https://i.imgur.com/irmCXhw.gif"
        )
        return embed
    
    def build_preferences_embed() -> discord.Embed:
        """Build preferences selection embed"""
        embed = discord.Embed(
            description="Isla adapts to what you respond to.\n\nTell her what kind of control speaks to you.",
            color=0x58585f
        )
        embed.set_author(
            name="✧ TRANSMISSION ✧",
            icon_url=HEART_GIF
        )
        return embed
    
    # Roles selection menu views
    class PronounsSelectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            
        @discord.ui.select(
            placeholder="How should Isla refer to you?",
            options=[
                discord.SelectOption(
                    label="She / Her",
                    value="she_her",
                    description="You will be addressed using she/her."
                ),
                discord.SelectOption(
                    label="They / Them",
                    value="they_them",
                    description="You will be addressed using they/them."
                ),
                discord.SelectOption(
                    label="He / Him",
                    value="he_him",
                    description="You will be addressed using he/him."
                ),
                discord.SelectOption(
                    label="Prefer not to say",
                    value="none",
                    description="Isla will avoid pronouns unless necessary."
                ),
            ]
        )
        async def pronouns_select(self, interaction: discord.Interaction, select: discord.ui.Select):
            # Handle pronoun selection (role assignment logic would go here)
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(f"You selected: {select.values[0]}", ephemeral=True)
    
    class PetnamesSelectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            
        @discord.ui.select(
            placeholder="Choose how you wish to be seen.",
            options=[
                discord.SelectOption(
                    label="Kitten",
                    value="kitten",
                    description="Curious. Soft-spoken. Attentive to Isla's presence."
                ),
                discord.SelectOption(
                    label="Puppy",
                    value="puppy",
                    description="Eager. Loyal. Thrives on approval and direction."
                ),
                discord.SelectOption(
                    label="Pet",
                    value="pet",
                    description="Neutral. Observant. Exists comfortably under Isla's watch."
                ),
                discord.SelectOption(
                    label="Stray",
                    value="stray",
                    description="Undecided. Watching from the edges—for now."
                ),
            ]
        )
        async def petnames_select(self, interaction: discord.Interaction, select: discord.ui.Select):
            # Handle petname selection (role assignment logic would go here)
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(f"You selected: {select.values[0]}", ephemeral=True)
    
    class RegionSelectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            
        @discord.ui.select(
            placeholder="Select your primary region.",
            options=[
                discord.SelectOption(
                    label="EMEA",
                    value="emea",
                    description="Europe, Middle East & Africa."
                ),
                discord.SelectOption(
                    label="APAC",
                    value="apac",
                    description="Asia–Pacific regions."
                ),
                discord.SelectOption(
                    label="AMERICAS",
                    value="americas",
                    description="North, Central & South America."
                ),
                discord.SelectOption(
                    label="Unspecified / Roaming",
                    value="unspecified",
                    description="You prefer not to declare a region."
                ),
            ]
        )
        async def region_select(self, interaction: discord.Interaction, select: discord.ui.Select):
            # Handle region selection (role assignment logic would go here)
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(f"You selected: {select.values[0]}", ephemeral=True)
    
    class PreferencesSelectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)
            
        @discord.ui.select(
            placeholder="Select your preferences",
            min_values=1,
            max_values=4,
            options=[
                discord.SelectOption(
                    label="Findom",
                    value="findom",
                    description="Financial Domination Focus"
                ),
                discord.SelectOption(
                    label="Techdom",
                    value="techdom",
                    description="System Domination Focus"
                ),
                discord.SelectOption(
                    label="Femdom",
                    value="femdom",
                    description="Standard Domination Tone"
                ),
                discord.SelectOption(
                    label="Beta Safe",
                    value="beta_safe",
                    description="Less NSFW"
                ),
            ]
        )
        async def preferences_select(self, interaction: discord.Interaction, select: discord.ui.Select):
            """Handle preferences selection - assign/remove roles"""
            if not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # Get preference role IDs from database
            from core.db import fetchall
            guild_id = interaction.guild.id
            
            # Fetch all preference role mappings for this guild
            rows = await fetchall(
                "SELECT preference_value, role_id FROM preference_roles WHERE guild_id = ?",
                (guild_id,)
            )
            
            # Build mapping of preference values to role IDs
            preference_role_map = {}
            all_preference_role_ids = set()
            for row in rows:
                preference_role_map[row["preference_value"]] = row["role_id"]
                all_preference_role_ids.add(row["role_id"])
            
            # If no roles configured, inform user
            if not preference_role_map:
                await interaction.followup.send("Preferences roles are not configured yet. Please contact an administrator.", ephemeral=True)
                return
            
            # Remove all previously assigned preference roles
            roles_to_remove = []
            for role in interaction.user.roles:
                if role.id in all_preference_role_ids:
                    roles_to_remove.append(role)
            
            # Add newly selected preference roles
            roles_to_add = []
            for value in select.values:
                role_id = preference_role_map.get(value)
                if role_id:
                    role = interaction.guild.get_role(role_id)
                    if role and role not in interaction.user.roles:
                        roles_to_add.append(role)
            
            # Apply role changes
            try:
                if roles_to_remove:
                    await interaction.user.remove_roles(*roles_to_remove, reason="Preferences updated")
                if roles_to_add:
                    await interaction.user.add_roles(*roles_to_add, reason="Preferences updated")
                
                await interaction.followup.send("Preferences updated.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"Failed to update preferences: {e}", ephemeral=True)
    
    # Roles configuration storage
    async def save_roles_config(guild_id: int, message_type: str, channel_id: int, message_id: int):
        """Save roles configuration to database"""
        from core.db import execute, _now_iso
        now = _now_iso()
        await execute(
            """INSERT OR REPLACE INTO roles_config (guild_id, message_type, channel_id, message_id, updated_at)
               VALUES (?, ?, ?, ?, ?)""",
            (guild_id, message_type, channel_id, message_id, now)
        )
    
    async def get_roles_config(guild_id: int, message_type: str):
        """Get roles configuration from database"""
        from core.db import fetchone
        row = await fetchone(
            "SELECT channel_id, message_id FROM roles_config WHERE guild_id = ? AND message_type = ?",
            (guild_id, message_type)
        )
        if row:
            return {"channel_id": row["channel_id"], "message_id": row["message_id"]}
        return None
    
    # Old subcommand groups removed - use /configure interactive menu instead
    # All old subcommand definitions below are commented out
    
    # configure_group = app_commands.Group(name="configure", description="[DEPRECATED]")
    # roles_group = app_commands.Group(name="roles", parent=configure_group, description="Configure role selection messages")
    
    # @roles_group.command(name="send", description="Send a role selection message to a channel")
    @app_commands.describe(
        message="Type of role message to send",
        channel="Channel to send the message to"
    )
    @app_commands.choices(message=[
        app_commands.Choice(name="pronouns", value="pronouns"),
        app_commands.Choice(name="petnames", value="petnames"),
        app_commands.Choice(name="region", value="region"),
        app_commands.Choice(name="preferences", value="preferences"),
    ])
    async def roles_send(interaction: discord.Interaction, message: str, channel: discord.TextChannel):
        """Send a role selection message to a channel"""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Build embed and view based on message type
        if message == "pronouns":
            embed = build_pronouns_embed()
            view = PronounsSelectView()
        elif message == "petnames":
            embed = build_petnames_embed()
            view = PetnamesSelectView()
        elif message == "region":
            embed = build_region_embed()
            view = RegionSelectView()
        elif message == "preferences":
            embed = build_preferences_embed()
            view = PreferencesSelectView()
        else:
            await interaction.followup.send("Invalid message type. Must be: pronouns, petnames, region, or preferences.", ephemeral=True)
            return
        
        # Check if message already exists
        existing = await get_roles_config(interaction.guild.id, message)
        if existing:
            # Overwrite existing message
            try:
                existing_channel = bot.get_channel(existing["channel_id"])
                if existing_channel:
                    existing_msg = await existing_channel.fetch_message(existing["message_id"])
                    if existing_msg:
                        await existing_msg.delete()
            except:
                pass  # Message may have been deleted, continue anyway
        
        # Send new message
        try:
            sent_message = await channel.send(embed=embed, view=view)
            await save_roles_config(interaction.guild.id, message, channel.id, sent_message.id)
            await interaction.followup.send(f"✅ Roles message for {message} has been sent.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to send message: {e}", ephemeral=True)
    
    @roles_group.command(name="edit", description="Edit an existing role selection message")
    @app_commands.describe(message="Type of role message to edit")
    @app_commands.choices(message=[
        app_commands.Choice(name="pronouns", value="pronouns"),
        app_commands.Choice(name="petnames", value="petnames"),
        app_commands.Choice(name="region", value="region"),
        app_commands.Choice(name="preferences", value="preferences"),
    ])
    async def roles_edit(interaction: discord.Interaction, message: str):
        """Edit an existing role selection message"""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Get existing configuration
        config = await get_roles_config(interaction.guild.id, message)
        if not config:
            await interaction.followup.send(f"❌ No {message} configuration message exists yet. Use /configure roles send first.", ephemeral=True)
            return
        
        # Build embed and view based on message type
        if message == "pronouns":
            embed = build_pronouns_embed()
            view = PronounsSelectView()
        elif message == "petnames":
            embed = build_petnames_embed()
            view = PetnamesSelectView()
        elif message == "region":
            embed = build_region_embed()
            view = RegionSelectView()
        elif message == "preferences":
            embed = build_preferences_embed()
            view = PreferencesSelectView()
        else:
            await interaction.followup.send("Invalid message type. Must be: pronouns, petnames, region, or preferences.", ephemeral=True)
            return
        
        # Fetch and edit message
        try:
            channel = bot.get_channel(config["channel_id"])
            if not channel:
                await interaction.followup.send(f"❌ Channel not found. Message may have been deleted.", ephemeral=True)
                return
            
            existing_msg = await channel.fetch_message(config["message_id"])
            await existing_msg.edit(embed=embed, view=view)
            await save_roles_config(interaction.guild.id, message, config["channel_id"], config["message_id"])
            await interaction.followup.send(f"✅ Roles message for {message} has been updated.", ephemeral=True)
        except discord.NotFound:
            await interaction.followup.send(f"❌ Message not found. It may have been deleted. Use /configure roles send to create a new one.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to edit message: {e}", ephemeral=True)
    
    # Introductions configuration commands
    introductions_group = app_commands.Group(name="introductions", parent=configure_group, description="Configure introduction channel")
    
    @introductions_group.command(name="set", description="Set the introductions channel")
    @app_commands.describe(channel="The channel to use for introductions")
    async def introductions_set(interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the introductions channel - always responds within 3s (C3)"""
        # Always defer to avoid timeout (C3)
        await interaction.response.defer(ephemeral=True)
        
        if not await check_admin_command_permissions(interaction):
            await interaction.followup.send("Permission check failed.", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.db import execute
        now = datetime.datetime.now(datetime.UTC).isoformat()
        
        await execute(
            """INSERT OR REPLACE INTO introductions_config (guild_id, channel_id, updated_at)
               VALUES (?, ?, ?)""",
            (interaction.guild.id, channel.id, now)
        )
        
        embed = discord.Embed(
            title="✅ Configuration Updated",
            description=f"Introductions channel set to {channel.mention}",
            color=0x4ec200
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @introductions_group.command(name="show", description="Show the current introductions channel")
    async def introductions_show(interaction: discord.Interaction):
        """Show the current introductions channel - always responds within 3s (C3)"""
        # Always defer to avoid timeout (C3)
        await interaction.response.defer(ephemeral=True)
        
        if not await check_admin_command_permissions(interaction):
            await interaction.followup.send("Permission check failed.", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.db import fetchone
        
        row = await fetchone(
            "SELECT channel_id FROM introductions_config WHERE guild_id = ?",
            (interaction.guild.id,)
        )
        
        if row:
            channel = bot.get_channel(row["channel_id"])
            if channel:
                embed = discord.Embed(
                    title="📋 Introductions Configuration",
                    description=f"Current channel: {channel.mention}",
                    color=0x4ec200
                )
            else:
                embed = discord.Embed(
                    title="📋 Introductions Configuration",
                    description=f"Channel ID: {row['channel_id']} (channel not found)",
                    color=0xff000d
                )
        else:
            embed = discord.Embed(
                title="📋 Introductions Configuration",
                description="No introductions channel configured. Use /configure introductions set to configure one.",
                color=0xff000d
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Orders configuration commands (B2)
    orders_config_group = app_commands.Group(name="orders", parent=configure_group, description="Configure orders system")
    
    # Casino configuration commands
    casino_config_group = app_commands.Group(name="casino", parent=configure_group, description="Configure casino channel")
    
    @casino_config_group.command(name="set", description="Set the casino channel")
    @app_commands.describe(channel="The channel to use for casino commands")
    async def casino_set(interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the casino channel - always responds within 3s (C3)"""
        # Always defer to avoid timeout (C3)
        await interaction.response.defer(ephemeral=True)
        
        if not await check_admin_command_permissions(interaction):
            await interaction.followup.send("Permission check failed.", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.db import execute, _now_iso
        now = _now_iso()
        
        await execute(
            """INSERT OR REPLACE INTO casino_channel_config (guild_id, channel_id, updated_at)
               VALUES (?, ?, ?)""",
            (interaction.guild.id, channel.id, now)
        )
        
        embed = discord.Embed(
            title="✅ Configuration Updated",
            description=f"Casino channel set to {channel.mention}",
            color=0x4ec200
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @casino_config_group.command(name="show", description="Show the current casino channel")
    async def casino_show(interaction: discord.Interaction):
        """Show the current casino channel - always responds within 3s (C3)"""
        # Always defer to avoid timeout (C3)
        await interaction.response.defer(ephemeral=True)
        
        if not await check_admin_command_permissions(interaction):
            await interaction.followup.send("Permission check failed.", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.db import get_casino_channel_id
        from core.config import CASINO_CHANNEL_ID
        
        channel_id = await get_casino_channel_id(interaction.guild.id)
        channel = bot.get_channel(channel_id)
        
        if channel:
            embed = discord.Embed(
                title="📋 Casino Configuration",
                description=f"Current channel: {channel.mention}",
                color=0x4ec200
            )
        else:
            embed = discord.Embed(
                title="📋 Casino Configuration",
                description=f"Channel ID: {channel_id} (channel not found)\n\nUsing default from config: {CASINO_CHANNEL_ID}",
                color=0xff000d
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Announcements configuration commands
    announcements_config_group = app_commands.Group(name="announcements", parent=configure_group, description="Configure announcements channel")
    
    @announcements_config_group.command(name="set", description="Set the announcements channel")
    @app_commands.describe(channel="The channel to use for announcements (throne, coffee, jackpots)")
    async def announcements_set(interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the announcements channel - always responds within 3s (C3)"""
        # Always defer to avoid timeout (C3)
        await interaction.response.defer(ephemeral=True)
        
        if not await check_admin_command_permissions(interaction):
            await interaction.followup.send("Permission check failed.", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.db import execute, _now_iso
        now = _now_iso()
        
        await execute(
            """INSERT OR REPLACE INTO announcements_channel_config (guild_id, channel_id, updated_at)
               VALUES (?, ?, ?)""",
            (interaction.guild.id, channel.id, now)
        )
        
        embed = discord.Embed(
            title="✅ Configuration Updated",
            description=f"Announcements channel set to {channel.mention}",
            color=0x4ec200
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @announcements_config_group.command(name="show", description="Show the current announcements channel")
    async def announcements_show(interaction: discord.Interaction):
        """Show the current announcements channel - always responds within 3s (C3)"""
        # Always defer to avoid timeout (C3)
        await interaction.response.defer(ephemeral=True)
        
        if not await check_admin_command_permissions(interaction):
            await interaction.followup.send("Permission check failed.", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.db import get_announcements_channel_id
        from core.config import EVENT_CHANNEL_ID
        
        channel_id = await get_announcements_channel_id(interaction.guild.id)
        channel = bot.get_channel(channel_id)
        
        if channel:
            embed = discord.Embed(
                title="📋 Announcements Configuration",
                description=f"Current channel: {channel.mention}",
                color=0x4ec200
            )
        else:
            embed = discord.Embed(
                title="📋 Announcements Configuration",
                description=f"Channel ID: {channel_id} (channel not found)\n\nUsing default from config: {EVENT_CHANNEL_ID}",
                color=0xff000d
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Logs configuration commands (C1)
    logs_config_group = app_commands.Group(name="logs", parent=configure_group, description="Configure logs channel (admin commands)")
    
    @logs_config_group.command(name="set", description="Set the logs channel (where admin commands can be used)")
    @app_commands.describe(channel="The channel to use for admin commands")
    async def logs_set(interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the logs channel"""
        # Always defer to avoid timeout (C3)
        await interaction.response.defer(ephemeral=True)
        
        if not await check_admin_command_permissions(interaction):
            await interaction.followup.send("Permission check failed.", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.db import execute, _now_iso
        now = _now_iso()
        
        await execute(
            """INSERT OR REPLACE INTO logs_channel_config (guild_id, channel_id, updated_at)
               VALUES (?, ?, ?)""",
            (interaction.guild.id, channel.id, now)
        )
        
        embed = discord.Embed(
            title="✅ Configuration Updated",
            description=f"Logs channel set to {channel.mention}\n\nAdmin commands can now only be used in this channel.",
            color=0x4ec200
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @logs_config_group.command(name="show", description="Show the current logs channel")
    async def logs_show(interaction: discord.Interaction):
        """Show the current logs channel"""
        # Always defer to avoid timeout (C3)
        await interaction.response.defer(ephemeral=True)
        
        if not await check_admin_command_permissions(interaction):
            await interaction.followup.send("Permission check failed.", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.db import get_logs_channel_id
        from core.config import ADMIN_COMMAND_CHANNEL_ID
        
        channel_id = await get_logs_channel_id(interaction.guild.id)
        channel = bot.get_channel(channel_id)
        
        if channel:
            embed = discord.Embed(
                title="📋 Logs Configuration",
                description=f"Current channel: {channel.mention}\n\nAdmin commands are restricted to this channel.",
                color=0x4ec200
            )
        else:
            embed = discord.Embed(
                title="📋 Logs Configuration",
                description=f"Channel ID: {channel_id} (channel not found)\n\nUsing default from config: {ADMIN_COMMAND_CHANNEL_ID}",
                color=0xff000d
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Usercommands configuration commands (C1)
    usercommands_config_group = app_commands.Group(name="usercommands", parent=configure_group, description="Configure usercommands channels (multiple allowed)")
    
    @usercommands_config_group.command(name="set", description="Set usercommands channels (can be called multiple times to add channels)")
    @app_commands.describe(channels="One or more channels where user commands can be used")
    async def usercommands_set(interaction: discord.Interaction, channels: str):
        """Set usercommands channels (comma-separated channel mentions or IDs)"""
        # Always defer to avoid timeout (C3)
        await interaction.response.defer(ephemeral=True)
        
        if not await check_admin_command_permissions(interaction):
            await interaction.followup.send("Permission check failed.", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        # Parse channel mentions/IDs
        channel_ids = []
        parts = [p.strip() for p in channels.split(",")]
        for part in parts:
            # Try to extract channel ID from mention (<#123456789>)
            if part.startswith("<#") and part.endswith(">"):
                try:
                    channel_id = int(part[2:-1])
                    channel_ids.append(channel_id)
                except ValueError:
                    pass
            else:
                # Try as direct ID
                try:
                    channel_id = int(part)
                    channel_ids.append(channel_id)
                except ValueError:
                    pass
        
        if not channel_ids:
            await interaction.followup.send("No valid channel IDs found. Please provide channel mentions or IDs (comma-separated).", ephemeral=True)
            return
        
        from core.db import execute, _now_iso
        now = _now_iso()
        guild_id = interaction.guild.id
        
        # Remove existing channels for this guild
        await execute(
            "DELETE FROM usercommands_channel_config WHERE guild_id = ?",
            (guild_id,)
        )
        
        # Add new channels
        for channel_id in channel_ids:
            channel = bot.get_channel(channel_id) or interaction.guild.get_channel(channel_id)
            if channel:
                await execute(
                    """INSERT INTO usercommands_channel_config (guild_id, channel_id, updated_at)
                       VALUES (?, ?, ?)""",
                    (guild_id, channel_id, now)
                )
        
        channel_mentions = " ".join(f"<#{cid}>" for cid in channel_ids if bot.get_channel(cid) or interaction.guild.get_channel(cid))
        embed = discord.Embed(
            title="✅ Configuration Updated",
            description=f"Usercommands channels set to: {channel_mentions}\n\nUser commands can now be used in these channels.",
            color=0x4ec200
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @usercommands_config_group.command(name="show", description="Show the current usercommands channels")
    async def usercommands_show(interaction: discord.Interaction):
        """Show the current usercommands channels"""
        # Always defer to avoid timeout (C3)
        await interaction.response.defer(ephemeral=True)
        
        if not await check_admin_command_permissions(interaction):
            await interaction.followup.send("Permission check failed.", ephemeral=True)
            return
        
        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.db import get_usercommands_channel_ids
        from core.config import USER_COMMAND_CHANNEL_ID
        
        channel_ids = await get_usercommands_channel_ids(interaction.guild.id)
        channel_mentions = []
        for channel_id in channel_ids:
            channel = bot.get_channel(channel_id) or interaction.guild.get_channel(channel_id)
            if channel:
                channel_mentions.append(channel.mention)
            else:
                channel_mentions.append(f"<#{channel_id}> (not found)")
        
        if channel_mentions:
            embed = discord.Embed(
                title="📋 Usercommands Configuration",
                description=f"Current channels: {' '.join(channel_mentions)}\n\nUser commands can be used in these channels.",
                color=0x4ec200
            )
        else:
            embed = discord.Embed(
                title="📋 Usercommands Configuration",
                description=f"Using default from config: <#{USER_COMMAND_CHANNEL_ID}>",
                color=0xff000d
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    # Debt group for debt management commands
    debt_group = app_commands.Group(name="debt", description="Debt management commands. Admin only.")
    
    @debt_group.command(name="throne_payoff", description="Pay off user debt using Throne funds. Admin only.")
    @app_commands.describe(
        user="The user whose debt to pay off",
        amount="The amount to pay off",
        note="Optional note for the transaction"
    )
    async def debt_throne_payoff(interaction: discord.Interaction, user: discord.Member, amount: int, note: str = ""):
        """Pay off user debt using Throne funds"""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        guild_id = interaction.guild.id
        user_id = user.id
        
        # Validate amount
        if amount <= 0:
            from core.utils import impact_icon
            from core.config import ERROR_GIF
            embed = discord.Embed(
                description="Amount must be positive.",
                color=0xff000d
            )
            embed.set_author(name="Error", icon_url=ERROR_GIF)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get current debt
        from core.data import get_debt, pay_debt, update_debt
        current_debt = await get_debt(guild_id, user_id)
        
        if current_debt <= 0:
            from core.utils import impact_icon
            from core.config import ERROR_GIF
            embed = discord.Embed(
                description=f"{user.mention} has no debt to pay off.",
                color=0xff000d
            )
            embed.set_author(name="Error", icon_url=ERROR_GIF)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Pay off debt (amount cannot exceed debt)
        payoff_amount = min(amount, current_debt)
        
        # Reduce debt directly (Throne payoff doesn't require balance)
        await update_debt(guild_id, user_id, -payoff_amount)
        
        # Log to ledger
        from core.db import execute, _now_iso
        import json
        now = _now_iso()
        await execute(
            """INSERT INTO economy_ledger (guild_id, user_id, ts, type, amount, meta_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (guild_id, user_id, now, "throne_debt_payoff", -payoff_amount,
             json.dumps({"admin_id": interaction.user.id, "note": note, "debt_before": current_debt, "debt_after": current_debt - payoff_amount}))
        )
        
        # Send admin confirmation
        from core.utils import impact_icon
        from core.config import HEART_GIF
        admin_embed = discord.Embed(
            description=f"Paid off **{payoff_amount}** coins of debt for {user.mention}.\n\nRemaining debt: **{current_debt - payoff_amount}** coins.",
            color=0x4ec200
        )
        admin_embed.set_author(name="Throne Debt Payoff", icon_url=HEART_GIF)
        if note:
            admin_embed.set_footer(text=f"Note: {note}")
        await interaction.response.send_message(embed=admin_embed, ephemeral=True)
        
        # Send user DM receipt
        try:
            user_embed = discord.Embed(
                description=f"Your debt has been reduced by **{payoff_amount}** coins via Throne payment.\n\nRemaining debt: **{current_debt - payoff_amount}** coins.",
                color=0x4ec200
            )
            user_embed.set_author(name="Debt Payment Received", icon_url=HEART_GIF)
            if note:
                user_embed.set_footer(text=f"Note: {note}")
            await user.send(embed=user_embed)
        except discord.Forbidden:
            # User has DMs disabled, skip
            pass
        except Exception as e:
            print(f"Error sending DM to user {user_id}: {e}")
    
    bot.tree.add_command(debt_group)
    
    @orders_config_group.command(name="new_orders_announcement", description="Set the channel for new orders announcements")
    @app_commands.describe(channel="The channel to post new orders announcements")
    async def orders_new_orders_announcement(interaction: discord.Interaction, channel: discord.TextChannel):
        """Set orders announcement channel"""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        from core.db import execute, _now_iso
        now = _now_iso()
        
        await execute(
            """INSERT OR REPLACE INTO orders_announcement_config (guild_id, channel_id, updated_at)
               VALUES (?, ?, ?)""",
            (interaction.guild.id, channel.id, now)
        )
        
        embed = discord.Embed(
            title="✅ Configuration Updated",
            description=f"Orders announcement channel set to {channel.mention}",
            color=0x4ec200
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Old configure_group not registered - using interactive /configure menu instead
    # bot.tree.add_command(configure_group)
    
    @bot.tree.command(name="casino_test", description="Test casino embed types. Admin only.")
    @app_commands.describe(embed_type="Type of casino embed to test")
    @app_commands.choices(embed_type=[
        app_commands.Choice(name="coinflip_win", value="coinflip_win"),
        app_commands.Choice(name="coinflip_loss", value="coinflip_loss"),
        app_commands.Choice(name="dice_win", value="dice_win"),
        app_commands.Choice(name="dice_loss", value="dice_loss"),
        app_commands.Choice(name="dice_draw", value="dice_draw"),
        app_commands.Choice(name="slots_win", value="slots_win"),
        app_commands.Choice(name="slots_loss", value="slots_loss"),
        app_commands.Choice(name="slots_jackpot", value="slots_jackpot"),
        app_commands.Choice(name="roulette_win", value="roulette_win"),
        app_commands.Choice(name="roulette_loss", value="roulette_loss"),
        app_commands.Choice(name="blackjack_state", value="blackjack_state"),
        app_commands.Choice(name="blackjack_win", value="blackjack_win"),
        app_commands.Choice(name="blackjack_loss", value="blackjack_loss"),
        app_commands.Choice(name="blackjack_draw", value="blackjack_draw"),
        app_commands.Choice(name="info_casino", value="info_casino"),
        app_commands.Choice(name="info_paytable", value="info_paytable"),
        app_commands.Choice(name="error_channel", value="error_channel"),
        app_commands.Choice(name="error_debt", value="error_debt"),
        app_commands.Choice(name="error_limit", value="error_limit"),
        app_commands.Choice(name="error_cooldown", value="error_cooldown"),
        app_commands.Choice(name="jackpot_announcement", value="jackpot_announcement"),
    ])
    async def casino_test(interaction: discord.Interaction, embed_type: str):
        """Test different casino embed types."""
        if not await check_admin_command_permissions(interaction):
            return
        
        user_display = interaction.user.display_name
        
        if embed_type == "coinflip_win":
            embed = build_casino_embed(
                kind="win",
                outcome=100,
                title="🪙 Coinflip — WIN",
                description=f"**{user_display}** wins **100** coins.",
                fields=[
                    {"name": "Bet", "value": "**100**", "inline": True},
                    {"name": "Multiplier", "value": "`x2`", "inline": True},
                    {"name": "New Balance", "value": "**500**", "inline": True}
                ],
                streak=5,
                cooldown=8
            )
        elif embed_type == "coinflip_loss":
            embed = build_casino_embed(
                kind="loss",
                outcome=-100,
                title="🪙 Coinflip — LOSS",
                description=f"**{user_display}** loses **100** coins.",
                fields=[
                    {"name": "Bet", "value": "**100**", "inline": True},
                    {"name": "Result", "value": "`Lose`", "inline": True},
                    {"name": "New Balance", "value": "**400**", "inline": True}
                ],
                streak=-6,
                cooldown=8
            )
        elif embed_type == "dice_win":
            embed = build_casino_embed(
                kind="win",
                outcome=100,
                title="🎲 Dice — WIN",
                description=f"**{user_display}** wins.",
                fields=[
                    {"name": "Rolls", "value": "`You: 5` • `Dealer: 3`", "inline": False},
                    {"name": "Bet", "value": "**100**", "inline": True},
                    {"name": "Net", "value": "**+100**", "inline": True},
                    {"name": "New Balance", "value": "**500**", "inline": True}
                ],
                streak=3,
                cooldown=10
            )
        elif embed_type == "dice_loss":
            embed = build_casino_embed(
                kind="loss",
                outcome=-100,
                title="🎲 Dice — LOSS",
                description=f"**{user_display}** loses.",
                fields=[
                    {"name": "Rolls", "value": "`You: 2` • `Dealer: 4`", "inline": False},
                    {"name": "Bet", "value": "**100**", "inline": True},
                    {"name": "Net", "value": "**-100**", "inline": True},
                    {"name": "New Balance", "value": "**400**", "inline": True}
                ],
                streak=-5,
                cooldown=10
            )
        elif embed_type == "dice_draw":
            embed = build_casino_embed(
                kind="draw",
                outcome=0,
                title="🎲 Dice — DRAW",
                description=f"**{user_display}** ties.",
                fields=[
                    {"name": "Rolls", "value": "`You: 4` • `Dealer: 4`", "inline": False},
                    {"name": "Bet", "value": "**100**", "inline": True},
                    {"name": "Net", "value": "**0** (refunded)", "inline": True},
                    {"name": "New Balance", "value": "**500**", "inline": True}
                ],
                cooldown=10
            )
        elif embed_type == "slots_win":
            embed = build_casino_embed(
                kind="win",
                outcome=750,
                title="🎰 Slots",
                description=f"**{user_display}** spins for **100** coins.",
                fields=[
                    {"name": "Reels", "value": "🍒 │ 🍒 │ 🍒", "inline": False},
                    {"name": "Outcome", "value": "Win x15", "inline": True},
                    {"name": "Net", "value": "**+750**", "inline": True},
                    {"name": "New Balance", "value": "**850**", "inline": True}
                ],
                streak=4,
                cooldown=15
            )
        elif embed_type == "slots_loss":
            embed = build_casino_embed(
                kind="loss",
                outcome=-50,
                title="🎰 Slots",
                description=f"**{user_display}** spins for **100** coins.",
                fields=[
                    {"name": "Reels", "value": "🥝 │ 🍇 │ 🍋", "inline": False},
                    {"name": "Outcome", "value": "Loss", "inline": True},
                    {"name": "Net", "value": "**-50**", "inline": True},
                    {"name": "New Balance", "value": "**450**", "inline": True}
                ],
                streak=-7,
                cooldown=15
            )
        elif embed_type == "slots_jackpot":
            embed = build_casino_embed(
                kind="win",
                outcome=2900,
                title="🎰 Slots",
                description=f"**{user_display}** spins for **100** coins.",
                fields=[
                    {"name": "Reels", "value": "👑 │ 👑 │ 👑", "inline": False},
                    {"name": "Outcome", "value": "Win x30 👑", "inline": True},
                    {"name": "Net", "value": "**+2900**", "inline": True},
                    {"name": "New Balance", "value": "**3000**", "inline": True}
                ],
                streak=5,
                cooldown=15
            )
        elif embed_type == "roulette_win":
            embed = build_casino_embed(
                kind="win",
                outcome=3500,
                title="🎡 Roulette",
                description=f"**{user_display}** bets **100** coins.",
                fields=[
                    {"name": "Bet Type", "value": "`7`", "inline": True},
                    {"name": "Spin", "value": "`🔴 7`", "inline": True},
                    {"name": "Payout", "value": "x36", "inline": True},
                    {"name": "Net", "value": "**+3500**", "inline": True},
                    {"name": "New Balance", "value": "**3600**", "inline": True}
                ],
                streak=3,
                cooldown=20
            )
        elif embed_type == "roulette_loss":
            embed = build_casino_embed(
                kind="loss",
                outcome=-100,
                title="🎡 Roulette",
                description=f"**{user_display}** bets **100** coins.",
                fields=[
                    {"name": "Bet Type", "value": "`red`", "inline": True},
                    {"name": "Spin", "value": "`⚫ 14`", "inline": True},
                    {"name": "Net", "value": "**-100**", "inline": True},
                    {"name": "New Balance", "value": "**400**", "inline": True}
                ],
                streak=-5,
                cooldown=20
            )
        elif embed_type == "blackjack_state":
            embed = build_casino_embed(
                kind="neutral",
                outcome=None,
                title="🃏 Blackjack",
                description=f"**{user_display}** plays **100** coins. Choose an action below.",
                fields=[
                    {"name": "Your Hand", "value": "10 + 6  (**16**)", "inline": False},
                    {"name": "Dealer", "value": "9  (`?`)", "inline": False}
                ],
                footer_text="Timeout: 60s (auto-stand)",
                cooldown=30
            )
        elif embed_type == "blackjack_win":
            embed = build_casino_embed(
                kind="win",
                outcome=100,
                title="🃏 Blackjack — WIN",
                description=f"**{user_display}** wins.",
                fields=[
                    {"name": "Your Hand", "value": "10 + 8  (**18**)", "inline": False},
                    {"name": "Dealer Hand", "value": "7 + 9  (**16**)", "inline": False},
                    {"name": "Net", "value": "**+100**", "inline": True},
                    {"name": "New Balance", "value": "**500**", "inline": True}
                ],
                streak=3,
                cooldown=30
            )
        elif embed_type == "blackjack_loss":
            embed = build_casino_embed(
                kind="loss",
                outcome=-100,
                title="🃏 Blackjack — LOSS",
                description=f"**{user_display}** loses.",
                fields=[
                    {"name": "Your Hand", "value": "10 + 9 + 5  (**24**)", "inline": False},
                    {"name": "Dealer Hand", "value": "8 + 7  (**15**)", "inline": False},
                    {"name": "Net", "value": "**-100**", "inline": True},
                    {"name": "New Balance", "value": "**400**", "inline": True}
                ],
                streak=-5,
                cooldown=30
            )
        elif embed_type == "blackjack_draw":
            embed = build_casino_embed(
                kind="draw",
                outcome=0,
                title="🃏 Blackjack — DRAW",
                description=f"**{user_display}** pushes.",
                fields=[
                    {"name": "Your Hand", "value": "10 + 7  (**17**)", "inline": False},
                    {"name": "Dealer Hand", "value": "9 + 8  (**17**)", "inline": False},
                    {"name": "Net", "value": "**0** (bet returned)", "inline": True},
                    {"name": "New Balance", "value": "**500**", "inline": True}
                ],
                cooldown=30
            )
        elif embed_type == "info_casino":
            embed = build_casino_embed(
                kind="info",
                outcome=None,
                title="ℹ️ Casino Overview",
                description="All games use unified validation: **debt blocking**, **rank caps**, **channel enforcement**, and **LCE tracking**.",
                fields=[
                    {"name": "Games", "value": "`/coinflip` `/gamble` • `/dice` • `/slots` • `/roulette` • `/blackjack`", "inline": False},
                    {"name": "Cooldowns", "value": "Coinflip 8s • Dice 10s • Slots 15s • Roulette 20s • Blackjack 30s", "inline": False},
                    {"name": "Streaks", "value": "🔥 Hot: 3+ wins • 🥶 Cold: 5+ losses • resets after 1h inactivity", "inline": False}
                ],
                footer_text="Use the /<game>info commands for full rules."
            )
        elif embed_type == "info_paytable":
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
        elif embed_type == "error_channel":
            embed = build_casino_embed(
                kind="info",
                outcome=None,
                title="ℹ️ Casino Channel Only",
                description="Use casino commands in <#1449946515882774630>.",
                fields=[
                    {"name": "Blocked Here", "value": "This command is restricted to the configured casino channel.", "inline": False}
                ],
                footer_text="Ask staff if the casino channel was moved."
            )
        elif embed_type == "error_debt":
            embed = build_casino_embed(
                kind="info",
                outcome=None,
                title="ℹ️ Gambling Locked",
                description="Gambling is disabled while your **Debt ≥ 5000** coins.",
                fields=[
                    {"name": "Current Debt", "value": "**5250**", "inline": True},
                    {"name": "Requirement", "value": "Debt must be **< 5000**", "inline": True}
                ],
                footer_text="Clear debt to regain casino access."
            )
        elif embed_type == "error_limit":
            embed = build_casino_embed(
                kind="info",
                outcome=None,
                title="ℹ️ Bet Limit Reached",
                description="Your bet exceeds your allowed maximum.",
                fields=[
                    {"name": "Your Rank Cap", "value": "**5000**", "inline": True},
                    {"name": "Absolute Max", "value": "**25000**", "inline": True},
                    {"name": "Your Bet", "value": "**6000**", "inline": True}
                ],
                footer_text="Caps are based on Lifetime Coins Earned (LCE)."
            )
        elif embed_type == "error_cooldown":
            embed = build_casino_embed(
                kind="info",
                outcome=None,
                title="ℹ️ Cooldown Active",
                description="You can gamble again in 5 seconds.",
                cooldown=8
            )
        elif embed_type == "jackpot_announcement":
            embed = build_casino_embed(
                kind="announcement",
                outcome=None,
                title="📣 JACKPOT HIT",
                description=f"**{user_display}** just landed **👑 x30** on Slots.",
                fields=[
                    {"name": "Spin", "value": "👑 │ 👑 │ 👑", "inline": False},
                    {"name": "Bet", "value": "**100**", "inline": True},
                    {"name": "Payout", "value": "**3000**", "inline": True},
                    {"name": "Net Gain", "value": "**2900**", "inline": True}
                ],
                footer_text="Casino • Slots • Big win broadcast"
            )
        else:
            await interaction.response.send_message(f"Unknown embed type: {embed_type}", ephemeral=True)
            return
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @bot.tree.command(name="orders_test", description="Test orders embed and views. Admin only.")
    async def orders_test(interaction: discord.Interaction):
        """Test orders embed and views - sends public /orders view"""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        # Import orders embed builder and view
        from commands.user_commands import build_orders_embed, OrdersSelectView, _get_available_orders
        
        guild_id = interaction.guild.id
        user_id = interaction.user.id
        
        available_orders = await _get_available_orders(guild_id)
        embed = build_orders_embed(available_orders, guild_id, user_id)
        view = OrdersSelectView(available_orders, guild_id, user_id)
        
        # Send publicly (no ephemeral) to match /orders behavior
        await interaction.response.send_message(embed=embed, view=view)
    
    @bot.tree.command(name="onboarding_test", description="Test onboarding messages. Admin only.")
    async def onboarding_test(interaction: discord.Interaction):
        """Test onboarding messages - sends public onboarding rules"""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        from systems.onboarding import send_onboarding_rules
        
        member = interaction.user
        await send_onboarding_rules(interaction, member, is_reply=False)
    
    @bot.tree.command(name="introduction_test", description="Test introduction channel message. Admin only.")
    async def introduction_test(interaction: discord.Interaction):
        """Test introduction channel message - shows what happens when a message is sent"""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        # Show what happens: the bot adds a ❤️ reaction
        embed = discord.Embed(
            title="📝 Introduction Channel Test",
            description="When a message is sent in the introductions channel, IslaBot automatically adds a ❤️ reaction.\n\nThis is a test - in the actual channel, reactions are added automatically.",
            color=0x4ec200
        )
        
        # Add ❤️ reaction to this test message to demonstrate
        await interaction.response.send_message(embed=embed, ephemeral=True)
        try:
            # Get the response message to add reaction
            message = await interaction.original_response()
            await message.add_reaction("❤️")
        except:
            pass
    
    @bot.tree.command(name="testmessage", description="Test onboarding and profile messages. Admin only.")
    @app_commands.describe(message_name="Name of the message to test", category="Category for profile_info (optional)")
    async def testmessage(interaction: discord.Interaction, message_name: str, category: str = None):
        """Test onboarding and profile messages"""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        member = interaction.user
        
        # Onboarding messages
        if message_name.startswith("onboarding_"):
            from systems.onboarding import (
                send_onboarding_welcome, send_onboarding_rules,
                send_rules_accept_1, send_rules_decline_1,
                send_rules_accept_2, send_rules_decline_2,
                send_rules_submission_false, send_rules_submission_correct
            )
            
            if message_name == "onboarding_welcome":
                await interaction.response.defer(ephemeral=True)
                await send_onboarding_welcome(member)
                await interaction.followup.send("✅ Welcome message sent!", ephemeral=True)
            
            elif message_name == "onboarding_rules":
                await send_onboarding_rules(interaction, member)
            
            elif message_name == "onboarding_rules_accept_1":
                await send_rules_accept_1(interaction, member)
            
            elif message_name == "onboarding_rules_decline_1":
                await send_rules_decline_1(interaction, member)
            
            elif message_name == "onboarding_rules_accept_2":
                await send_rules_accept_2(interaction, member)
            
            elif message_name == "onboarding_rules_decline_2":
                await send_rules_decline_2(interaction, member)
            
            elif message_name == "onboarding_rules_submission_false":
                await send_rules_submission_false(interaction, member)
            
            elif message_name == "onboarding_rules_submission_correct":
                await interaction.response.defer(ephemeral=True)
                channel = interaction.channel
                if isinstance(channel, discord.TextChannel):
                    await send_rules_submission_correct(channel, member)
                await interaction.followup.send("✅ Submission correct message sent!", ephemeral=True)
            
            else:
                await interaction.response.send_message(
                    f"Unknown onboarding message: {message_name}",
                    ephemeral=True,
                    delete_after=5
                )
        
        # Profile messages
        elif message_name == "profile":
            from core.data import get_profile_stats
            from commands.user_commands import build_profile_embed
            
            guild_id = interaction.guild.id if interaction.guild else 0
            fake_stats = await get_profile_stats(guild_id, member.id)
            embed = build_profile_embed(member, fake_stats)
            
            from core.config import ALLOWED_SEND_SET
            if int(interaction.channel.id) in ALLOWED_SEND_SET:
                await interaction.response.send_message(content=f"<@{member.id}>", embed=embed)
            else:
                await interaction.response.send_message(content=f"<@{member.id}>", embed=embed, delete_after=15)
        
        elif message_name == "collection":
            from core.data import get_profile_stats
            from commands.user_commands import build_collection_embed
            
            guild_id = interaction.guild.id if interaction.guild else 0
            fake_stats = await get_profile_stats(guild_id, member.id)
            embed = build_collection_embed(member, fake_stats)
            
            from core.config import ALLOWED_SEND_SET
            if int(interaction.channel.id) in ALLOWED_SEND_SET:
                await interaction.response.send_message(content=f"<@{member.id}>", embed=embed)
            else:
                await interaction.response.send_message(content=f"<@{member.id}>", embed=embed, delete_after=15)
        
        # Rank messages
        elif message_name == "rank":
            from core.data import get_profile_stats, get_rank
            from commands.user_commands import build_rank_embed
            from systems.progression import GATES, RANK_LADDER
            
            guild_id = interaction.guild.id if interaction.guild else 0
            fake_stats = await get_profile_stats(guild_id, member.id)
            rank_data = await get_rank(guild_id, member.id)
            fake_stats.update(rank_data)
            
            # Calculate failing gates count
            rank_names = [r["name"] for r in RANK_LADDER]
            current_rank_name = fake_stats.get("rank", "Newcomer")
            current_idx = rank_names.index(current_rank_name) if current_rank_name in rank_names else 0
            next_idx = min(current_idx + 1, len(rank_names) - 1)
            next_rank_name = rank_names[next_idx] if next_idx > current_idx else current_rank_name
            
            failing_gates_count = 0
            if next_rank_name != "Max Rank":
                next_gates = GATES.get(next_rank_name, [])
                for gate in next_gates:
                    gate_type = gate["type"]
                    gate_min = gate["min"]
                    
                    if gate_type == "messages_7d" and fake_stats.get("messages_sent", 0) < gate_min:
                        failing_gates_count += 1
                    elif gate_type == "was" and fake_stats.get("was", 0) < gate_min:
                        failing_gates_count += 1
                    elif gate_type == "obedience14" and fake_stats.get("obedience_pct", 0) < gate_min:
                        failing_gates_count += 1
                
                if fake_stats.get("orders_failed", 0) > 4:
                    failing_gates_count += 1
                if fake_stats.get("orders_late", 0) > 2:
                    failing_gates_count += 1
            
            fake_stats["failing_gates_count"] = failing_gates_count
            
            embed = build_rank_embed(member, fake_stats)
            
            from core.config import ALLOWED_SEND_SET
            if int(interaction.channel.id) in ALLOWED_SEND_SET:
                await interaction.response.send_message(content=f"<@{member.id}>", embed=embed)
            else:
                await interaction.response.send_message(content=f"<@{member.id}>", embed=embed, delete_after=15)
        
        elif message_name == "rank_info":
            from commands.user_commands import build_rank_info_embed
            
            embed = build_rank_info_embed()
            
            from core.config import ALLOWED_SEND_SET
            if int(interaction.channel.id) in ALLOWED_SEND_SET:
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(embed=embed, delete_after=15)
        
        # Order messages
        elif message_name == "orders":
            from commands.user_commands import build_orders_embed, _get_available_orders
            
            guild_id = interaction.guild.id if interaction.guild else 0
            user_id = member.id
            available_orders = await _get_available_orders(guild_id)
            embed = build_orders_embed(available_orders, guild_id, user_id)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        elif message_name.startswith("order_info:"):
            order_name = message_name.split(":", 1)[1]
            from commands.user_commands import build_order_info_embed, _normalize_order_name, _get_available_orders
            
            guild_id = interaction.guild.id if interaction.guild else 0
            order_key = _normalize_order_name(order_name)
            available_orders = await _get_available_orders(guild_id)
            is_available = order_key in available_orders
            
            embed = build_order_info_embed(order_key, is_available)
            if embed:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("Unknown order.", ephemeral=True)
        
        elif message_name.startswith("order_accept:"):
            order_name = message_name.split(":", 1)[1]
            from commands.user_commands import build_order_accept_embed, _normalize_order_name, ORDERS_CATALOG
            
            order_key = _normalize_order_name(order_name)
            if order_key in ORDERS_CATALOG:
                order = ORDERS_CATALOG[order_key]
                embed = build_order_accept_embed(order_key, order["due_seconds"])
                if embed:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message("Error building embed.", ephemeral=True)
            else:
                await interaction.response.send_message("Unknown order.", ephemeral=True)
        
        elif message_name.startswith("order_complete:"):
            order_name = message_name.split(":", 1)[1]
            from commands.user_commands import build_order_complete_embed, _normalize_order_name, ORDERS_CATALOG
            
            order_key = _normalize_order_name(order_name)
            if order_key in ORDERS_CATALOG:
                order = ORDERS_CATALOG[order_key]
                # Simulate completion proof
                completion_proof = "💬 Messages: 2/2\n✅ Task completed"
                embed = build_order_complete_embed(order_key, False, order["reward_coins"], completion_proof)
                if embed:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message("Error building embed.", ephemeral=True)
            else:
                await interaction.response.send_message("Unknown order.", ephemeral=True)
        
        else:
            await interaction.response.send_message(
                f"Unknown message name: {message_name}\n\nAvailable messages:\n"
                "**Onboarding:**\n"
                "- onboarding_welcome\n- onboarding_rules\n- onboarding_rules_accept_1\n"
                "- onboarding_rules_decline_1\n- onboarding_rules_accept_2\n- onboarding_rules_decline_2\n"
                "- onboarding_rules_submission_false\n- onboarding_rules_submission_correct\n\n"
                "**Profile:**\n"
                "- profile\n- collection\n\n"
                "**Rank:**\n"
                "- rank\n- rank_info\n\n"
                "**Orders:**\n"
                "- orders\n- order_info:<order_name>\n- order_accept:<order_name>\n- order_complete:<order_name>",
                ephemeral=True,
                delete_after=15
            )
    
    @bot.tree.command(name="messages", description="List all registered message templates. Admin only.")
    @app_commands.describe()
    async def messages_list(interaction: discord.Interaction):
        """List all registered message templates grouped by system prefix"""
        if not await check_admin_command_permissions(interaction):
            return
        
        # Group messages by prefix (first part before dot)
        groups = {}
        for msg_id, metadata in MESSAGES.items():
            prefix = msg_id.split(".", 1)[0] if "." in msg_id else "misc"
            if prefix not in groups:
                groups[prefix] = []
            groups[prefix].append((msg_id, metadata))
        
        # Sort groups and messages within groups
        sorted_groups = sorted(groups.items())
        for prefix in sorted_groups:
            groups[prefix[0]].sort(key=lambda x: x[0])
        
        # Build list of all entries for pagination
        all_entries = []
        for prefix, msgs in sorted_groups:
            for msg_id, metadata in msgs:
                all_entries.append((prefix, msg_id, metadata))
        
        total_entries = len(all_entries)
        entries_per_page = 20
        
        if total_entries <= entries_per_page:
            # Single page - no pagination needed
            embed = discord.Embed(
                description="Registered message templates available for testing.",
                color=0x58585f
            )
            embed.set_author(name="Message Registry", icon_url=HEART_GIF)
            
            # Add fields per category
            for prefix, msgs in sorted_groups:
                lines = []
                for msg_id, metadata in msgs:
                    kind = metadata["kind"]
                    visibility = metadata["visibility"]
                    impact = metadata["impact"]
                    lines.append(f"`{msg_id}` — {kind} — {visibility} — {impact}")
                
                value = "\n".join(lines)
                # Discord field value limit is 1024 characters
                if len(value) > 1024:
                    # Split into multiple fields if needed
                    chunk_size = 900  # Leave some buffer
                    chunks = [value[i:i+chunk_size] for i in range(0, len(value), chunk_size)]
                    for i, chunk in enumerate(chunks):
                        field_name = prefix.capitalize() if i == 0 else f"{prefix.capitalize()} (cont.)"
                        embed.add_field(name=field_name, value=chunk, inline=False)
                else:
                    embed.add_field(name=prefix.capitalize(), value=value, inline=False)
            
            embed.set_footer(text="Use /testmessage <message_id> or /testsequence <sequence_id>.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # Multiple pages - use Select Menu for pagination
            class MessagesListView(discord.ui.View):
                def __init__(self, all_entries, entries_per_page, author_id):
                    super().__init__(timeout=300)
                    self.all_entries = all_entries
                    self.entries_per_page = entries_per_page
                    self.author_id = author_id
                    self.current_page = 0
                    self.max_page = (total_entries - 1) // entries_per_page
                    self._build_page_select()
                
                def _build_page_select(self):
                    """Build or rebuild the page select menu"""
                    # Remove existing select if present
                    for item in self.children[:]:
                        if isinstance(item, discord.ui.Select):
                            self.remove_item(item)
                    
                    self.page_select = discord.ui.Select(
                        placeholder=f"Page {self.current_page + 1} of {self.max_page + 1}",
                        options=[
                            discord.SelectOption(
                                label=f"Page {i + 1}",
                                value=str(i),
                                default=(i == self.current_page)
                            )
                            for i in range(self.max_page + 1)
                        ]
                    )
                    self.page_select.callback = self.on_page_select
                    self.add_item(self.page_select)
                
                async def on_page_select(self, interaction: discord.Interaction):
                    if interaction.user.id != self.author_id:
                        await interaction.response.send_message("This is not your message list.", ephemeral=True)
                        return
                    
                    page = int(self.page_select.values[0])
                    self.current_page = page
                    self._build_page_select()
                    embed = self.build_embed()
                    await interaction.response.edit_message(embed=embed, view=self)
                
                def build_embed(self):
                    """Build embed for current page"""
                    start_idx = self.current_page * self.entries_per_page
                    end_idx = min(start_idx + self.entries_per_page, len(self.all_entries))
                    page_entries = self.all_entries[start_idx:end_idx]
                    
                    # Group page entries by prefix
                    page_groups = {}
                    for prefix, msg_id, metadata in page_entries:
                        if prefix not in page_groups:
                            page_groups[prefix] = []
                        page_groups[prefix].append((msg_id, metadata))
                    
                    embed = discord.Embed(
                        description=f"Registered message templates available for testing. (Page {self.current_page + 1} of {self.max_page + 1})",
                        color=0x58585f
                    )
                    embed.set_author(name="Message Registry", icon_url=HEART_GIF)
                    
                    # Add fields per category on this page
                    for prefix in sorted(page_groups.keys()):
                        lines = []
                        for msg_id, metadata in page_groups[prefix]:
                            kind = metadata["kind"]
                            visibility = metadata["visibility"]
                            impact = metadata["impact"]
                            lines.append(f"`{msg_id}` — {kind} — {visibility} — {impact}")
                        
                        value = "\n".join(lines)
                        if len(value) > 1024:
                            chunk_size = 900
                            chunks = [value[i:i+chunk_size] for i in range(0, len(value), chunk_size)]
                            for i, chunk in enumerate(chunks):
                                field_name = prefix.capitalize() if i == 0 else f"{prefix.capitalize()} (cont.)"
                                embed.add_field(name=field_name, value=chunk, inline=False)
                        else:
                            embed.add_field(name=prefix.capitalize(), value=value, inline=False)
                    
                    embed.set_footer(text="Use /testmessage <message_id> or /testsequence <sequence_id>.")
                    return embed
            
            view = MessagesListView(all_entries, entries_per_page, interaction.user.id)
            initial_embed = view.build_embed()
            await interaction.response.send_message(embed=initial_embed, view=view, ephemeral=True)

