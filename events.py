"""
Event system for obedience events
"""
import discord
import asyncio
import datetime
import random
import secrets
import re
import os
from discord import FFmpegPCMAudio

from config import (
    EVENT_DURATION_SECONDS, EVENT_COOLDOWN_SECONDS, EVENT_CHANNEL_ID,
    EVENT_PHASE2_CHANNEL_ID, EVENT_PHASE3_FAILED_CHANNEL_ID, EVENT_PHASE3_SUCCESS_CHANNEL_ID,
    EVENT_2_VC_CHANNELS, EVENT_2_AUDIO, EVENT_REWARDS, EVENT_TIER_MAP,
    EVENT_4_WOOF_ROLE, EVENT_4_MEOW_ROLE, EVENT_4_WOOF_CHANNEL_ID, EVENT_4_MEOW_CHANNEL_ID,
    EVENT_7_OPT_IN_ROLE, EVENT_7_SUCCESS_ROLE, EVENT_7_FAILED_ROLE,
    EVENT_CLEANUP_ROLES, COLLECTIVE_THRESHOLD, EXCLUDED_ROLE_SET
)
from data import increment_event_participation, xp_data
from xp import add_xp
from utils import resolve_channel_id

# Global state
active_event = None
event_cooldown_until = None
events_enabled = True
last_event_times_today = set()
event_scheduler_task = None

# Bot instance (set by main.py)
bot = None

def set_bot(bot_instance):
    """Set the bot instance for this module"""
    global bot
    bot = bot_instance

async def clear_event_roles():
    """Clear all event-related roles from all members when no events are active."""
    global active_event
    if active_event:
        return  # Don't clear roles if an event is active
    
    for guild in bot.guilds:
        for role_id in EVENT_CLEANUP_ROLES:
            role = guild.get_role(role_id)
            if not role:
                continue
            
            members_with_role = [m for m in guild.members if role in m.roles]
            if members_with_role:
                try:
                    for member in members_with_role:
                        await member.remove_roles(role, reason="Event cleanup - no active events")
                    print(f"Cleared {len(members_with_role)} members from role {role.name} ({role_id})")
                except Exception as e:
                    print(f"Failed to clear role {role.name} ({role_id}): {e}")

def build_event_embed(description: str, image_url: str = None) -> discord.Embed:
    """Build event embed with description and optional image."""
    embed = discord.Embed(
        description=f"*{description}*",
        color=0xff000d,
    )
    if image_url:
        embed.set_image(url=image_url)
    return embed

def event_prompt(event_type: int) -> tuple:
    """Get event prompt and image URL. Returns (prompt, image_url)."""
    prompts = {
        1: [
            ("I don't see enough messages sent… are you being shy now?", "https://i.imgur.com/r4ovg5g.png"),
            ("I don't see enough messages sent… that's not very impressive.", "https://i.imgur.com/r4ovg5g.png"),
            ("I don't see enough messages sent… you can type more than that.", "https://i.imgur.com/r4ovg5g.png"),
            ("It's so quiet in here… entertain me.", "https://i.imgur.com/r4ovg5g.png"),
            ("It's so quiet in here… did you forget how to type?", "https://i.imgur.com/r4ovg5g.png"),
        ],
        2: [
            ("You can join voice and stay quiet. I don't mind.", "https://i.imgur.com/773NSZA.png"),
            ("Come join me in voice. Silence is fine.", "https://i.imgur.com/773NSZA.png"),
            ("Sit with me in voice for a bit. That's enough.", "https://i.imgur.com/773NSZA.png"),
        ],
        3: [
            ("Don't overthink it. Would you give me your heart?", "https://i.imgur.com/K9BVKMv.png"),
            ("You can answer without words. Your heart will do.", "https://i.imgur.com/K9BVKMv.png"),
            ("It's simple. Would you offer me your heart?", "https://i.imgur.com/K9BVKMv.png"),
        ],
        4: [
            ("Choose wisely.", None),
        ],
        5: [
            ("Are you still with me?", None),
        ],
        6: [
            ("Choose wisely.", "https://i.imgur.com/zAg5z06.png"),
        ],
        7: [
            ("Are you there my doggies?\n\nI have a little something for you.", "https://i.imgur.com/XjGS6Gk.png"),
        ],
    }
    choices = prompts.get(event_type, [("...", None)])
    return random.choice(choices)

def event_6_prompt() -> tuple:
    """Get Event 6 prompt (Photo Reaction)."""
    variations = [
        ("I know you're there, sitting quietly in my presence, and yet you haven't acknowledged the goddess before you.\n\n*Don't stay silent now when you know exactly how to address me.*", "https://i.imgur.com/MHIPpcn.png"),
        ("I know you're there, quiet in my presence, fully aware of the goddess before you—your silence is already an answer, but I expect you to speak.\n\n*Don't stay silent now when you know exactly how to address me.*", "https://i.imgur.com/MHIPpcn.png"),
        ("You're sitting there, feeling my presence without question, and yet you haven't acknowledged the goddess who stands above you.\n\n*Don't stay silent now when you know exactly how to address me.*", "https://i.imgur.com/MHIPpcn.png"),
        ("I like watching you play my programs, seeing where your attention lingers and what you're willing to give up for it. There's something amusing about the way you pretend it's just curiosity, just a little spending here and there, when I can see how easily you indulge. I don't push—you do that all on your own. I simply notice, quietly pleased, as you decide what I'm worth to you.\n\n*Don't stay silent now when you know exactly how to address me.*", "https://i.imgur.com/xd9HPMa.png", 0.05),  # 5% chance
        ("I enjoy watching how easily you commit when something belongs to me. You open my programs, you stay longer than you intended, and you spend without needing to be told—because you want to. I see the satisfaction in that choice, the quiet thrill of giving value to something you respect. It isn't about taking from you; it's about watching you decide what I'm worth, again and again. That certainty never surprises me. It's exactly how this was always going to go.\n\n*Don't stay silent now when you know exactly how to address me.*", "https://i.imgur.com/4qnFaHF.png", 0.005),  # 0.5% chance
    ]
    # Weighted random selection
    rand = random.random()
    if rand < 0.005:
        return variations[4]  # 0.5% chance
    elif rand < 0.05:
        return variations[3]  # 5% chance
    else:
        return random.choice(variations[:3])  # Equal chance for first 3

def choose_collective_question():
    """Choose random question for Event 7 Phase 2."""
    questions = [
        ("What program does Isla Rebrand affect?", "steam"),
        ("What's the main theme of Isla Hearts?", ["level drain", "draining level", "draining levels"]),
        ("What's Isla's most extreme file?", "islaware"),
        ("What was Isla's first program?", ["islaexe", "isla.exe"]),
        ("When did IslaOS 2.0 launch?", ["13/12/2025", "12/13/2025"]),
        ("How much does rebrand cost?", "$15"),
        ("How much is islahearts?", "$20"),
        ("How much does islaware cost?", "$30"),
        ("What is the price of slots?", "$20"),
        ("What does isla.exe cost?", "$15"),
        ("What year did isla begin?", "2025"),
        ("What month was isla founded?", "july"),
        ("What is my favorite drink?", ["dr pepper", "drpepper", "dr.pepper"]),
        ("What is my favorite color?", "red"),
        ("What is my favorite anime?", "one piece"),
        ("What is my favorite anime character?", "makima"),
        ("What gaming genre do i enjoy most?", ["horror", "rpg"]),
        ("What platform does isla.exe use?", "windows"),
        ("What is the nickname I gave you?", ["dogs", "pups", "puppies", "dog", "pup", "puppy"]),
        ("What title do i prefer?", "goddess"),
        ("What time do i usually appear?", "midnight"),
        ("What word do i repeat often?", "send"),
    ]
    # Use secrets.choice for cryptographically secure random selection
    return secrets.choice(questions)

async def check_event7_phase1_threshold(state):
    """Check Event 7 Phase 1 threshold after 1 minute."""
    await asyncio.sleep(60)  # Wait 1 minute
    global active_event
    
    if active_event != state or state.get("phase") != 1:
        return
    
    reactor_count = len(state.get("reactors", set()))
    if reactor_count >= COLLECTIVE_THRESHOLD and not state.get("threshold_reached"):
        guild = bot.get_guild(state["guild_id"])
        if not guild:
            return
        
        channel = guild.get_channel(state["channel_id"])
        if not channel:
            return
        
        try:
            event_message = await channel.fetch_message(state["message_id"])
            embed = discord.Embed(
                description="*Good. I have what I need.\nThe door is open—for those who kept up.*",
                color=0xff000d,
            )
            await event_message.reply(embed=embed)
            state["threshold_reached"] = True
            print(f"Event 7 Phase 1: {reactor_count} reactions after 1 minute - threshold reached")
            # Escalate to Phase 2
            await escalate_collective_event(guild)
        except Exception as e:
            print(f"Failed to send Event 7 Phase 1 threshold message: {e}")

async def end_event4_phase1(state):
    """End Event 4 Phase 1 after 1 minute and start Phase 2."""
    await asyncio.sleep(60)  # 1 minute
    global active_event
    if active_event != state:
        return
    
    guild = bot.get_guild(state["guild_id"])
    if not guild:
        return
    
    # Start Phase 2
    await start_event4_phase2(guild, state)

async def start_event4_phase2(guild, state):
    """Start Event 4 Phase 2 - send messages to Woof and Meow channels."""
    global active_event
    if active_event != state:
        return
    
    state["phase"] = 2
    state["phase2_started"] = True
    state["answered"] = set()  # Track who has answered in Phase 2
    
    # Send message to Woof channel
    woof_channel = guild.get_channel(EVENT_4_WOOF_CHANNEL_ID)
    if woof_channel:
        try:
            woof_embed = build_event_embed("*Who's a good puppy?*", "https://i.imgur.com/yHTrhB4.png")
            await woof_channel.send("@everyone", embed=woof_embed)
            print(f"Event 4 Phase 2: Sent message to Woof channel")
        except Exception as e:
            print(f"Failed to send Event 4 Phase 2 message to Woof channel: {e}")
    
    # Send message to Meow channel
    meow_channel = guild.get_channel(EVENT_4_MEOW_CHANNEL_ID)
    if meow_channel:
        try:
            meow_embed = build_event_embed("*Who's a good kitty?*", "https://i.imgur.com/JfoxREn.png")
            await meow_channel.send("@everyone", embed=meow_embed)
            print(f"Event 4 Phase 2: Sent message to Meow channel")
        except Exception as e:
            print(f"Failed to send Event 4 Phase 2 message to Meow channel: {e}")

async def end_event7_phase2(state):
    """End Event 7 Phase 2 after 1 minute."""
    await asyncio.sleep(60)  # 1 minute
    global active_event
    if active_event != state:
        return
    
    guild = bot.get_guild(state["guild_id"])
    if not guild:
        return
    
    # Remove opt-in role from all users who have it
    opt_in_role = guild.get_role(EVENT_7_OPT_IN_ROLE)
    if opt_in_role:
        for member in guild.members:
            if opt_in_role in member.roles:
                try:
                    await member.remove_roles(opt_in_role, reason="Event 7 Phase 2 ended")
                    print(f"  ↳ Removed opt-in role from {member.name}")
                except Exception as e:
                    print(f"  ↳ Failed to remove opt-in role from {member.name}: {e}")
    
    # Phase 2 ended, now start Phase 3
    await handle_event7_phase3(guild, state)

async def end_event7_phase3(state):
    """End Event 7 Phase 3 after 2 minutes and remove Phase 3 roles."""
    await asyncio.sleep(120)  # 2 minutes
    global active_event, event_cooldown_until
    if active_event != state:
        return
    
    guild = bot.get_guild(state["guild_id"])
    if guild:
        # Remove Phase 3 roles (success and failed roles)
        success_role = guild.get_role(EVENT_7_SUCCESS_ROLE)
        failed_role = guild.get_role(EVENT_7_FAILED_ROLE)
        
        if success_role:
            for member in guild.members:
                if success_role in member.roles:
                    try:
                        await member.remove_roles(success_role, reason="Event 7 Phase 3 ended")
                        print(f"  ↳ Removed success role from {member.name}")
                    except Exception as e:
                        print(f"  ↳ Failed to remove success role from {member.name}: {e}")
        
        if failed_role:
            for member in guild.members:
                if failed_role in member.roles:
                    try:
                        await member.remove_roles(failed_role, reason="Event 7 Phase 3 ended")
                        print(f"  ↳ Removed failed role from {member.name}")
                    except Exception as e:
                        print(f"  ↳ Failed to remove failed role from {member.name}: {e}")
    
    # End the event
    active_event = None
    event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=EVENT_COOLDOWN_SECONDS)
    print("Event 7 Phase 3 ended")
    
    # Clear event roles when no events are active
    await clear_event_roles()

# Import send_tier3_pre_announcement from tasks (circular import handled)
def _get_send_tier3_pre_announcement():
    """Lazy import to avoid circular dependency"""
    from tasks import send_tier3_pre_announcement
    return send_tier3_pre_announcement

async def start_obedience_event(ctx_or_guild, event_type: int, channel=None):
    """Start an obedience event (1-7). Only one can run at a time.
    Can accept either a context object, interaction object, or a guild object with optional channel."""
    global active_event, event_cooldown_until, events_enabled
    
    # Check if events are enabled (manual commands can still run)
    is_manual_command = hasattr(ctx_or_guild, 'send') or hasattr(ctx_or_guild, 'response')
    if not events_enabled and not is_manual_command:
        # Automated events are disabled, but manual commands can still run
        return
    
    if active_event:
        if is_manual_command:
            if hasattr(ctx_or_guild, 'response'):
                await ctx_or_guild.response.send_message("An obedience event is already running.", ephemeral=True)
            elif hasattr(ctx_or_guild, 'send'):
                await ctx_or_guild.send("An obedience event is already running.")
        return
    
    # Manual commands can override cooldown, automated events cannot
    if event_cooldown_until and datetime.datetime.now(datetime.UTC) < event_cooldown_until:
        if is_manual_command:
            event_cooldown_until = None
            print("Manual event command overrode cooldown")
            if hasattr(ctx_or_guild, 'response'):
                await ctx_or_guild.response.send_message("✅ Manual event command - cooldown overridden.", ephemeral=True, delete_after=3)
            elif hasattr(ctx_or_guild, 'send'):
                await ctx_or_guild.send("✅ Manual event command - cooldown overridden.", delete_after=3)
            event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=1800)
            print(f"⏰ Manual event cooldown set: No other events will start for 30 minutes (until {event_cooldown_until.strftime('%H:%M:%S UTC')})")
        else:
            return
    elif is_manual_command:
        event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=1800)
        print(f"⏰ Manual event cooldown set: No other events will start for 30 minutes (until {event_cooldown_until.strftime('%H:%M:%S UTC')})")
    
    # Get guild and event channel
    if hasattr(ctx_or_guild, 'guild'):
        guild = ctx_or_guild.guild
    else:
        guild = ctx_or_guild
    
    event_channel = channel or guild.get_channel(EVENT_CHANNEL_ID)
    if not event_channel:
        if hasattr(ctx_or_guild, 'response'):
            await ctx_or_guild.response.send_message(f"Event channel not found (ID: {EVENT_CHANNEL_ID})", ephemeral=True)
        elif hasattr(ctx_or_guild, 'send'):
            await ctx_or_guild.send(f"Event channel not found (ID: {EVENT_CHANNEL_ID})")
        print(f"Event channel not found (ID: {EVENT_CHANNEL_ID})")
        return
    
    # For manual Tier 3 events, send pre-announcement first
    event_tier = EVENT_TIER_MAP.get(event_type)
    if is_manual_command and event_tier == 3:
        try:
            send_tier3 = _get_send_tier3_pre_announcement()
            await send_tier3(guild)
            await asyncio.sleep(60)
        except Exception as e:
            print(f"Failed to send Tier 3 pre-announcement: {e}")
    
    # Get prompt and image
    prompt, image_url = event_prompt(event_type)
    embed = build_event_embed(prompt, image_url)
    
    # Add footers
    if event_type == 1:
        embed.set_footer(text="Double XP for 5 minutes")
    elif event_type == 2:
        embed.set_footer(text="Join Voice Chat for XP")
    elif event_type == 3:
        embed.set_footer(text="React for XP")
    
    # Send with @everyone mention
    try:
        message = await event_channel.send("@everyone", embed=embed)
    except Exception as e:
        if hasattr(ctx_or_guild, 'response'):
            await ctx_or_guild.response.send_message(f"Failed to send event message: {e}", ephemeral=True)
        elif hasattr(ctx_or_guild, 'send'):
            await ctx_or_guild.send(f"Failed to send event message: {e}")
        print(f"Failed to send event message: {e}")
        return

    state = {
        "type": event_type,
        "channel_id": event_channel.id,
        "guild_id": guild.id,
        "message_id": message.id,
        "started_at": datetime.datetime.now(datetime.UTC),
        "phase": 1,
        "participants": set(),
        "reactors": set(),
        "message_cooldowns": {},
    }

    # Event-specific setup
    if event_type == 2:  # Silent Company
        join_times = {}
        for vc_id in EVENT_2_VC_CHANNELS:
            vc = guild.get_channel(vc_id)
            if vc:
                for member in vc.members:
                    if member.bot or any(int(r.id) in EXCLUDED_ROLE_SET for r in member.roles):
                        continue
                    join_times[member.id] = state["started_at"]
        state["join_times"] = join_times
        
        if EVENT_2_VC_CHANNELS:
            vc_id = EVENT_2_VC_CHANNELS[0]
            vc = guild.get_channel(vc_id)
            if vc:
                try:
                    if guild.voice_client:
                        try:
                            if guild.voice_client.is_playing():
                                guild.voice_client.stop()
                            await guild.voice_client.disconnect()
                            print(f"Disconnected from existing voice connection before joining Event 2 VC")
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            print(f"Error disconnecting from existing VC: {e}")
                    
                    print(f"Attempting to join voice channel {vc_id} ({vc.name})")
                    voice_client = await vc.connect()
                    state["bot_vc"] = vc_id
                    state["voice_client"] = voice_client
                    print(f"✅ Successfully joined voice channel {vc.name} (ID: {vc_id})")
                    
                    audio_source_path = EVENT_2_AUDIO
                    if not audio_source_path:
                        print("❌ EVENT_2_AUDIO not configured.")
                    else:
                        is_url = audio_source_path.startswith(('http://', 'https://'))
                        is_local_file = not is_url and os.path.exists(audio_source_path)
                        
                        if is_url or is_local_file:
                            try:
                                print(f"Loading audio source: {audio_source_path}")
                                audio_source = FFmpegPCMAudio(audio_source_path)
                                voice_client.play(audio_source, after=lambda e: print(f"Audio finished playing. Error: {e}" if e else "Audio finished playing."))
                                print(f"✅ Playing audio: {audio_source_path}")
                            except Exception as e:
                                print(f"❌ Failed to play audio: {e}")
                                import traceback
                                traceback.print_exc()
                        else:
                            print(f"❌ Audio file not found or invalid URL: {audio_source_path}")
                except discord.errors.ClientException as e:
                    print(f"❌ ClientException when joining VC: {e}")
                    try:
                        if guild.voice_client:
                            await guild.voice_client.disconnect()
                        await asyncio.sleep(1)
                        voice_client = await vc.connect()
                        state["bot_vc"] = vc_id
                        state["voice_client"] = voice_client
                        print(f"✅ Reconnected to voice channel after error")
                    except Exception as retry_e:
                        print(f"❌ Failed to reconnect: {retry_e}")
                except Exception as e:
                    print(f"❌ Failed to join VC: {e}")
                    import traceback
                    traceback.print_exc()
    
    elif event_type == 3:  # Hidden Reaction
        state["heart_emojis"] = ["❤️", "🧡", "💛", "💚", "💙", "💜", "🤎", "🖤", "🤍", "💔", "❤️‍🔥", "❤️‍🩹", "💕", "💞", "💓", "💗", "💖", "💘", "💝", "💟", "❣️", "💌", "🫀"]
    
    elif event_type == 4:  # Keyword Prompt - 2 Phase Event
        state["woof_users"] = set()
        state["meow_users"] = set()
        state["phase2_started"] = False
        
        class Event4ChoiceView(discord.ui.View):
            def __init__(self, event_state):
                super().__init__(timeout=300)
                self.event_state = event_state
            
            @discord.ui.button(label="Woof", style=discord.ButtonStyle.danger, emoji=None)
            async def woof_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                global active_event
                if not active_event or active_event != self.event_state:
                    await interaction.response.send_message("This event has ended.", ephemeral=True)
                    return
                user_id = interaction.user.id
                if user_id in self.event_state.get("woof_users", set()) or user_id in self.event_state.get("meow_users", set()):
                    await interaction.response.send_message("You've already chosen.", ephemeral=True)
                    return
                await interaction.response.defer(ephemeral=True)
                self.event_state.setdefault("woof_users", set()).add(user_id)
                guild = interaction.guild
                member = guild.get_member(user_id) or interaction.user
                if isinstance(member, discord.Member):
                    woof_role = guild.get_role(EVENT_4_WOOF_ROLE)
                    if woof_role and woof_role not in member.roles:
                        try:
                            await member.add_roles(woof_role, reason="Event 4 Phase 1 - Woof choice")
                            print(f"✅ Assigned Woof role to {member.name}")
                        except Exception as e:
                            print(f"Failed to assign Woof role: {e}")
                await interaction.followup.send("Good choice.", ephemeral=True)
            
            @discord.ui.button(label="Meow", style=discord.ButtonStyle.danger, emoji=None)
            async def meow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                global active_event
                if not active_event or active_event != self.event_state:
                    await interaction.response.send_message("This event has ended.", ephemeral=True)
                    return
                user_id = interaction.user.id
                if user_id in self.event_state.get("woof_users", set()) or user_id in self.event_state.get("meow_users", set()):
                    await interaction.response.send_message("You've already chosen.", ephemeral=True)
                    return
                await interaction.response.defer(ephemeral=True)
                self.event_state.setdefault("meow_users", set()).add(user_id)
                guild = interaction.guild
                member = guild.get_member(user_id) or interaction.user
                if isinstance(member, discord.Member):
                    meow_role = guild.get_role(EVENT_4_MEOW_ROLE)
                    if meow_role and meow_role not in member.roles:
                        try:
                            await member.add_roles(meow_role, reason="Event 4 Phase 1 - Meow choice")
                            print(f"✅ Assigned Meow role to {member.name}")
                        except Exception as e:
                            print(f"Failed to assign Meow role: {e}")
                await interaction.followup.send("Good choice.", ephemeral=True)
        
        view = Event4ChoiceView(state)
        await message.edit(view=view)
        state["view"] = view
        asyncio.create_task(end_event4_phase1(state))
    
    elif event_type == 6:  # Choice Event
        winning_choice = random.choice(["choice_1", "choice_2"])
        state["winning"] = winning_choice
        state["handled"] = set()
        
        class ChoiceEventView(discord.ui.View):
            def __init__(self, event_state, winning):
                super().__init__(timeout=300)
                self.event_state = event_state
                self.winning = winning
            
            @discord.ui.button(label="", style=discord.ButtonStyle.danger, emoji="🖤", custom_id="choice_1")
            async def choice_1_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.handle_choice(interaction, "choice_1")
            
            @discord.ui.button(label="", style=discord.ButtonStyle.danger, emoji="🖤", custom_id="choice_2")
            async def choice_2_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.handle_choice(interaction, "choice_2")
            
            async def handle_choice(self, interaction: discord.Interaction, choice: str):
                user_id = interaction.user.id
                if user_id in self.event_state.get("handled", set()):
                    await interaction.response.send_message("You've already chosen.", ephemeral=True)
                    return
                self.event_state.setdefault("handled", set()).add(user_id)
                member = interaction.user
                is_winning = (choice == self.winning)
                if is_winning:
                    increment_event_participation(user_id)
                    await add_xp(user_id, EVENT_REWARDS[6]["win"], member=member)
                    await interaction.response.send_message("Good choice.", ephemeral=True)
                else:
                    increment_event_participation(user_id)
                    await add_xp(user_id, EVENT_REWARDS[6]["lose"], member=member)
                    await interaction.response.send_message("Wrong choice.", ephemeral=True)
        
        view = ChoiceEventView(state, winning_choice)
        await message.edit(view=view)
        state["view"] = view
    
    elif event_type == 7:  # Collective Event
        state["reactors"] = set()
        state["answered"] = set()
        state["question"] = None
        state["question_answer"] = None
        state["question_answers"] = []
        state["threshold_reached"] = False
        state["phase2_message_id"] = None
        
        class Event7WoofButtonView(discord.ui.View):
            def __init__(self, event_state):
                super().__init__(timeout=300)
                self.event_state = event_state
            
            @discord.ui.button(label="Woof", style=discord.ButtonStyle.danger, emoji=None)
            async def woof_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                global active_event
                try:
                    if not active_event or active_event != self.event_state:
                        await interaction.response.send_message("This event has ended.", ephemeral=True)
                        return
                    user_id = interaction.user.id
                    if user_id in self.event_state.get("reactors", set()):
                        await interaction.response.send_message("You've already participated.", ephemeral=True)
                        return
                    await interaction.response.defer(ephemeral=True)
                    self.event_state.setdefault("reactors", set()).add(user_id)
                    guild = interaction.guild
                    member = guild.get_member(user_id) or interaction.user
                    if not isinstance(member, discord.Member):
                        try:
                            member = await guild.fetch_member(user_id)
                        except:
                            print(f"⚠️ Could not fetch member {user_id}, using User object")
                    increment_event_participation(user_id)
                    await add_xp(user_id, EVENT_REWARDS[7]["phase1"], member=member)
                    role = guild.get_role(EVENT_7_OPT_IN_ROLE)
                    if role:
                        if role not in member.roles:
                            try:
                                await member.add_roles(role, reason="Event 7 Phase 1 participation")
                                print(f"✅ Assigned role {role.name} (ID: {EVENT_7_OPT_IN_ROLE}) to {member.name}")
                            except Exception as e:
                                print(f"❌ Failed to assign role {EVENT_7_OPT_IN_ROLE} to {member.name}: {e}")
                    await interaction.followup.send("Good puppy.", ephemeral=True)
                    reactor_count = len(self.event_state.get("reactors", set()))
                    if reactor_count >= COLLECTIVE_THRESHOLD:
                        started_at = self.event_state.get("started_at")
                        if started_at:
                            time_elapsed = (datetime.datetime.now(datetime.UTC) - started_at).total_seconds()
                            if time_elapsed >= 60 and not self.event_state.get("threshold_reached"):
                                self.event_state["threshold_reached"] = True
                                await escalate_collective_event(guild)
                except discord.errors.NotFound:
                    print(f"⚠️ Interaction expired for user {interaction.user.name}")
                except Exception as e:
                    print(f"❌ Error in woof_button callback: {e}")
                    try:
                        await interaction.followup.send("An error occurred. Please try again.", ephemeral=True)
                    except:
                        pass
        
        view = Event7WoofButtonView(state)
        await message.edit(view=view)
        state["view"] = view
        asyncio.create_task(check_event7_phase1_threshold(state))

    if is_manual_command:
        print(f"Manual event {event_type} started")

    active_event = state
    asyncio.create_task(end_obedience_event(state))

async def end_obedience_event(state):
    """Conclude an event after duration."""
    await asyncio.sleep(EVENT_DURATION_SECONDS)
    global active_event, event_cooldown_until
    if active_event != state:
        return
    guild = bot.get_guild(state["guild_id"])
    if not guild:
        active_event = None
        return

    event_type = state["type"]
    channel = guild.get_channel(state["channel_id"])
    rewarded_users = set()

    # Event 2: Bot leaves VC, reward users who stayed
    if event_type == 2:
        voice_client = state.get("voice_client") or guild.voice_client
        if voice_client:
            try:
                if voice_client.is_playing():
                    voice_client.stop()
                await voice_client.disconnect()
                print("Bot disconnected from voice channel and stopped audio")
            except Exception as e:
                print(f"Failed to disconnect from VC: {e}")
        
        reward = EVENT_REWARDS[2]
        now = datetime.datetime.now(datetime.UTC)
        join_times = state.get("join_times", {})
        for vc_id in EVENT_2_VC_CHANNELS:
            vc = guild.get_channel(vc_id)
            if vc:
                for member in vc.members:
                    if member.bot or any(int(r.id) in EXCLUDED_ROLE_SET for r in member.roles):
                        continue
                    if member.id in join_times:
                        if (now - join_times[member.id]).total_seconds() >= EVENT_DURATION_SECONDS:
                            rewarded_users.add(member.id)
                            increment_event_participation(member.id)
                            await add_xp(member.id, reward, member=member)
                            print(f"  ↳ ✅ Event 2: Awarded {reward} XP bonus to {member.name} for staying in VC")
    
    # Event 4: Send ending message
    elif event_type == 4:
        if channel:
            embed = build_event_embed(
                "Seems like everyone here knows their place. Good.",
                "https://i.imgur.com/DrPzPo8.png"
            )
            await channel.send("@here", embed=embed)
    
    # Event 5: Send ending message, punish non-participants
    elif event_type == 5:
        rewarded_users = set(state["participants"])
        if channel:
            embed = build_event_embed(
                "I'm aware of everyone who answered. Good. \n\nAnd for the rest..\nThey made their choice.",
                "https://i.imgur.com/DrPzPo8.png"
            )
            await channel.send("@here", embed=embed)
        
        all_members = set(m.id for m in guild.members if not m.bot and not any(int(r.id) in EXCLUDED_ROLE_SET for r in m.roles))
        non_participants = all_members - rewarded_users
        for uid in non_participants:
            member = guild.get_member(uid)
            if member:
                await add_xp(uid, -20, member=member)
    
    # Event 6: Send ending message, punish non-participants
    elif event_type == 6:
        rewarded_users = set(state.get("handled", set()))
        if channel:
            try:
                event_message = await channel.fetch_message(state["message_id"])
                embed = discord.Embed(
                    description="*I see you have made your choice.\n\nYour XP has been updated.*",
                    color=0xff000d,
                )
                await event_message.reply(embed=embed)
            except Exception as e:
                print(f"Failed to send Event 6 ending message: {e}")
        
        all_members = set(m.id for m in guild.members if not m.bot and not any(int(r.id) in EXCLUDED_ROLE_SET for r in m.roles))
        non_participants = all_members - rewarded_users
        for uid in non_participants:
            member = guild.get_member(uid)
            if member:
                await add_xp(uid, -20, member=member)
    
    # Event 7: Handle Phase 2 end, then Phase 3
    elif event_type == 7:
        if state.get("phase") == 2:
            await handle_event7_phase3(guild, state)
        else:
            active_event = None
            event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=EVENT_COOLDOWN_SECONDS)
            await clear_event_roles()
            return

    event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=EVENT_COOLDOWN_SECONDS)
    active_event = None
    await clear_event_roles()

async def handle_event7_phase3(guild, state):
    """Handle Event 7 Phase 3 - assign roles and send messages."""
    success_role = guild.get_role(EVENT_7_SUCCESS_ROLE)
    failed_role = guild.get_role(EVENT_7_FAILED_ROLE)
    
    successful_users = []
    failed_users = []
    
    answered_correctly = state.get("answered_correctly", set())
    answered_incorrectly = state.get("answered_incorrectly", set())
    all_participants = answered_correctly | answered_incorrectly
    
    for user_id in all_participants:
        member = guild.get_member(user_id)
        if not member:
            continue
        
        if user_id in answered_correctly:
            successful_users.append(member)
            if success_role and success_role not in member.roles:
                try:
                    await member.add_roles(success_role, reason="Event 7 Phase 2 correct answer")
                    print(f"  ↳ Assigned success role to {member.name}")
                except Exception as e:
                    print(f"  ↳ Failed to assign success role to {member.name}: {e}")
        else:
            failed_users.append(member)
            if failed_role and failed_role not in member.roles:
                try:
                    await member.add_roles(failed_role, reason="Event 7 Phase 2 failure - no correct answer")
                    print(f"  ↳ Assigned failed role to {member.name}")
                except Exception as e:
                    print(f"  ↳ Failed to assign failed role to {member.name}: {e}")
    
    await asyncio.sleep(2)
    
    state["phase"] = 3
    state["phase3_started"] = datetime.datetime.now(datetime.UTC)
    state["phase3_message_cooldowns"] = {}
    
    success_channel = guild.get_channel(EVENT_PHASE3_SUCCESS_CHANNEL_ID)
    failed_channel = guild.get_channel(EVENT_PHASE3_FAILED_CHANNEL_ID)
    
    if success_channel and success_role and successful_users:
        await success_channel.send(success_role.mention)
    
    if failed_channel and failed_role and failed_users:
        await failed_channel.send(failed_role.mention)
    
    await asyncio.sleep(10)
    
    if successful_users and success_channel:
        asyncio.create_task(send_event7_phase3_success(guild, successful_users, success_role))
    if failed_users and failed_channel:
        asyncio.create_task(send_event7_phase3_failed(guild, failed_users, failed_role))
    
    throne_channel = guild.get_channel(EVENT_PHASE3_SUCCESS_CHANNEL_ID)
    if throne_channel and successful_users:
        if throne_channel.id == EVENT_PHASE3_SUCCESS_CHANNEL_ID and throne_channel.id != EVENT_CHANNEL_ID:
            embed = build_event_embed(
                "Good puppies like to please properly. My Throne is open.\n\n◊ ¿°ᵛ˘ æ¢ɲ≥[Throne](https://throne.com/lsla/item/1230a476-4752-4409-9583-9313e60686fe) Әᵛæ´. ✁æ ˘ɲ±æ≤ ┍ææ≥, \"˘æ\"¿˘, Әɲ≥",
                "https://i.imgur.com/Yti9Kss.png"
            )
            await throne_channel.send(embed=embed)
            print(f"✅ Sent Phase 3 throne message to success channel {throne_channel.id} ({throne_channel.name})")
    
    asyncio.create_task(end_event7_phase3(state))

async def send_event7_phase3_failed(guild, failed_users, failed_role):
    """Send Phase 3 failed messages."""
    channel = guild.get_channel(EVENT_PHASE3_FAILED_CHANNEL_ID)
    if not channel:
        return
    
    if failed_role:
        await channel.send(failed_role.mention)
        await asyncio.sleep(1)
    
    quote_variations = [
        "Look at you. Still trying.",
        "You really don't get it, do you?",
        "It's almost impressive how little goes on in your head.",
        "I expected nothing—and somehow you still fell short.",
        "You're adorable when you think you matter.",
        "This is why I don't explain things to you.",
        "So earnest. So slow.",
        "You should stop thinking. It's clearly not your strength.",
        "I don't need to correct you. You embarrass yourself just fine.",
        "You exist exactly where you belong—below me.",
    ]
    
    image_variations = [
        "https://i.imgur.com/wL9CM6q.gif",
        "https://i.imgur.com/waRLVv1.gif",
        "https://i.imgur.com/gvhIpAG.gif",
        "https://i.imgur.com/DP8dXq4.gif",
        "https://i.imgur.com/vBE53cR.gif",
        "https://i.imgur.com/89yIXiY.gif",
    ]
    
    text_variations = [
        "ᕕɲ≤ ϐæ¢´ˆ˘ æ┍ µӘ\"\"°ɲ˘ϐϐ ≤æ¢ ˘Ø\"˘´°˘ɲˆ˘? ◊'¿¿ 𝈇˘ ıµ˘ æɲ˘ ıæ ˆ´˘Әı˘ Әɲ≥ ≥˘ϐı´æ≤ °ı Ә¿¿. øæ¢ µ˘¿\"˘≥ ›˘ «°¿¿ `æ†˘´. ✁µ˘´˘ ›°𝖡µı µӘᵛ˘ 𝈇˘˘ɲ Ә †Ә≤ ┍æ´ ≤æ¢ ıæ ϐӘᵛ˘ œӘ≤Ә«Ә†Ә, 𝈇¢ı ≤æ¢ «°¿¿˘≥ µ°› ıææ. øæ¢ ˘ᵛ˘ɲ ›¢´≥˘´˘≥ ≤æ¢´ æ†ɲ ┍Әıµ˘´. ¥æ›˘æɲ˘ ¿°«˘ ≤æ¢ µӘϐ ɲæ ´°𝖡µı ıæ †°ϐµ ┍æ´ Ә ɲæ´›Ә¿ ¿°┍˘, ≥æ ıµ˘≤?",
        "\"◊ ¿æᵛ˘ µæ† ˆæɲ┍°≥˘ɲı ≤æ¢ Ә´˘ ┍æ´ ϐæ›˘æɲ˘ ϐæ †´æɲ𝖡.\"",
        "\"𝞜Әıˆµ°ɲ𝖡 ≤æ¢ ϐı´¢𝖡𝖡¿˘ °ϐ… ´˘¿ӘØ°ɲ𝖡.\"",
        "\"◊ı'ϐ ˆ¢ı˘ ıµӘı ≤æ¢ «˘˘\" µæ\"°ɲ𝖡 ┍æ´ Ә\"\"´æᵛӘ¿.\"",
    ]
    
    used_quotes = []
    used_images = []
    for i in range(3):
        quote = random.choice([q for q in quote_variations if q not in used_quotes])
        image = random.choice([img for img in image_variations if img not in used_images])
        used_quotes.append(quote)
        used_images.append(image)
        embed = build_event_embed(quote, image)
        await channel.send(embed=embed)
        await asyncio.sleep(1)
    
    used_texts = []
    for i in range(12):
        text = random.choice([t for t in text_variations if t not in used_texts])
        used_texts.append(text)
        embed = build_event_embed(text)
        await channel.send("@everyone", embed=embed)
        await asyncio.sleep(1)
        
        if (i + 1) % 2 == 0 and failed_users:
            random_users = random.sample(failed_users, min(5, len(failed_users)))
            mentions = " ".join([u.mention for u in random_users])
            await channel.send(mentions)
            await asyncio.sleep(1)

async def send_event7_phase3_success(guild, successful_users, success_role):
    """Send Phase 3 success messages."""
    channel = guild.get_channel(EVENT_PHASE3_SUCCESS_CHANNEL_ID)
    if not channel:
        return
    
    if success_role:
        await channel.send(success_role.mention)
        await asyncio.sleep(1)
    
    quote_variations = [
        "Good… you earned this. Look closely—I don't show just anyone.",
        "Mmm. I like when you get it right. Consider this a small glimpse.",
        "See? Obedience has its rewards. Don't look away.",
        "That's exactly what I wanted. I think you deserve a peek.",
        "You did so well… I'll let you see a little more than usual.",
        "Good. Now be still and appreciate what I chose to show you.",
        "I knew you could do it. I dressed with you in mind.",
        "Such a good response. This part is just for you.",
    ]
    
    image_variations = [
        "https://i.imgur.com/N3Kgds9.png",
        "https://i.imgur.com/8clTMgf.png",
        "https://i.imgur.com/bUqMhNf.png",
        "https://i.imgur.com/RyaBdLX.png",
        "https://i.imgur.com/wKntHsw.png",
        "https://i.imgur.com/iYWsSs5.png",
        "https://i.imgur.com/UlCCKu5.png",
        "https://i.imgur.com/Zu9U3CL.png",
        "https://i.imgur.com/eWRtWKc.png",
        "https://i.imgur.com/GcH758a.png",
    ]
    
    text_variations = [
        "᲼᲼\nS̵̛̳̜͕͓͎͚̹̯̟͔̃͌̉͠ȯ̵͕̣͊͛̓̅̆̊̉͌̚͘͝m̶̢̨͍̺͖̩̼͇̪̰̮͐͋̑̆̓͐̀ͅè̸̡̢̤̺̩̠̼̲̖̰̫̼̜̊̽͗̉̇̑ṭ̷̨̛̦̘̻̙̼̪̩̫̖̘͋́̎̄͌̓̕͝h̸̩̪̘̯͉̮̩̼̬͕͂̂̄i̷̡̨̨̫̳̟͍͎̟̯͉̳̞̩̓̄͆͛̕n̴̲͔͎̊̅͂̀͒̔̈́̆͂̾͠g̸̨̢̩̳̣͔̹͇̩͚̺̳͕̣͕͋̍̈́̾̓͊̄̿̓͝ ̸͔͚̟̪̺̝̳̻͍̺̟͛̀́̀̍́̋͜͜͜͝ï̵̪̘̦̬͎̗͊̊͊̍̂̊s̷̤̰̳͇̰̥̹͖̤̼͌̃͑̾̒͗͑̓̅́͑̚̚͜ ̷̡̡̼̻̳̻̠̯̜̘͇̟̠̱̖̎́̀̔̍͂̇̄̏̈́ơ̵̧̘̮̊̽̑̆̎̿̂̍̋͑̈́͘n̶̘̞̺̫̭̩̜̜͎̈́̓̋̓̾͊̇̆́͂̍̐͠ ̵̱̊̕͠t̷̛͙̗͍̩̞̥̹͂̾͋̅̀̄̉̐͐̈́̂͘͠h̴̼͍̙̬͖̍̄̓̀e̴̢̛̅͒͊̽͐̚͝ ̴̨̛̭̱̖̜̣̝̝̓̅̓̀̈́̉̿͂̆̂͂͜͝͝ẃ̴̭̗̳̳̳͂͗̇̍̿͑a̶͚͚͕̠̳̭̘͐̍ÿ̷̛̫͕̘͍́̽̿̚.̶̳͍̩̇̊͜.̷̜̼̼̌͐̔.̶̧̨̩̳̮̟̖͈̘͕̻̣̱̎͒̀̈́͘\n\n◊ ¿°ᵛ˘ æ¢ɲæ ˘ɲ±æ≤ ┍ææ≥, \"˘æ\"¿˘, Әɲ≥",
        "◊ ¿æᵛ˘ µæ† ˆæɲ┍°≥˘ɲı ≤æ¢ Ә´˘ ┍æ´ ϐæ›˘æɲ˘ ϐæ †´æɲ𝖡. ◊'¿¿ 𝈇˘ ıµ˘ æɲ˘ ıæ ˆ´˘Әı˘ Әɲ≥ ≥˘ϐı´æ≤ °ı Ә¿¿.",
        "𝞜Әıˆµ°ɲ𝖡 ≤æ¢ ϐı´¢𝖡𝖡¿˘ °ϐ… ´˘¿ӘØ°ɲ𝖡. ◊ı'ϐ ˆ¢ı˘ ıµӘı ≤æ¢ «˘˘\" µæ\"°ɲ𝖡 ┍æ´ Ә\"\"´æᵛӘ¿.",
        "◊ ¿°ᵛ˘ æ¢ɲ≥ Әᵛæ´. ✁æ ˘ɲ±æ≤ ┍ææ≥, \"˘æ\"¿˘, Әɲ≥. øæ¢ µ˘¿\"˘≥ ›˘ «°¿¿ `æ†˘´.",
        "¥æ›˘æɲ˘ ¿°«˘ ≤æ¢ µӘϐ ɲæ ´°𝖡µı ıæ †°ϐµ ┍æ´ Ә ɲæ´›Ә¿ ¿°┍˘, ≥æ ıµ˘≤?",
        "◊'¿¿ 𝈇˘ ıµ˘ æɲ˘ ıæ ˆ´˘Әı˘ Әɲ≥ ≥˘ϐı´æ≤ °ı Ә¿¿. øæ¢ ˘ᵛ˘ɲ ›¢´≥˘´˘≥ ≤æ¢´ æ†ɲ ┍Әıµ˘´.",
        "◊ ¿æᵛ˘ µæ† ˆæɲ┍°≥˘ɲı ≤æ¢ Ә´˘ ┍æ´ ϐæ›˘æɲ˘ ϐæ †´æɲ𝖡. ✁µ˘´˘ ›°𝖡µı µӘᵛ˘ 𝈇˘˘ɲ Ә †Ә≤ ┍æ´ ≤æ¢ ıæ ϐӘᵛ˘ œӘ≤Ә«Ә†Ә.",
        "𝞜Әıˆµ°ɲ𝖡 ≤æ¢ ϐı´¢𝖡𝖡¿˘ °ϐ… ´˘¿ӘØ°ɲ𝖡. 𝈇¢ı ≤æ¢ «°¿¿˘≥ µ°› ıææ.",
        "◊ı'ϐ ˆ¢ı˘ ıµӘı ≤æ¢ «˘˘\" µæ\"°ɲ𝖡 ┍æ´ Ә\"\"´æᵛӘ¿. øæ¢ µ˘¿\"˘≥ ›˘ «°¿¿ `æ†˘´.",
        "◊ ¿°ᵛ˘ æ¢ɲ≥ Әᵛæ´. ✁æ ˘ɲ±æ≤ ┍ææ≥, \"˘æ\"¿˘, Әɲ≥. ¥æ›˘æɲ˘ ¿°«˘ ≤æ¢ µӘϐ ɲæ ´°𝖡µı.",
        "◊'¿¿ 𝈇˘ ıµ˘ æɲ˘ ıæ ˆ´˘Әı˘ Әɲ≥ ≥˘ϐı´æ≤ °ı Ә¿¿. ✁µ˘´˘ ›°𝖡µı µӘᵛ˘ 𝈇˘˘ɲ Ә †Ә≤.",
        "øæ¢ ˘ᵛ˘ɲ ›¢´≥˘´˘≥ ≤æ¢´ æ†ɲ ┍Әıµ˘´. ◊ ¿æᵛ˘ µæ† ˆæɲ┍°≥˘ɲı ≤æ¢ Ә´˘ ┍æ´ ϐæ›˘æɲ˘ ϐæ †´æɲ𝖡.",
    ]
    
    used_quotes = []
    used_images = []
    for i in range(3):
        quote = random.choice([q for q in quote_variations if q not in used_quotes])
        image = random.choice([img for img in image_variations if img not in used_images])
        used_quotes.append(quote)
        used_images.append(image)
        embed = build_event_embed(quote, image)
        await channel.send(embed=embed)
        await asyncio.sleep(1)
    
    used_texts = []
    for i in range(12):
        text = random.choice([t for t in text_variations if t not in used_texts])
        used_texts.append(text)
        embed = build_event_embed(text)
        await channel.send("@everyone", embed=embed)
        await asyncio.sleep(1)
        
        if (i + 1) % 2 == 0 and successful_users:
            random_users = random.sample(successful_users, min(5, len(successful_users)))
            mentions = " ".join([u.mention for u in random_users])
            await channel.send(mentions)
            await asyncio.sleep(1)

async def handle_event_message(message):
    """Handle messages during active events."""
    global active_event
    if not active_event:
        return
    if message.guild is None or message.guild.id != active_event["guild_id"]:
        return
    if message.author.bot:
        return
    if any(int(r.id) in EXCLUDED_ROLE_SET for r in message.author.roles):
        return
    
    event_type = active_event["type"]
    content = message.content.strip().lower()
    
    # Event 1: Presence Check
    if event_type == 1:
        user_id = message.author.id
        now = datetime.datetime.now(datetime.UTC)
        cooldowns = active_event.get("message_cooldowns", {})
        
        if user_id in cooldowns:
            time_since = (now - cooldowns[user_id]).total_seconds()
            if time_since < 10:
                return
        
        cooldowns[user_id] = now
        active_event["message_cooldowns"] = cooldowns
        active_event.setdefault("participants", set()).add(user_id)
        increment_event_participation(user_id)
        await add_xp(user_id, EVENT_REWARDS[1], member=message.author)
    
    # Event 4: Keyword Prompt - Phase 2 only
    elif event_type == 4 and active_event.get("phase") == 2:
        resolved_channel_id = resolve_channel_id(message.channel)
        user_id = message.author.id
        
        if user_id in active_event.get("answered", set()):
            return
        
        has_me = bool(re.search(r'\bme+\b', content, re.IGNORECASE))
        has_i_am = bool(re.search(r'\bi\s+am\b', content, re.IGNORECASE))
        
        if not (has_me or has_i_am):
            return
        
        if resolved_channel_id == EVENT_4_WOOF_CHANNEL_ID:
            woof_role = message.guild.get_role(EVENT_4_WOOF_ROLE)
            if woof_role and woof_role in message.author.roles:
                active_event.setdefault("answered", set()).add(user_id)
                await add_xp(user_id, EVENT_REWARDS[4], member=message.author)
                try:
                    await message.add_reaction("❤️")
                except Exception:
                    pass
                print(f"  ↳ ✅ Event 4 Phase 2: {message.author.name} answered correctly in Woof channel (+{EVENT_REWARDS[4]} XP)")
        
        elif resolved_channel_id == EVENT_4_MEOW_CHANNEL_ID:
            meow_role = message.guild.get_role(EVENT_4_MEOW_ROLE)
            if meow_role and meow_role in message.author.roles:
                active_event.setdefault("answered", set()).add(user_id)
                await add_xp(user_id, EVENT_REWARDS[4], member=message.author)
                try:
                    await message.add_reaction("❤️")
                except Exception:
                    pass
                print(f"  ↳ ✅ Event 4 Phase 2: {message.author.name} answered correctly in Meow channel (+{EVENT_REWARDS[4]} XP)")
    
    # Event 5: Direct Prompt
    elif event_type == 5:
        accepted = ["yes", "yess", "ye", "yas", "yep", "yepy", "yeah", "yup", "yea",
                   "here", "her", "hre", "still here", "here still", "present", "with you"]
        
        if any(phrase in content for phrase in accepted):
            user_id = message.author.id
            if user_id not in active_event.get("participants", set()):
                active_event.setdefault("participants", set()).add(user_id)
                increment_event_participation(user_id)
                await add_xp(user_id, EVENT_REWARDS[5], member=message.author)
                try:
                    await message.add_reaction("❤️")
                except Exception:
                    pass
        
        if "sorry" in content:
            user_id = message.author.id
            sorry_replies = [
                "It's fine. For now.",
                "I'll allow it this time.",
                "It's fine… this once.",
                "I'll overlook it for now.",
            ]
            await add_xp(user_id, 20, member=message.author)
            try:
                await message.reply(random.choice(sorry_replies))
            except Exception:
                pass
    
    # Event 7 Phase 2: Answer questions
    elif event_type == 7 and active_event.get("phase") == 2:
        resolved_channel_id = resolve_channel_id(message.channel)
        if resolved_channel_id == EVENT_PHASE2_CHANNEL_ID:
            user_id = message.author.id
            
            if user_id in active_event.get("answered_correctly", set()):
                print(f"  ↳ Event 7 Phase 2: User {message.author.name} already answered correctly")
                return
            
            question_answers = active_event.get("question_answers", [])
            if not question_answers:
                print(f"  ↳ Event 7 Phase 2: No question answers configured")
                return
            
            def normalize_stretched(text):
                """Remove stretched letters (e.g., 'horrorrrr' -> 'horror')."""
                if not text:
                    return text.lower()
                result = [text[0].lower()]
                for char in text[1:].lower():
                    if char != result[-1]:
                        result.append(char)
                return ''.join(result)
            
            normalized_content = normalize_stretched(content)
            
            is_correct = False
            for ans in question_answers:
                if isinstance(ans, list):
                    for a in ans:
                        normalized_ans = normalize_stretched(a)
                        if normalized_ans in normalized_content:
                            is_correct = True
                            break
                elif isinstance(ans, str):
                    normalized_ans = normalize_stretched(ans)
                    if normalized_ans in normalized_content:
                        is_correct = True
                if is_correct:
                    break
            
            if is_correct:
                if user_id not in active_event.get("answered_correctly", set()):
                    increment_event_participation(user_id)
                    await add_xp(user_id, EVENT_REWARDS[7]["phase2_correct"], member=message.author)
                    active_event.setdefault("answered_correctly", set()).add(user_id)
                    
                    guild = message.guild
                    success_role = guild.get_role(EVENT_7_SUCCESS_ROLE)
                    if success_role and success_role not in message.author.roles:
                        try:
                            await message.author.add_roles(success_role, reason="Event 7 Phase 2 correct answer")
                            print(f"  ↳ ✅ Assigned success role to {message.author.name}")
                        except Exception as e:
                            print(f"  ↳ Failed to assign success role: {e}")
                    
                    try:
                        await message.add_reaction("❤️")
                    except Exception as e:
                        print(f"  ↳ Failed to add heart reaction: {e}")
                    print(f"  ↳ ✅ Event 7 Phase 2: {message.author.name} answered correctly (+{EVENT_REWARDS[7]['phase2_correct']} XP)")
            else:
                increment_event_participation(user_id)
                await add_xp(user_id, EVENT_REWARDS[7]["phase2_wrong"], member=message.author)
                active_event.setdefault("answered_incorrectly", set()).add(user_id)
                print(f"  ↳ ❌ Event 7 Phase 2: {message.author.name} answered incorrectly ({EVENT_REWARDS[7]['phase2_wrong']} XP)")
    
    # Event 7 Phase 3: Track messages in success/failure channels
    elif event_type == 7 and active_event.get("phase") == 3:
        user_id = message.author.id
        channel_id = message.channel.id
        now = datetime.datetime.now(datetime.UTC)
        
        if channel_id == EVENT_PHASE3_SUCCESS_CHANNEL_ID:
            success_role = message.guild.get_role(EVENT_7_SUCCESS_ROLE)
            if success_role and success_role in message.author.roles:
                cooldowns = active_event.get("phase3_message_cooldowns", {})
                if user_id in cooldowns:
                    time_since = (now - cooldowns[user_id]).total_seconds()
                    if time_since < 10:
                        return
                
                cooldowns[user_id] = now
                active_event["phase3_message_cooldowns"] = cooldowns
                await add_xp(user_id, 20, member=message.author)
        
        elif channel_id == EVENT_PHASE3_FAILED_CHANNEL_ID:
            failed_role = message.guild.get_role(EVENT_7_FAILED_ROLE)
            if failed_role and failed_role in message.author.roles:
                cooldowns = active_event.get("phase3_message_cooldowns", {})
                if user_id in cooldowns:
                    time_since = (now - cooldowns[user_id]).total_seconds()
                    if time_since < 10:
                        return
                
                cooldowns[user_id] = now
                active_event["phase3_message_cooldowns"] = cooldowns
                await add_xp(user_id, -20, member=message.author)

async def handle_event_reaction(payload: discord.RawReactionActionEvent):
    """Handle reactions during active events."""
    global active_event
    if not active_event:
        return
    if payload.guild_id != active_event["guild_id"]:
        return
    if payload.user_id == bot.user.id:
        return
    
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
    if any(int(r.id) in EXCLUDED_ROLE_SET for r in member.roles):
        return
    
    event_type = active_event["type"]
    
    # Event 3: Hidden Reaction - only heart emojis count
    if event_type == 3 and payload.message_id == active_event["message_id"]:
        emoji_str = str(payload.emoji)
        heart_emojis = active_event.get("heart_emojis", [])
        if emoji_str in heart_emojis:
            if payload.user_id not in active_event.get("reactors", set()):
                active_event.setdefault("reactors", set()).add(payload.user_id)
                increment_event_participation(payload.user_id)
                await add_xp(payload.user_id, EVENT_REWARDS[3], member=member)

async def escalate_collective_event(guild):
    """Trigger phase 2 for collective event."""
    global active_event
    if not active_event or active_event["type"] != 7:
        return
    
    await asyncio.sleep(2)
    
    phase2_channel = guild.get_channel(EVENT_PHASE2_CHANNEL_ID)
    if not phase2_channel:
        return
    
    question, answer = choose_collective_question()
    active_event["phase"] = 2
    active_event["threshold_reached"] = True
    
    if isinstance(answer, list):
        active_event["question_answers"] = answer
    else:
        active_event["question_answers"] = [answer]
    
    active_event["answered_correctly"] = set()
    active_event["answered_incorrectly"] = set()
    
    question_embed = build_event_embed(f"Good. Now answer me.\n\n*{question}*", "https://i.imgur.com/v8Ik4cS.png")
    msg = await phase2_channel.send(embed=question_embed)
    active_event["phase2_message_id"] = msg.id
    
    asyncio.create_task(end_event7_phase2(active_event))

