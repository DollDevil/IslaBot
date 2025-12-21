"""
Scheduled tasks for the bot - VC XP, auto-save, event scheduling, daily checks
"""
import discord
from discord.ext import tasks
import datetime
import random

from core.config import (
    EVENT_CHANNEL_ID, EVENT_SCHEDULE, EVENT_TIER_MAP, VC_XP,
    VC_XP_TRACK_CHANNELS, NON_XP_CATEGORY_IDS, NON_XP_CHANNEL_IDS,
    EXCLUDED_ROLE_SET, USER_COMMAND_CHANNEL_ID
)
from core.data import xp_data, save_xp_data
from systems.xp import add_xp
from core.utils import resolve_category_id, get_channel_multiplier, get_timezone, USE_PYTZ
from systems.events import active_event, start_obedience_event, events_enabled

# Global state for tracking
last_event_times_today = set()
last_daily_check_times_today = set()

# Bot instance (set by main.py)
bot = None

def set_bot(bot_instance):
    """Set the bot instance for this module"""
    global bot
    bot = bot_instance

def get_next_scheduled_time(hour: int, minute: int) -> int:
    """Get next occurrence of a scheduled time in UK timezone as Unix timestamp."""
    uk_tz = get_timezone("Europe/London")
    if uk_tz is None:
        uk_tz = datetime.timezone.utc
    
    if USE_PYTZ:
        now_uk = datetime.datetime.now(uk_tz)
    else:
        now_uk = datetime.datetime.now(uk_tz)
    
    target_time = now_uk.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if target_time <= now_uk:
        target_time += datetime.timedelta(days=1)
    
    if USE_PYTZ:
        target_utc = target_time.astimezone(datetime.timezone.utc)
    else:
        target_utc = target_time.astimezone(datetime.timezone.utc)
    
    return int(target_utc.timestamp())

async def send_tier3_pre_announcement(guild):
    """Send pre-announcement for Tier 3 events 5 minutes before they start."""
    channel = guild.get_channel(EVENT_CHANNEL_ID)
    if not channel:
        return
    
    embed = discord.Embed(
        description="᲼᲼\nS̵̛̳̜͕͓͎͚̹̯̟͔̃͌̉͠ȯ̵͕̣͊͛̓̅̆̊̉͌̚͘͝m̶̢̨͍̺͔͖̩̼͇̪̰̮͐͋̑̆̓͐̀ͅè̸̡̢̤̺̩̠̼̲̖̰̫̼̜̊̽͗̉̇̑ṭ̷̨̛̦̘̻̙̼̪̩̫̖̘͋́̎̄͌̓̕͝h̸̩̪͚̘̯͉̮̩̼̬͕͂̂͂̄i̷̡̨̨̫̳̟͍͎̟̯͉̳̞̩̓̄͆͛̕n̴̲͔͎̊̅̈́͂̀͒̔̈́̆͂̾͠g̸̨̢̩̳̣͔̹͇̩͚̺̳͕̣͕͋̍̈́̾̓͊̄̿̓͝ ̸͔͚̟̪̺̝̳̻͍̺̟͛̀́̀̍́̋͜͜͜͝ï̵̪̘̦̬͎̗͊̊͊̍̂̊s̷̤̰̳͇̰̥̹͖̤̼͌̃͑̾̒͗͑̓̅́͑̚̚͜ ̷̡̡̼̻̳̻̠̯̜̘͇̟̠̱̖̎́̀̔̍͂̇̄̏̈́ơ̵̧̘̮̊̽̑̆̎̿̂̍̋͑̈́͘n̶̘̞̮̺̫̭̩̜̜͎̈́̓̋̓̾͊̇̆́͂̍̐͠ ̵̱̊̂̕͠t̷̛͙̗͍̩̞̥̹͂̾͋̅̀̄̉̐͐̈́̂͘͠h̴̼͍̙̬͖̍̄̓̀e̴̢̛̅͒͊̽͐̚͝ ̴̨̛̭̱̖̜̣̝̝̓̅̓̀̈́̉̿͂̆̂͂͜͝͝ẃ̴̭̗̳̳̳͂͗̇̍̿͑a̶͚͚͕̠̳̭̘͐̍ÿ̷̛̫͕̘͍́̽̿̚͠.̶̳͍̩̇̊͜.̷̜̼̌͐̔.̶̧̨̩̳̮̟̖͈̘͕̻̣̱̎͒̀̈́͘\n\n◊ ¿°ᵛ˘ æ¢ɲæ ˘ɲ±æ≤ ┍ææ≥, \"˘æ\"¿˘, Әɲ≥",
        color=0xff000d,
    )
    embed.set_image(url="https://i.imgur.com/gvhIpAG.gif")
    
    try:
        await channel.send(embed=embed)
        print("Sent Tier 3 pre-announcement")
    except Exception as e:
        print(f"Failed to send Tier 3 pre-announcement: {e}")

async def send_daily_check_dailycommand(guild):
    """Send Daily Check message for /daily command."""
    daily_channel = guild.get_channel(USER_COMMAND_CHANNEL_ID)
    if not daily_channel:
        print(f"Daily check channel not found (ID: {USER_COMMAND_CHANNEL_ID})")
        return False
    
    embed = discord.Embed(
        title="Daily Check <:kisses:1449998044446593125>",
        description="Have you checked in today?\nYour coins are waiting.\n\nType `/daily` in <#1450107538019192832> to claim your allocation.",
        color=0xcdb623,
    )
    embed.set_thumbnail(url="https://i.imgur.com/zMiZC5b.png")
    embed.set_footer(text="Resets daily at 6:00 PM GMT")
    
    try:
        await daily_channel.send(embed=embed)
        print(f"✅ Daily Check (/daily) sent to {daily_channel.name}")
        return True
    except Exception as e:
        print(f"Failed to send Daily Check (/daily): {e}")
        return False

async def send_daily_check_throne(guild):
    """Send Daily Check message for Throne coffee."""
    throne_channel = guild.get_channel(EVENT_CHANNEL_ID)
    if not throne_channel:
        print(f"Throne check channel not found (ID: {EVENT_CHANNEL_ID})")
        return False
    
    description_variants = [
        "I haven't had my coffee yet.\nYou wouldn't want me disappointed today, would you?",
        "I woke up craving something warm…\nCoffee would be a very good start.",
        "My focus is slipping.\nA coffee would fix that.",
        "I expect to be taken care of.\nCoffee sounds like the correct choice right now.",
        "I'm watching the day unfold.\nCoffee would improve my mood significantly.",
        "You know what I like.\nCoffee. Warm. Thoughtful. Timely.",
        "I could handle the day without coffee…\nBut I'd rather not have to.",
    ]
    
    embed = discord.Embed(
        title="Coffee Check ☕",
        description=f"{random.choice(description_variants)}\n\n[Buy Coffee](https://throne.com/lsla/item/1230a476-4752-4409-9583-9313e60686fe)",
        color=0xa0b964,
    )
    embed.set_thumbnail(url="https://i.imgur.com/F2RpiGq.png")
    embed.set_footer(text="I remember who takes care of me.")
    
    try:
        await throne_channel.send("@everyone", embed=embed)
        print(f"✅ Daily Check (Throne) sent to {throne_channel.name}")
        return True
    except Exception as e:
        print(f"Failed to send Daily Check (Throne): {e}")
        return False

async def send_daily_check_slots(guild):
    """Send Daily Check message for Slots."""
    slots_channel = guild.get_channel(EVENT_CHANNEL_ID)
    if not slots_channel:
        print(f"Slots check channel not found (ID: {EVENT_CHANNEL_ID})")
        return False
    
    description_variants = [
        "I'm in the mood to watch you try your luck.\nGo play my slots.",
        "I enjoy seeing effort turn into results.\nSlots would be a good use of your time right now.",
        "I wonder how lucky you're feeling today.\nWhy don't you find out for me?",
        "Luck favors the attentive.\nYou should give my slots a try.",
        "I'm watching.\nThis would be a good moment to play.",
        "Sometimes obedience looks like initiative.\nSlots. Now.",
        "I like it when you make the right choice on your own.\nMy slots are waiting.",
    ]
    
    embed = discord.Embed(
        title="Slots Check 🎲",
        description=f"{random.choice(description_variants)}\n\n[Buy Slots](https://islaexe.itch.io/islas-slots)",
        color=0xcd6032,
    )
    embed.set_thumbnail(url="https://i.imgur.com/KEnVDdy.png")
    embed.set_footer(text="This is part of your role.")
    
    try:
        await slots_channel.send("@everyone", embed=embed)
        print(f"✅ Daily Check (Slots) sent to {slots_channel.name}")
        return True
    except Exception as e:
        print(f"Failed to send Daily Check (Slots): {e}")
        return False

@tasks.loop(minutes=1)
async def award_vc_xp():
    """Award XP every minute to users in tracked voice channels"""
    for guild in bot.guilds:
        for vc in guild.voice_channels:
            if vc.id not in VC_XP_TRACK_CHANNELS:
                continue
            
            for member in vc.members:
                if member.bot:
                    continue
                if any(int(role.id) in EXCLUDED_ROLE_SET for role in member.roles):
                    print(f"Skipped VC XP for {member.name} (has excluded role)")
                    continue
                category_id = resolve_category_id(vc)
                if category_id in NON_XP_CATEGORY_IDS or vc.id in NON_XP_CHANNEL_IDS:
                    print(f"Skipped VC XP for {member.name} (excluded VC/channel/category)")
                    continue
                
                xp_to_award = VC_XP
                if active_event and active_event.get("type") == 2:
                    event_start = active_event.get("started_at")
                    if event_start:
                        elapsed = (datetime.datetime.now(datetime.UTC) - event_start).total_seconds()
                        if elapsed <= 300:
                            xp_to_award = VC_XP * 2
                
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
                xp_data[uid]["vc_minutes"] = xp_data[uid].get("vc_minutes", 0) + 1
                
                base_mult = get_channel_multiplier(vc.id)
                await add_xp(member.id, xp_to_award, member=member, base_multiplier=base_mult)
                event_bonus = " (Event 2 double XP)" if xp_to_award > VC_XP else ""
                print(f"Awarded {xp_to_award} VC XP to {member.name} in {vc.name} (channel mult {base_mult}x){event_bonus}")

@tasks.loop(minutes=5)
async def auto_save():
    """Periodically save XP data as backup"""
    save_xp_data()
    print(f"Auto-saved XP data at {datetime.datetime.now(datetime.UTC)}")

@tasks.loop(minutes=1)
async def daily_check_scheduler():
    """Automatically send Daily Check messages at scheduled times."""
    global last_daily_check_times_today
    
    uk_tz = get_timezone("Europe/London")
    if uk_tz is None:
        return
    
    if USE_PYTZ:
        now_uk = datetime.datetime.now(uk_tz)
    else:
        now_uk = datetime.datetime.now(uk_tz)
    
    today_str = now_uk.strftime("%Y-%m-%d")
    current_time = (now_uk.hour, now_uk.minute)
    
    last_daily_check_times_today = {entry for entry in last_daily_check_times_today if entry.startswith(today_str)}
    
    daily_check_times = [
        (19, 0, "throne"),
        (20, 0, "slots"),
        (22, 0, "daily"),
    ]
    
    for hour, minute, check_type in daily_check_times:
        time_diff = abs((now_uk.hour * 60 + now_uk.minute) - (hour * 60 + minute))
        
        if time_diff <= 1:
            check_key = f"{today_str}_DAILY_CHECK_{check_type}_{hour:02d}:{minute:02d}"
            
            if check_key in last_daily_check_times_today:
                continue
            
            for guild in bot.guilds:
                if check_type == "throne":
                    success = await send_daily_check_throne(guild)
                elif check_type == "slots":
                    success = await send_daily_check_slots(guild)
                elif check_type == "daily":
                    success = await send_daily_check_dailycommand(guild)
                else:
                    success = False
                
                if success:
                    last_daily_check_times_today.add(check_key)
                    print(f"Auto-sent Daily Check ({check_type}) at {now_uk.strftime('%H:%M:%S')} UK time")
                    break

@tasks.loop(minutes=1)
async def event_scheduler():
    """Automatically schedule events based on UK timezone schedule"""
    global active_event, last_event_times_today
    from events import event_cooldown_until
    
    if not events_enabled:
        return
    
    if active_event:
        return
    if event_cooldown_until and datetime.datetime.now(datetime.UTC) < event_cooldown_until:
        return
    
    uk_tz = get_timezone("Europe/London")
    if uk_tz is None:
        print("ERROR: Timezone support not available. Cannot schedule events. Install pytz: pip install pytz")
        return
    
    if USE_PYTZ:
        now_uk = datetime.datetime.now(uk_tz)
    else:
        now_uk = datetime.datetime.now(uk_tz)
    today_str = now_uk.strftime("%Y-%m-%d")
    current_time = (now_uk.hour, now_uk.minute)
    
    last_event_times_today = {entry for entry in last_event_times_today if entry.startswith(today_str)}
    
    if current_time == (23, 55):
        tomorrow = (now_uk + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        pre_announce_key = f"{tomorrow}_TIER_3_00:00_pre_announced"
        if pre_announce_key not in last_event_times_today:
            for guild in bot.guilds:
                await send_tier3_pre_announcement(guild)
            last_event_times_today.add(pre_announce_key)
            print(f"Sent Tier 3 pre-announcement at {now_uk.strftime('%H:%M:%S')} UK time (for event at 00:00)")
    
    for tier, scheduled_times in EVENT_SCHEDULE.items():
        for hour, minute in scheduled_times:
            time_diff = abs((now_uk.hour * 60 + now_uk.minute) - (hour * 60 + minute))
            
            if time_diff <= 1:
                event_key = f"{today_str}_TIER_{tier}_{hour:02d}:{minute:02d}"
                
                if event_key in last_event_times_today:
                    continue
                
                available_events = [et for et, t in EVENT_TIER_MAP.items() if t == tier]
                if not available_events:
                    continue
                
                event_type = random.choice(available_events)
                
                for guild in bot.guilds:
                    event_channel = guild.get_channel(EVENT_CHANNEL_ID)
                    if event_channel:
                        try:
                            await start_obedience_event(guild, event_type, channel=event_channel)
                            last_event_times_today.add(event_key)
                            if tier == 3 and hour == 0 and minute == 0:
                                last_event_times_today.discard(f"{today_str}_TIER_3_00:00_pre_announced")
                            print(f"Auto-started Event {event_type} (Tier {tier}) at {now_uk.strftime('%H:%M:%S')} UK time")
                            return
                        except Exception as e:
                            print(f"Failed to auto-start event {event_type}: {e}")
                        break

