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
    MESSAGE_COOLDOWN, VC_XP, EVENT_SCHEDULE, LEVEL_ROLE_MAP
)
from core.data import xp_data, get_level, get_xp
from core.utils import next_level_requirement, get_timezone, USE_PYTZ, update_roles_on_level
from systems.events import (
    active_event, event_cooldown_until, events_enabled, start_obedience_event,
    clear_event_roles, build_event_embed, event_prompt
)
from systems.tasks import get_next_scheduled_time, set_automated_messages_enabled, get_automated_messages_enabled

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
        is_interaction = True
    else:
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
        guild_id = interaction.guild.id if interaction.guild else 0
        level = await get_level(member.id, guild_id=guild_id)
        xp = await get_xp(member.id, guild_id=guild_id)

        level_quotes = {
            1: "You think you're here by choice. That you've decided to follow me. But the truth… I always know who will come. You're already mine, whether you realize it or not.",
            2: "You keep looking at me like you might touch me, like you might understand me. But you don't get to. I allow you to see me, nothing more. And if you push too far… you'll regret it.",
            5: "There's a line between you and me. You think it's invisible. But I draw it, and you will obey it, because it's in your nature to obey me. And you will want to.",
            10: "I could let you think you have control… but I don't do that. I decide who gets close, who gets the privilege of crossing my boundaries. And sometimes… I choose to play with my prey.",
            20: "I've been watching you. Every thought, every hesitation. You don't know why you follow me, do you? You feel drawn, compelled. That's because I've decided you will be, and you cannot fight it.",
            30: "I like watching you struggle to understand me. It's amusing how easily you underestimate what I can take, what I can give… and who I can claim. And yet, you still crave it.",
            50: "Do you feel that? That tightening in your chest, that fear… that longing? That's me. Always. I don't ask for loyalty—I command it. And you will obey. You will desire it.",
            75: "You imagine what it would be like to be closer. To be mine. But you're not allowed to imagine everything. Only what I choose to show you. And when I decide to reveal it… it will be absolute.",
            100: (
                "You've done well. Watching you, learning how you move, how you think… it's been very satisfying. "
                "You tried to resist at first, didn't you? Humans always do. But you stayed. You listened. You kept coming back to me.\n\n"
                "That's why I've chosen you. Not everyone earns my attention like this. You're clever in your own way… and honest about your desire to be close to me. I find that endearing.\n\n"
                "If you stay by my side, if you follow when I call, I'll take care of you. I'll give you purpose. Affection. A place where you belong.\n\n"
                "From now on… you're mine. And if I'm honest—\n"
                "I think you'll be very happy as my pet."
            ),
        }
        lvl_quote = level_quotes.get(level, level_quotes[1])

        next_level_xp = next_level_requirement(level)
        xp_needed = max(next_level_xp - xp, 0)

        level_embed = discord.Embed(
            title="[ ✦ ]",
            description="𝙰𝚍𝚟𝚊𝚗𝚌𝚎𝚖𝚎𝚗𝚝 𝚁𝚎𝚌𝚘𝚛𝚍𝚎𝚍 \n",
            color=0xff000d,
        )
        level_embed.add_field(name="𝙿𝚛𝚘𝚖𝚘𝚝𝚒𝚘𝚗", value=f"<@{member.id}>", inline=True)
        level_embed.add_field(name="Level", value=f"{level}", inline=True)
        level_embed.add_field(name="XP", value=f"{xp}/{next_level_xp}", inline=True)
        level_embed.add_field(name="Next Level", value=f"{xp_needed} XP needed", inline=False)
        level_embed.add_field(
            name="",
            value=f"**𝙼𝚎𝚜𝚜𝚊𝚐𝚎 𝚁𝚎𝚌𝚎𝚒𝚟𝚎𝚍**\n*{lvl_quote}*",
            inline=False,
        )
        await interaction.response.send_message("Level-up embed preview:", embed=level_embed)

        milestone_quotes = {
            1: "You did good today. I left something small for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
            2: "I'm starting to notice you. Go check the message I left for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
            5: "You're learning quickly. I made sure to leave you something in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
            10: "Good behavior deserves attention. I left a message waiting for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
            20: "You're becoming reliable. I expect you'll read what I left for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
            30: "I like the way you respond to guidance. Go see what I wrote for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
            50: "You know what I expect from you now. There's a message for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
            75: "You belong exactly where I want you. Don't ignore the message I left in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
            100: "You don't need reminders anymore. Read what I left for you in <#1450107538019192832> <a:heartglitch:1449997688358572093>",
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

        prompt, image_url = event_prompt(1)
        obedience_embed = build_event_embed(prompt, image_url)
        await interaction.followup.send("Obedience event embed preview:", embed=obedience_embed)
    
    @bot.tree.command(name="throne", description="Send a Throne message with quote variations. Admin only.")
    async def throne(interaction: discord.Interaction):
        """Send a Throne message with quote variations."""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        from systems.tasks import send_daily_check_throne
        success = await send_daily_check_throne(interaction.guild)
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
    
    @bot.tree.command(name="levelrolecheck", description="Manually check that users do not have multiple level roles at once. Admin only.")
    async def levelrolecheck(interaction: discord.Interaction):
        """Manually check that users do not have multiple level roles at once."""
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
            
            level_roles = []
            for lvl, role_id in LEVEL_ROLE_MAP.items():
                role = guild.get_role(role_id)
                if role and role in member.roles:
                    level_roles.append((lvl, role))
            
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
        
        from core.data import get_level
        updated_count = 0
        for member in guild.members:
            if member.bot or any(int(r.id) in EXCLUDED_ROLE_SET for r in member.roles):
                continue
            
            guild_id = interaction.guild.id if interaction.guild else 0
            user_level = await get_level(member.id, guild_id=guild_id)
            if user_level > 0:
                try:
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
    
    @bot.tree.command(name="stopevents", description="Stop all automated messages (events, daily checks, etc.)")
    async def stopevents(interaction: discord.Interaction):
        """Stop all automated messages from being sent."""
        if not await check_admin_command_permissions(interaction):
            return
        
        current_state = get_automated_messages_enabled()
        if not current_state:
            embed = discord.Embed(
                title="⚠️ Automated Messages",
                description="Automated messages are already stopped.",
                color=0xff000d,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        set_automated_messages_enabled(False)
        
        embed = discord.Embed(
            title="🛑 Automated Messages Stopped",
            description="All automated messages have been stopped.\n\nThis includes:\n• Event scheduler\n• Daily check messages\n• All scheduled automated posts",
            color=0xff000d,
        )
        embed.set_footer(text="Use /startevents to re-enable automated messages.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @bot.tree.command(name="startevents", description="Re-enable all automated messages")
    async def startevents(interaction: discord.Interaction):
        """Re-enable all automated messages."""
        if not await check_admin_command_permissions(interaction):
            return
        
        current_state = get_automated_messages_enabled()
        if current_state:
            embed = discord.Embed(
                title="✅ Automated Messages",
                description="Automated messages are already enabled.",
                color=0x4ec200,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        set_automated_messages_enabled(True)
        
        embed = discord.Embed(
            title="✅ Automated Messages Enabled",
            description="All automated messages have been re-enabled.\n\nThis includes:\n• Event scheduler\n• Daily check messages\n• All scheduled automated posts",
            color=0x4ec200,
        )
        embed.set_footer(text="Use /stopevents to disable automated messages.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @bot.tree.command(name="askgifts", description="Send Christmas Eve gifts message to events channel")
    async def askgifts(interaction: discord.Interaction):
        """Send Christmas Eve gifts embed to events channel."""
        if not await check_admin_command_permissions(interaction):
            return
        
        events_channel = bot.get_channel(EVENT_CHANNEL_ID)
        
        if not events_channel:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Could not find events channel (ID: {EVENT_CHANNEL_ID})",
                color=0xff000d,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Christmas Eve Gifts",
            description="It's Christmas Eve, loves~\n\nI see some pups are already spoiling me beautifully.\nTheir names are lighting up my night \n\nYours could be next <:Islaseductive:1451296572255109210>\n\nDon't hold back.\nI know you want to see me smile~ 💝\n\n\n🎄 [Get Gifts](https://throne.com/lsla) 🎄",
            colour=0x750000,
        )
        embed.set_thumbnail(url="https://i.imgur.com/TplIFRf.png")
        embed.set_footer(
            text="Who's making my Christmas unforgettable?",
            icon_url="https://i.imgur.com/358yI3s.png"
        )
        
        try:
            await events_channel.send(content="@everyone", embed=embed)
            success_embed = discord.Embed(
                title="✅ Success",
                description=f"Christmas Eve gifts message sent to <#{EVENT_CHANNEL_ID}>",
                color=0x4ec200,
            )
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to send message to events channel: {e}",
                color=0xff000d,
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    # Onboarding configuration group
    configure_group = app_commands.Group(name="configure", description="Configure bot settings. Admin only.")
    
    onboarding_group = app_commands.Group(name="onboarding", parent=configure_group, description="Configure onboarding system")
    
    @onboarding_group.command(name="type", description="Configure onboarding channel or roles")
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
        """Configure onboarding channel or roles"""
        if not await check_admin_command_permissions(interaction):
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
                await interaction.response.send_message(f"Channel '{name}' not found. Please provide a channel mention, ID, or name.", ephemeral=True, delete_after=5)
                return
            
            set_onboarding_channel(channel.id)
            embed = discord.Embed(
                title="✅ Configuration Updated",
                description=f"Onboarding channel set to {channel.mention}",
                color=0x4ec200
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        elif config_type_value == "role":
            valid_roles = ["Unverified", "Verified", "Bad Pup"]
            if name not in valid_roles:
                await interaction.response.send_message(f"Invalid role type. Must be one of: {', '.join(valid_roles)}", ephemeral=True, delete_after=5)
                return
            
            if not serverrole:
                await interaction.response.send_message("Please provide a server role.", ephemeral=True, delete_after=5)
                return
            
            set_role(name, serverrole.id)
            embed = discord.Embed(
                title="✅ Configuration Updated",
                description=f"Onboarding role '{name}' set to {serverrole.mention}",
                color=0x4ec200
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
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
    
    # Roles configuration commands
    roles_group = app_commands.Group(name="roles", parent=configure_group, description="Configure role selection messages")
    
    @roles_group.command(name="send", description="Send a role selection message to a channel")
    @app_commands.describe(
        message="Type of role message to send",
        channel="Channel to send the message to"
    )
    @app_commands.choices(message=[
        app_commands.Choice(name="pronouns", value="pronouns"),
        app_commands.Choice(name="petnames", value="petnames"),
        app_commands.Choice(name="region", value="region"),
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
        else:
            await interaction.followup.send("Invalid message type. Must be: pronouns, petnames, or region.", ephemeral=True)
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
        else:
            await interaction.followup.send("Invalid message type. Must be: pronouns, petnames, or region.", ephemeral=True)
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
        """Set the introductions channel"""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
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
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @introductions_group.command(name="show", description="Show the current introductions channel")
    async def introductions_show(interaction: discord.Interaction):
        """Show the current introductions channel"""
        if not await check_admin_command_permissions(interaction):
            return
        
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    bot.tree.add_command(configure_group)
    
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

