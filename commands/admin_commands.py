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
from core.data import xp_data, get_level, get_xp, save_xp_data
from core.utils import next_level_requirement, get_timezone, USE_PYTZ, update_roles_on_level
from systems.events import (
    active_event, event_cooldown_until, events_enabled, start_obedience_event,
    clear_event_roles, build_event_embed, event_prompt
)
from systems.tasks import get_next_scheduled_time

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
    
    return True

def register_commands(bot_instance):
    """Register all admin commands with the bot"""
    global bot
    bot = bot_instance
    
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
        level = get_level(member.id)
        xp = get_xp(member.id)

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
            description="𝙰𝚍𝚟𝚊𝚗𝚌𝚎𝚖𝚎𝚗𝚝 𝚁𝚎𝚌𝚘𝚛𝚍𝚎𝚍 \n᲼᲼",
            color=0xff000d,
        )
        level_embed.add_field(name="𝙿𝚛𝚘𝚖𝚘𝚝𝚒𝚘𝚗", value=f"<@{member.id}>", inline=True)
        level_embed.add_field(name="Level", value=f"{level}", inline=True)
        level_embed.add_field(name="XP", value=f"{xp}/{next_level_xp}", inline=True)
        level_embed.add_field(name="Next Level", value=f"{xp_needed} XP needed", inline=False)
        level_embed.add_field(
            name="᲼᲼",
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
    
    @bot.tree.command(name="stopevents", description="Stop or start events from running. Admin only.")
    async def stopevents(interaction: discord.Interaction):
        """Stop or start events from running."""
        import systems.events as events
        
        if not await check_admin_command_permissions(interaction):
            return
        
        events.events_enabled = not events.events_enabled
        status = "enabled" if events.events_enabled else "disabled"
        await interaction.response.send_message(f"✅ Events are now **{status}**.", ephemeral=True, delete_after=10)
        print(f"Events {status} by {interaction.user.name}")
    
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
            
            user_level = get_level(member.id)
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

