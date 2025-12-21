"""
Main entry point for IslaBot - wires together all modules
# Auto-deployment test - remove this comment after testing
"""
import discord
from discord.ext import commands
import os
import datetime
from dotenv import load_dotenv

# Import all modules
from config import ALLOWED_GUILDS, EVENT_SCHEDULE
from data import load_xp_data
from utils import get_timezone, USE_PYTZ
import events
import handlers
import tasks
from commands import user_commands, admin_commands
from xp import set_bot as set_xp_bot
from utils import set_bot as set_utils_bot
from events import set_bot as set_events_bot
from tasks import set_bot as set_tasks_bot

# Load environment variables
# Try loading from secret.env first (for local development)
try:
    load_dotenv('secret.env')
    print("✓ Loaded environment variables from secret.env")
except Exception as e:
    print(f"Note: Could not load secret.env file: {e}. Trying system environment variables...")

# Also try .env as a fallback
try:
    load_dotenv('.env')
except Exception:
    pass  # .env is optional

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True
intents.message_content = True
intents.voice_states = True

COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or(COMMAND_PREFIX),
    intents=intents,
    case_insensitive=True,
    strip_after_prefix=True,
)

# Set bot instance in all modules (must be done before registering commands/handlers)
handlers.set_bot(bot)
set_tasks_bot(bot)
set_xp_bot(bot)
set_utils_bot(bot)
set_events_bot(bot)
user_commands.set_bot(bot)
admin_commands.set_bot(bot)

# Register commands
user_commands.register_commands(bot)
admin_commands.register_commands(bot)

# Register event handlers
@bot.event
async def on_message(message):
    await handlers.on_message(message)

@bot.event
async def on_voice_state_update(member, before, after):
    await handlers.on_voice_state_update(member, before, after)

@bot.event
async def on_raw_reaction_add(payload):
    await handlers.on_raw_reaction_add(payload)

@bot.event
async def on_command_error(ctx, error):
    await handlers.on_command_error(ctx, error)

@bot.event
async def on_guild_join(guild):
    await handlers.on_guild_join(guild)

@bot.event
async def on_member_remove(member):
    await handlers.on_member_remove(member)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    
    # Leave any guilds that aren't in the allowed list
    for guild in bot.guilds:
        if guild.id not in ALLOWED_GUILDS:
            try:
                await guild.leave()
                print(f'Left {guild.name} (ID: {guild.id}) - not in allowed guilds list')
            except Exception as e:
                print(f'Failed to leave {guild.name} (ID: {guild.id}): {e}')
    
    print(f'Bot is now in {len([g for g in bot.guilds if g.id in ALLOWED_GUILDS])} allowed guild(s)')
    
    # Load XP data
    load_xp_data()
    
    # Initialize event scheduler with UK timezone
    uk_tz = get_timezone("Europe/London")
    if uk_tz is not None:
        if USE_PYTZ:
            now_uk = datetime.datetime.now(uk_tz)
        else:
            now_uk = datetime.datetime.now(uk_tz)
        today_str = now_uk.strftime("%Y-%m-%d")
        
        # Clear any old tracking data
        from events import last_event_times_today
        last_event_times_today.clear()
        tasks.last_daily_check_times_today.clear()
        
        # Print scheduled times for each tier
        for tier, scheduled_times in EVENT_SCHEDULE.items():
            times_str = ", ".join([f"{h:02d}:{m:02d}" for h, m in scheduled_times])
            print(f"⏱️ Tier {tier} events scheduled at: {times_str} UK time")
        
        # Print Daily Check scheduled times
        print(f"📋 Daily Check messages scheduled at: 19:00 (Throne), 20:00 (Slots), 22:00 (Daily) UK time")
        
        print(f"📅 Current UK time: {now_uk.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    else:
        print("⚠️ WARNING: Timezone support not available. Event scheduling may not work correctly.")
    
    # Set initial 30-minute cooldown to prevent events from starting immediately
    import events
    events.event_cooldown_until = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=1800)
    print(f"⏰ Initial event cooldown set: No events will start for 30 minutes (until {events.event_cooldown_until.strftime('%H:%M:%S UTC')})")
    
    # Clear event roles on startup (no events should be active)
    await events.clear_event_roles()
    
    # Start background tasks
    tasks.award_vc_xp.start()
    tasks.auto_save.start()
    tasks.event_scheduler.start()
    tasks.daily_check_scheduler.start()
    print("Background tasks started: VC XP tracking, auto-save, event scheduler, and Daily Check scheduler")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

# Bot login
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    print("=" * 60)
    print("ERROR: DISCORD_TOKEN not found in environment variables!")
    print("=" * 60)
    print("\nTo fix this:")
    print("1. For Wispbyte: Set DISCORD_TOKEN in your Wispbyte server's environment variables")
    print("   - Go to your Wispbyte server settings")
    print("   - Find 'Environment Variables' or 'Startup' section")
    print("   - Add: DISCORD_TOKEN=your_bot_token_here")
    print("\n2. For local development: Create a 'secret.env' file with:")
    print("   DISCORD_TOKEN=your_bot_token_here")
    print("=" * 60)
    exit(1)

try:
    bot.run(TOKEN)
except Exception as e:
    print(f"ERROR: Failed to start bot: {e}")
    exit(1)

