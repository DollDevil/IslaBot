"""
Main entry point for IslaBot - wires together all modules
# Auto-deployment test - remove this comment after testing
"""
import sys
import os

# Add parent directory to path so we can import core and systems packages
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import discord
from discord.ext import commands
import datetime
from dotenv import load_dotenv

# Import all modules
from core.config import ALLOWED_GUILDS
# Legacy: load_xp_data is now a no-op (data is in DB)
from core.utils import get_timezone, USE_PYTZ
import systems.events as events
import systems.handlers as handlers
import systems.tasks as tasks
from commands import user_commands, admin_commands
# Legacy XP/Level system removed
from core.utils import set_bot as set_utils_bot
from systems.events import set_bot as set_events_bot
from systems.tasks import set_bot as set_tasks_bot

# Load environment variables
# Try loading from secret.env first (for local development)
try:
    load_dotenv('secret.env')
    print("[+] Loaded environment variables from secret.env")
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
set_utils_bot(bot)
set_events_bot(bot)
user_commands.set_bot(bot)
admin_commands.set_bot(bot)

# Import and set onboarding bot
import systems.onboarding as onboarding
onboarding.set_bot(bot)

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
async def on_app_command_completion(interaction, command):
    await handlers.on_app_command_completion(interaction, command)

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
async def on_member_join(member):
    await handlers.on_member_join(member)

@bot.event
async def on_connect():
    """Called when bot connects to Discord (before on_ready) - initialize database here"""
    from core.data import initialize_database
    await initialize_database()
    print("[+] Database initialized in on_connect")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    
    # PHASE 0: DEBUG STARTUP BANNER
    print("=" * 60)
    print("DEBUG STARTUP DIAGNOSTICS")
    print("=" * 60)
    print(f"Current working directory: {os.getcwd()}")
    from core.db import get_db_path
    db_path = get_db_path()
    print(f"Resolved DB path: {db_path}")
    print(f"DB path exists: {os.path.exists(db_path)}")
    print(f"DB directory exists: {os.path.exists(os.path.dirname(db_path))}")
    
    # Count commands before sync
    commands_before = list(bot.tree.get_commands())
    commands_count = len(commands_before)
    print(f"Discovered app commands (before sync): {commands_count}")
    if commands_count > 0:
        command_names = [cmd.name for cmd in commands_before[:10]]  # Show first 10
        print(f"Command names (first 10): {', '.join(command_names)}")
        if commands_count > 10:
            print(f"... and {commands_count - 10} more")
    print("=" * 60)
    
    # Leave any guilds that aren't in the allowed list
    for guild in bot.guilds:
        if guild.id not in ALLOWED_GUILDS:
            try:
                await guild.leave()
                print(f'Left {guild.name} (ID: {guild.id}) - not in allowed guilds list')
            except Exception as e:
                print(f'Failed to leave {guild.name} (ID: {guild.id}): {e}')
    
    print(f'Bot is now in {len([g for g in bot.guilds if g.id in ALLOWED_GUILDS])} allowed guild(s)')
    
    # Database already initialized in setup_hook, but verify it's ready
    from core.data import initialize_database
    await initialize_database()  # This is idempotent (checks _db_initialized flag)
    
    # Initialize event scheduler with UK timezone
    uk_tz = get_timezone("Europe/London")
    if uk_tz is not None:
        if USE_PYTZ:
            now_uk = datetime.datetime.now(uk_tz)
        else:
            now_uk = datetime.datetime.now(uk_tz)
        today_str = now_uk.strftime("%Y-%m-%d")
        
        print(f"[*] Current UK time: {now_uk.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"[*] Promo rotation scheduler: Runs daily at 12:00 UK time (4-day cycle: Throne -> none -> Coffee -> none)")
    
    # Start background tasks
    tasks.auto_save.start()
    tasks.promo_rotation_scheduler.start()
    tasks.v3_daily_job.start()
    tasks.v3_weekly_job.start()
    tasks.cleanup_expired_events_task.start()
    tasks.daily_orders_drop_task.start()
    tasks.personal_order_reminders_task.start()
    print("Background tasks started: auto-save, promo rotation scheduler, V3 progression jobs (daily/weekly), event cleanup, daily orders drop, and personal order reminders")
    
    # Sync slash commands (global + per-guild for faster propagation)
    sync_results = {}
    
    # Global sync
    try:
        synced_global = await bot.tree.sync()
        sync_results["global"] = len(synced_global)
        print(f"[+] Global sync: {len(synced_global)} command(s)")
    except Exception as e:
        sync_results["global"] = f"ERROR: {e}"
        print(f"[-] Global sync failed: {e}")
    
    # Per-guild sync for faster propagation in allowed guilds
    for guild_id in ALLOWED_GUILDS:
        try:
            synced_guild = await bot.tree.sync(guild=discord.Object(id=guild_id))
            sync_results[f"guild_{guild_id}"] = len(synced_guild)
            print(f"[+] Guild sync ({guild_id}): {len(synced_guild)} command(s)")
        except Exception as e:
            sync_results[f"guild_{guild_id}"] = f"ERROR: {e}"
            print(f"[-] Guild sync ({guild_id}) failed: {e}")

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

@bot.event
async def on_disconnect():
    """Clean up database connection on disconnect"""
    from core.data import shutdown_database
    await shutdown_database()

try:
    bot.run(TOKEN)
except Exception as e:
    print(f"ERROR: Failed to start bot: {e}")
    # Ensure database is closed on error
    from core.data import shutdown_database
    import asyncio
    try:
        asyncio.run(shutdown_database())
    except:
        pass
    exit(1)

