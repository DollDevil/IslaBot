"""
Event handlers for Discord events - on_message, on_reaction, on_voice_state_update, etc.
"""
import discord
from discord.ext import commands
import datetime

from core.config import (
    REPLY_CHANNEL_ID, EVENT_PHASE2_CHANNEL_ID, EVENT_PHASE2_ALLOWED_ROLE,
    EVENT_PHASE3_SUCCESS_CHANNEL_ID, EVENT_PHASE3_SUCCESS_ROLES,
    EVENT_PHASE3_FAILED_CHANNEL_ID, EVENT_PHASE3_FAILED_ROLES,
    NON_XP_CATEGORY_IDS, NON_XP_CHANNEL_IDS, XP_TRACK_SET,
    EXCLUDED_ROLE_SET, VC_XP_TRACK_CHANNELS, VC_XP, MESSAGE_COOLDOWN,
    ALLOWED_GUILDS
)
from core.data import xp_data, save_xp_data
from systems.xp import add_xp
from core.utils import resolve_channel_id, resolve_category_id, get_channel_multiplier, get_reply_quote
from systems.events import active_event, handle_event_message, handle_event_reaction

# Global state
message_cooldowns = {}
vc_members_time = {}

# Bot instance (set by main.py)
bot = None

def set_bot(bot_instance):
    """Set the bot instance for this module"""
    global bot
    bot = bot_instance

async def on_message(message):
    """Handle incoming messages - XP tracking, event handling, reply system"""
    resolved_channel_id = resolve_channel_id(message.channel)
    print(f"[MESSAGE] {message.author.name} in #{message.channel} (ID: {resolved_channel_id}): {message.content[:50]}")
    
    if message.author.bot:
        print("  ↳ Skipped: Bot message")
        return

    if isinstance(message.author, discord.Member):
        if any(int(role.id) in EXCLUDED_ROLE_SET for role in message.author.roles):
            print(f"  ↳ Skipped: User has bot role")
            return

        # Channel permission checks for special event channels
        if resolved_channel_id == EVENT_PHASE2_CHANNEL_ID:
            opt_in_role = message.guild.get_role(EVENT_PHASE2_ALLOWED_ROLE)
            if opt_in_role and opt_in_role not in message.author.roles:
                print(f"  ↳ Blocked: User {message.author.name} doesn't have required role for Phase 2 channel")
                try:
                    await message.delete()
                except:
                    pass
                return
        
        if resolved_channel_id == EVENT_PHASE3_SUCCESS_CHANNEL_ID:
            has_success_role = any(int(role.id) in EVENT_PHASE3_SUCCESS_ROLES for role in message.author.roles)
            if not has_success_role:
                print(f"  ↳ Blocked: User {message.author.name} doesn't have required role for Success channel")
                try:
                    await message.delete()
                except:
                    pass
                return
        
        if resolved_channel_id == EVENT_PHASE3_FAILED_CHANNEL_ID:
            has_failed_role = any(int(role.id) in EVENT_PHASE3_FAILED_ROLES for role in message.author.roles)
            if not has_failed_role:
                print(f"  ↳ Blocked: User {message.author.name} doesn't have required role for Failure channel")
                try:
                    await message.delete()
                except:
                    pass
                return

    # Reply system for introduction channel
    if resolved_channel_id == REPLY_CHANNEL_ID and isinstance(message.author, discord.Member):
        quote = get_reply_quote(message.author)
        embed = discord.Embed(
            description=f"*{quote}*",
            color=0xff000d
        )
        try:
            await message.reply(embed=embed)
            print(f"  ↳ Replied to {message.author.name} with quote: {quote[:50]}...")
        except Exception as e:
            print(f"  ↳ Failed to reply: {e}")
        
        try:
            await message.add_reaction("❤️")
            print(f"  ↳ Added ❤️ reaction to message from {message.author.name}")
        except Exception as e:
            print(f"  ↳ Failed to add reaction: {e}")

    # Obedience event tracking - process BEFORE exclusion checks so event messages work in any channel
    await handle_event_message(message)

    # Skip excluded categories
    category_id = resolve_category_id(message.channel)
    if category_id in NON_XP_CATEGORY_IDS:
        print(f"  ↳ Skipped: Category excluded from XP ({category_id})")
        return
    if resolved_channel_id in NON_XP_CHANNEL_IDS:
        print(f"  ↳ Skipped: Channel excluded from XP ({resolved_channel_id})")
        return

    if resolved_channel_id in XP_TRACK_SET:
        print("  ↳ Channel is tracked")
        user_id = message.author.id
        current_time = datetime.datetime.now(datetime.UTC)
        
        # Track messages sent (excluding bot commands)
        is_bot_command = message.content.startswith('!') or (message.content.startswith('/') and len(message.content) > 1)
        if not is_bot_command:
            uid = str(user_id)
            if uid not in xp_data:
                xp_data[uid] = {
                    "xp": 0, "level": 1, "coins": 0,
                    "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
                    "times_gambled": 0, "total_wins": 0,
                    "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
                    "equipped_collar": None, "equipped_badge": None
                }
            if "messages_sent" not in xp_data[uid]:
                xp_data[uid]["messages_sent"] = 0
            xp_data[uid]["messages_sent"] = xp_data[uid].get("messages_sent", 0) + 1
        
        if user_id in message_cooldowns:
            time_since_last = (current_time - message_cooldowns[user_id]).total_seconds()
            if time_since_last < MESSAGE_COOLDOWN:
                print(f"  ↳ Cooldown active ({MESSAGE_COOLDOWN - time_since_last:.0f}s remaining)")
                return
        
        message_cooldowns[user_id] = current_time
        base_mult = get_channel_multiplier(resolved_channel_id)
        print(f"  ↳ ✅ Adding 10 XP to {message.author.name} (channel mult {base_mult}x)")
        await add_xp(message.author.id, 10, member=message.author, base_multiplier=base_mult)
    else:
        event_channels = [EVENT_PHASE2_CHANNEL_ID, EVENT_PHASE3_SUCCESS_CHANNEL_ID, EVENT_PHASE3_FAILED_CHANNEL_ID]
        if resolved_channel_id in event_channels:
            print(f"  ↳ Channel not tracked (event channel - XP tracking disabled)")
        else:
            print(f"  ↳ Channel not tracked (ID mismatch)")

async def on_voice_state_update(member, before, after):
    """Handle voice state updates - track VC time and Event 2 participation"""
    if member.bot:
        return
    if any(int(role.id) in EXCLUDED_ROLE_SET for role in getattr(member, "roles", [])):
        return

    if after.channel:
        cat_id = resolve_category_id(after.channel)
        if after.channel.id not in VC_XP_TRACK_CHANNELS:
            after_channel_allowed = False
        elif cat_id in NON_XP_CATEGORY_IDS or after.channel.id in NON_XP_CHANNEL_IDS:
            after_channel_allowed = False
        else:
            after_channel_allowed = True
    else:
        after_channel_allowed = False

    # Obedience event: track silent company presence
    if active_event and active_event.get("type") == 2 and active_event.get("join_times") is not None:
        join_times = active_event["join_times"]
        if after.channel and not before.channel:
            if after_channel_allowed:
                join_times[member.id] = datetime.datetime.now(datetime.UTC)
        if before.channel and not after.channel:
            join_times.pop(member.id, None)

    if after.channel and not before.channel:
        if after_channel_allowed and after.channel.id in VC_XP_TRACK_CHANNELS:
            vc_members_time[member.id] = {"time": datetime.datetime.now(datetime.UTC), "channel_id": after.channel.id}
        print(f"{member.name} joined VC: {after.channel.name}")

    elif before.channel and not after.channel:
        join_data = vc_members_time.pop(member.id, None)
        if join_data:
            join_time = join_data["time"]
            channel_id = join_data.get("channel_id", before.channel.id if before.channel else 0)
        else:
            join_time = None
            channel_id = before.channel.id if before.channel else 0
        if join_time and channel_id in VC_XP_TRACK_CHANNELS:
            seconds = (datetime.datetime.now(datetime.UTC) - join_time).total_seconds()
            minutes = int(seconds // 60)
            if minutes > 0:
                uid = str(member.id)
                if uid not in xp_data:
                    xp_data[uid] = {
                        "xp": 0, "level": 1, "coins": 0,
                        "messages_sent": 0, "vc_minutes": 0, "event_participations": 0,
                        "times_gambled": 0, "total_wins": 0,
                        "badges_owned": [], "collars_owned": [], "interfaces_owned": [],
                        "equipped_collar": None, "equipped_badge": None
                    }
                if "vc_minutes" not in xp_data[uid]:
                    xp_data[uid]["vc_minutes"] = 0
                xp_data[uid]["vc_minutes"] = xp_data[uid].get("vc_minutes", 0) + minutes
                save_xp_data()
                
                xp_gained = minutes * VC_XP
                base_mult = get_channel_multiplier(channel_id)
                await add_xp(member.id, xp_gained, member=member, base_multiplier=base_mult)
                print(f"Added {xp_gained} VC XP to {member.name} ({minutes} minutes) (channel mult {base_mult}x)")
    
    elif before.channel and after.channel and before.channel != after.channel:
        print(f"{member.name} switched from {before.channel.name} to {after.channel.name}")

async def on_raw_reaction_add(payload):
    """Handle reaction events for obedience events"""
    await handle_event_reaction(payload)

async def on_command_error(ctx, error):
    """Handle command errors gracefully"""
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.", delete_after=5)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("Could not find that member.", delete_after=5)
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Invalid argument provided.", delete_after=5)
    elif isinstance(error, commands.CommandNotFound):
        # Prefix commands have been removed - all commands are now slash commands
        pass
    else:
        print(f"Error: {error}")

async def on_guild_join(guild):
    """Automatically leave any guild that isn't in the allowed list."""
    if guild.id not in ALLOWED_GUILDS:
        try:
            await guild.leave()
            print(f'Left {guild.name} (ID: {guild.id}) - not in allowed guilds list')
        except Exception as e:
            print(f'Failed to leave {guild.name} (ID: {guild.id}): {e}')

async def on_member_remove(member):
    """Erase user's progress when they leave the server"""
    if member.guild.id not in ALLOWED_GUILDS:
        return
    
    user_id = str(member.id)
    if user_id in xp_data:
        del xp_data[user_id]
        save_xp_data()
        print(f"Erased progress for {member.name} (ID: {member.id}) - user left server")

