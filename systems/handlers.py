"""
Event handlers for Discord events - on_message, on_reaction, on_voice_state_update, etc.
"""
import discord
from discord.ext import commands
import datetime

from core.config import (
    EVENT_PHASE2_CHANNEL_ID, EVENT_PHASE2_ALLOWED_ROLE,
    EVENT_PHASE3_SUCCESS_CHANNEL_ID, EVENT_PHASE3_SUCCESS_ROLES,
    EVENT_PHASE3_FAILED_CHANNEL_ID, EVENT_PHASE3_FAILED_ROLES,
    NON_XP_CATEGORY_IDS, NON_XP_CHANNEL_IDS, XP_TRACK_SET,
    EXCLUDED_ROLE_SET, VC_XP_TRACK_CHANNELS, VC_XP, MESSAGE_COOLDOWN,
    ALLOWED_GUILDS
)
# V3 Progression: XP/Level system removed
from core.utils import resolve_channel_id, resolve_category_id, get_channel_multiplier
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
        
        # Check for Bad Pup role - handle submission messages
        from systems.onboarding import has_bad_pup_role, check_submission_text, send_rules_submission_correct, send_rules_submission_false
        if has_bad_pup_role(message.author):
            # Check if message matches submission text
            if check_submission_text(message.content):
                # Correct submission - verify user
                await send_rules_submission_correct(message, message.author)
                print(f"Bad Pup user {message.author.name} submitted correct text, verified")
            else:
                # Incorrect submission - send false message
                await send_rules_submission_false(message, message.author)
                print(f"Bad Pup user {message.author.name} submitted incorrect text")
            # Return early - Bad Pup users can't do anything else
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

    # Reaction system for introduction channel (reactions only, no messages)
    if isinstance(message.author, discord.Member) and message.guild:
        intro_channel_id = await get_introductions_channel_id(message.guild.id)
        if intro_channel_id and resolved_channel_id == intro_channel_id:
            try:
                await message.add_reaction("❤️")
                print(f"  ↳ Added ❤️ reaction to message from {message.author.name}")
            except Exception as e:
                print(f"  ↳ Failed to add reaction: {e}")
    
    # Introduction channel reply system
    await handle_introduction_reply(message)

    # Obedience event tracking - process BEFORE exclusion checks so event messages work in any channel
    await handle_event_message(message)

    # Track messages sent for ALL channels (excluding bot commands) - V3 progression
    # This happens before exclusion checks so all messages are counted
    user_id = message.author.id
    is_bot_command = message.content.startswith('!') or (message.content.startswith('/') and len(message.content) > 1)
    if not is_bot_command and isinstance(message.author, discord.Member):
        guild_id = message.guild.id
        channel_id = message.channel.id
        
        # Record message event (for order verification)
        is_reply = message.reference is not None and message.reference.resolved is not None
        replied_to_user_is_bot = False
        if is_reply and message.reference.resolved:
            if isinstance(message.reference.resolved, discord.Message):
                replied_to_user_is_bot = message.reference.resolved.author.bot
        
        from core.db import record_message_event, bump_message
        await record_message_event(guild_id, user_id, channel_id, is_reply, replied_to_user_is_bot)
        await bump_message(guild_id, user_id)
        print(f"  ↳ Tracked message for {message.author.name}")
    
    # Note: XP/Level system removed - progression now based on Coins, Rank, Activity, Orders

    # V3 Progression: Messages are tracked for Activity/WAS, not XP
    # XP/Level system removed - progression now based on Coins, Rank, Activity, Orders
    # Message tracking already done above via record_message()

# Introduction reply system functions
async def get_introductions_channel_id(guild_id: int):
    """Get configured introductions channel ID for a guild"""
    from core.db import fetchone
    row = await fetchone(
        "SELECT channel_id FROM introductions_config WHERE guild_id = ?",
        (guild_id,)
    )
    return row["channel_id"] if row else None

async def check_introduction_cooldown(guild_id: int, user_id: int) -> bool:
    """Check if user is on cooldown for introduction replies (6 hours)"""
    from core.db import fetchone
    row = await fetchone(
        "SELECT last_replied_at FROM introduction_replies WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    if not row:
        return False
    
    last_replied = datetime.datetime.fromisoformat(row["last_replied_at"].replace('Z', '+00:00'))
    six_hours_ago = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=6)
    return last_replied > six_hours_ago

async def update_introduction_cooldown(guild_id: int, user_id: int):
    """Update introduction reply cooldown"""
    from core.db import execute
    now = datetime.datetime.now(datetime.UTC).isoformat()
    await execute(
        """INSERT OR REPLACE INTO introduction_replies (guild_id, user_id, last_replied_at)
           VALUES (?, ?, ?)""",
        (guild_id, user_id, now)
    )

async def get_user_region(member: discord.Member) -> str:
    """Get user's region from their role selection (EMEA, APAC, AMERICAS, UNSPECIFIED)"""
    from core.db import fetchone
    row = await fetchone(
        """SELECT item_id FROM inventory_items 
           WHERE guild_id = ? AND user_id = ? AND item_type = ? 
           AND item_id IN ('emea', 'apac', 'americas')""",
        (member.guild.id, member.id, "region")
    )
    if row:
        return row["item_id"].upper()  # EMEA, APAC, AMERICAS
    return "UNSPECIFIED"

async def get_user_petname(member: discord.Member) -> tuple:
    """Get user's petname selection (petname string or None, has_petname bool)"""
    from core.db import fetchone
    row = await fetchone(
        """SELECT item_id FROM inventory_items 
           WHERE guild_id = ? AND user_id = ? AND item_type = ? 
           AND item_id IN ('kitten', 'puppy', 'pet')""",
        (member.guild.id, member.id, "petname")
    )
    if row:
        return (row["item_id"], True)  # Return lowercase petname
    return (None, False)

def get_user_local_time_bucket(region: str) -> str:
    """Get user's local time bucket: early, daytime, or late"""
    if region == "UNSPECIFIED":
        return "daytime"
    
    # Map regions to UTC offsets (simplified - fixed offsets)
    # EMEA: UTC+2, APAC: UTC+8, AMERICAS: UTC-5
    offset_map = {
        "EMEA": 2,
        "APAC": 8,
        "AMERICAS": -5,
    }
    
    offset = offset_map.get(region, 0)
    
    # Get UTC time and add offset
    utc_now = datetime.datetime.now(datetime.UTC)
    local_time = utc_now + datetime.timedelta(hours=offset)
    hour = local_time.hour
    
    if 5 <= hour < 12:
        return "early"
    elif hour >= 12:
        return "daytime"
    else:  # 0-4
        return "late"

def classify_intro_length(content: str) -> str:
    """Classify introduction length: short, medium, or long"""
    # Remove whitespace for character count
    content_no_ws = ''.join(content.split())
    length = len(content_no_ws)
    
    if length < 120:
        return "short"
    elif length < 350:
        return "medium"
    else:
        return "long"

def select_introduction_quote(petname: str, has_petname: bool, length: str, time_bucket: str) -> str:
    """Select introduction quote based on parameters"""
    quotes = {
        # Petname quotes
        ("petname", "short", "daytime"): "A new <petname> with a quick introduction. I would've liked reading more~",
        ("petname", "short", "late"): "Short introduction so late at night — you are one interesting <petname>. Btw... they say nighttime is the best time to try my programs~",
        ("petname", "short", "early"): "Short and sweet introduction — good {petname}. It's pretty early for you, isn't it? Have you had your morning coffee yet? I'd loooove a coffee right now... share some through Throne, would you~ 💋",
        ("petname", "medium", "daytime"): "A new <petname> with a solid introduction. I enjoyed reading what you chose to share, now go run my programs~",
        ("petname", "medium", "late"): "An introduction so late at night? You are one interesting <petname>. Btw... they say nighttime is the best time to try my programs~",
        ("petname", "medium", "early"): "I liked your introduction — good {petname}. It's pretty early for you though, isn't it? Have you had your morning coffee yet? I'd loooove a coffee right now... share some through Throne, would you~ 💋",
        ("petname", "long", "daytime"): "Long and open introduction — my kind of <petname>. Your words already have me intrigued.",
        ("petname", "long", "late"): "So many words this late at night — you pour yourself out beautifully, <petname>. Btw... they say nighttime is the best time to try my programs~",
        ("petname", "long", "early"): "Long intro this early in the morning — such an eager {petname}. You woke up ready to please. Now go send your goddess a coffee through Throne~ 💋",
        
        # No petname quotes
        ("no_petname", "short", "daytime"): "A new user with a quick introduction. I would've liked reading more~",
        ("no_petname", "short", "late"): "Short introduction so late at night — you are one interesting person. Btw... they say nighttime is the best time to try my programs~",
        ("no_petname", "short", "early"): "Short and sweet introduction — I like that. It's pretty early for you, isn't it? Have you had your morning coffee yet? I see you woke up ready to please. Now go send your goddess a coffee through Throne~ 💋",
        ("no_petname", "medium", "daytime"): "A new user with a solid introduction. I enjoyed reading what you chose to share, now go run my programs~",
        ("no_petname", "medium", "late"): "An introduction so late at night? You are one interesting person. Btw... they say nighttime is the best time to try my programs~",
        ("no_petname", "medium", "early"): "I liked your introduction. It's pretty early for you though, isn't it? Have you had your morning coffee yet? I'd loooove a coffee right now... share some through Throne, would you~ 💋",
        ("no_petname", "long", "daytime"): "Long and open introduction — just the way I like it. Your words already have me intrigued.",
        ("no_petname", "long", "late"): "So many words this late at night — you pour yourself out beautifully. Btw... they say nighttime is the best time to try my programs~",
        ("no_petname", "long", "early"): "Long intro this early in the morning? I see you woke up ready to please. Now go send your goddess a coffee through Throne~ 💋",
    }
    
    petname_key = "petname" if has_petname else "no_petname"
    key = (petname_key, length, time_bucket)
    quote = quotes.get(key, quotes.get((petname_key, length, "daytime"), "Welcome."))
    
    # Substitute petname placeholders
    if has_petname and petname:
        quote = quote.replace("<petname>", petname)
        quote = quote.replace("{petname}", petname)
    
    return quote

class IntroductionReplyView(discord.ui.View):
    """View with gift button and conditional throne/programs buttons"""
    def __init__(self, guild_id: int, user_id: int, is_early: bool, is_late: bool):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.user_id = user_id
        
        # Gift button (always)
        gift_button = discord.ui.Button(
            emoji="🎁",
            label="Gift from Isla",
            style=discord.ButtonStyle.primary,
            custom_id=f"intro_gift_{guild_id}_{user_id}"
        )
        gift_button.callback = self.gift_callback
        self.add_item(gift_button)
        
        # Throne button (only if early)
        if is_early:
            throne_button = discord.ui.Button(
                emoji="☕",
                label="Throne",
                style=discord.ButtonStyle.link,
                url="https://throne.com/lsla"
            )
            self.add_item(throne_button)
        
        # Programs button (only if late)
        if is_late:
            programs_button = discord.ui.Button(
                emoji="👾",
                label="Programs",
                style=discord.ButtonStyle.link,
                url="https://discord.com/channels/1407164448132698213/1449922902760882307"
            )
            self.add_item(programs_button)
    
    async def gift_callback(self, interaction: discord.Interaction):
        """Handle gift button click"""
        from core.db import fetchone, execute
        from core.data import add_coins
        
        # Check if already claimed
        row = await fetchone(
            "SELECT claimed_at FROM gift_claims WHERE guild_id = ? AND user_id = ?",
            (self.guild_id, self.user_id)
        )
        
        if row:
            await interaction.response.send_message("🎁 You've already claimed your gift!", ephemeral=True)
            return
        
        # Get user region and petname for bonus calculation
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        region = await get_user_region(member) if member else "UNSPECIFIED"
        petname, has_petname = await get_user_petname(member) if member else (None, False)
        
        # Calculate coin reward
        coins = 100
        if has_petname:
            coins += 25
        if region != "UNSPECIFIED":
            coins += 25
        
        # Award coins
        await add_coins(self.user_id, coins, guild_id=self.guild_id, reason="intro_gift", meta={"petname": has_petname, "region": region})
        
        # Mark as claimed
        now = datetime.datetime.now(datetime.UTC).isoformat()
        await execute(
            "INSERT INTO gift_claims (guild_id, user_id, claimed_at) VALUES (?, ?, ?)",
            (self.guild_id, self.user_id, now)
        )
        
        embed = discord.Embed(description=f"🎁 Claimed **+{coins}** coins")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def handle_introduction_reply(message):
    """Handle introduction channel replies"""
    if not isinstance(message.author, discord.Member) or message.author.bot:
        return
    
    if not message.guild:
        return
    
    # Skip bot commands
    if message.content.startswith('!') or (message.content.startswith('/') and len(message.content) > 1):
        return
    
    # Check if this is the introductions channel
    guild_id = message.guild.id
    intro_channel_id = await get_introductions_channel_id(guild_id)
    
    if not intro_channel_id or message.channel.id != intro_channel_id:
        return
    
    # Check cooldown
    if await check_introduction_cooldown(guild_id, message.author.id):
        return
    
    # Get user region and petname
    region = await get_user_region(message.author)
    petname, has_petname = await get_user_petname(message.author)
    
    # Get time bucket
    time_bucket = get_user_local_time_bucket(region)
    is_early = (time_bucket == "early")
    is_late = (time_bucket == "late")
    
    # Classify intro length
    length = classify_intro_length(message.content)
    
    # Select quote
    quote = select_introduction_quote(petname, has_petname, length, time_bucket)
    
    # Build embed
    embed = discord.Embed(description=quote)
    embed.set_author(
        name="𝚂𝚢𝚜𝚝𝚎𝚖 𝙼𝚎𝚜𝚜𝚊𝚐𝚎",
        icon_url="https://i.imgur.com/irmCXhw.gif"
    )
    
    # Create view
    view = IntroductionReplyView(guild_id, message.author.id, is_early, is_late)
    
    # Send as DM (preferred), fallback to channel reply
    try:
        await message.author.send(embed=embed, view=view)
        print(f"  ↳ Sent introduction reply DM to {message.author.name}")
    except discord.Forbidden:
        # DM failed, send as channel reply
        try:
            reply_msg = await message.reply(
                content=f"<@{message.author.id}>",
                embed=embed,
                view=view,
                delete_after=20
            )
            print(f"  ↳ Sent introduction reply in channel to {message.author.name} (DM blocked)")
        except Exception as e:
            print(f"  ↳ Failed to send introduction reply: {e}")
            return
    
    # Update cooldown
    await update_introduction_cooldown(guild_id, message.author.id)

async def on_voice_state_update(member, before, after):
    """Handle voice state changes and track VC sessions"""
    # Record voice session changes for order verification
    if member.bot:
        return
    
    guild_id = member.guild.id if member.guild else None
    user_id = member.id
    
    if not guild_id:
        return
    
    from core.db import execute, _now_iso
    from datetime import datetime
    
    now_ts = int(datetime.now(datetime.UTC).timestamp())
    
    # User joined a voice channel
    if not before.channel and after.channel:
        # Record join time
        await execute(
            """INSERT INTO voice_sessions (guild_id, user_id, join_ts, leave_ts, minutes)
               VALUES (?, ?, ?, NULL, 0)""",
            (guild_id, user_id, now_ts)
        )
    
    # User left a voice channel
    elif before.channel and not after.channel:
        # Find active session and close it
        session = await execute(
            """SELECT join_ts FROM voice_sessions 
               WHERE guild_id = ? AND user_id = ? AND leave_ts IS NULL
               ORDER BY join_ts DESC LIMIT 1""",
            (guild_id, user_id)
        )
        # Note: execute doesn't return rows, need to use fetchone
        from core.db import fetchone
        session = await fetchone(
            """SELECT join_ts FROM voice_sessions 
               WHERE guild_id = ? AND user_id = ? AND leave_ts IS NULL
               ORDER BY join_ts DESC LIMIT 1""",
            (guild_id, user_id)
        )
        
        if session:
            join_ts = session["join_ts"]
            session_minutes = max(1, (now_ts - join_ts) // 60)  # Minimum 1 minute
            
            # Close session
            await execute(
                """UPDATE voice_sessions SET leave_ts = ?, minutes = ?
                   WHERE guild_id = ? AND user_id = ? AND join_ts = ? AND leave_ts IS NULL""",
                (now_ts, session_minutes, guild_id, user_id, join_ts)
            )
            
            # Update activity_daily
            from core.db import add_vc_minutes
            await add_vc_minutes(guild_id, user_id, session_minutes)
            
            print(f"  ↳ Recorded VC session: {member.name} - {session_minutes} minutes")
    
    # Continue with existing voice tracking logic
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
                guild_id = member.guild.id
                from core.data import record_vc_minutes
                await record_vc_minutes(guild_id, member.id, minutes)
                
                # V3 Progression: VC minutes tracked for Activity/WAS, not XP
                print(f"Tracked {minutes} VC minutes for {member.name}")
    
    elif before.channel and after.channel and before.channel != after.channel:
        print(f"{member.name} switched from {before.channel.name} to {after.channel.name}")

async def on_raw_reaction_add(payload):
    """Handle reaction events for obedience events and order verification"""
    # Record reaction event for order verification
    if payload.guild_id and payload.user_id:
        guild_id = payload.guild_id
        user_id = payload.user_id
        
        # Check if user is a bot
        guild = bot.get_guild(guild_id) if bot else None
        if guild:
            member = guild.get_member(user_id)
            if member and not member.bot:
                channel_id = payload.channel_id
                emoji = payload.emoji
                message_id = payload.message_id
                
                # Check if channel is a forum channel
                channel = guild.get_channel(channel_id)
                is_forum = isinstance(channel, discord.ForumChannel) if channel else False
                
                from core.db import record_reaction_event, bump_reaction
                await record_reaction_event(guild_id, user_id, channel_id, emoji, message_id, is_forum)
                await bump_reaction(guild_id, user_id)
                print(f"  ↳ Recorded reaction event for user {member.name if member else user_id}")
    
    # Handle event reactions
    await handle_event_reaction(payload)

async def on_app_command_completion(interaction: discord.Interaction, command):
    """Handle app command completion - record command event for order verification"""
    if interaction.user.bot:
        return
    
    if not interaction.guild:
        return
    
    guild_id = interaction.guild.id
    user_id = interaction.user.id
    command_name = command.name if hasattr(command, 'name') else str(command)
    channel_id = interaction.channel.id if interaction.channel else None
    
    if channel_id:
        from core.db import record_command_event
        await record_command_event(guild_id, user_id, command_name, channel_id)
        print(f"  ↳ Recorded command event: {command_name} for user {interaction.user.name}")

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
    
    # Note: User data is stored in DB - we don't delete on leave (historical data is preserved)
    # If you want to delete user data on leave, uncomment below:
    # from core.db import execute
    # guild_id = member.guild.id
    # user_id = member.id
    # await execute("DELETE FROM user_profile WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    # await execute("DELETE FROM economy_balance WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    # ... (delete from other tables as needed)
    print(f"Member {member.name} (ID: {member.id}) left server - data preserved in DB")

async def on_member_join(member):
    """Handle new member join - give Unverified role and send welcome message"""
    if member.guild.id not in ALLOWED_GUILDS:
        return
    
    if member.bot:
        return
    
    from systems.onboarding import (
        get_role_id, send_onboarding_welcome, has_bad_pup_role
    )
    
    # Give Unverified role
    unverified_role_id = get_role_id("Unverified")
    if unverified_role_id:
        role = member.guild.get_role(unverified_role_id)
        if role:
            try:
                await member.add_roles(role, reason="Onboarding: New member")
                print(f"Added Unverified role to {member.name}")
            except Exception as e:
                print(f"Error adding Unverified role to {member.name}: {e}")
    
    # Send welcome message
    try:
        await send_onboarding_welcome(member)
        print(f"Sent welcome message for {member.name}")
    except Exception as e:
        print(f"Error sending welcome message for {member.name}: {e}")

