# Timed Posts Schedule

All times are in **UK timezone (Europe/London)**. The bot checks every 1 minute for scheduled times and sends messages within a 1-minute window.

---

## 📅 Event Scheduler

**Frequency:** Checks every 1 minute  
**Channel:** Event Channel (ID: 1450533795156594738)

### Tier 1 Events
Events are randomly selected from Tier 1 event pool and sent **5 times per day**:
- **03:00** (3:00 AM)
- **06:00** (6:00 AM)
- **09:00** (9:00 AM)
- **15:00** (3:00 PM)
- **21:00** (9:00 PM)

### Tier 2 Events
Events are randomly selected from Tier 2 event pool and sent **2 times per day**:
- **12:00** (12:00 PM / Noon)
- **18:00** (6:00 PM)

### Tier 3 Events
Events are randomly selected from Tier 3 event pool and sent **1 time per day**:
- **00:00** (12:00 AM / Midnight)

**Pre-announcement:** A special pre-announcement message is sent **5 minutes before** Tier 3 events:
- **23:55** (11:55 PM) - Pre-announcement for the midnight event

**Event Duration:** 5 minutes  
**Cooldown:** 30 minutes after event ends (no new events during cooldown)

---

---

## 📋 Daily Check Messages

**Frequency:** Checks every 1 minute

Sent at **three different times** each day:

### 1. Daily Check (/daily command)
**Time:** **22:00** (10:00 PM) UK time  
**Channel:** User Command Channel (ID: 1450107538019192832)  
**Mentions:** @everyone

**Message Content:**
- Title: "Daily Check <:kisses:1449998044446593125>"
- Description: "Have you checked in today?\nYour coins are waiting.\n\nType `/daily` in <#1450107538019192832> to claim your allocation."
- Thumbnail: https://i.imgur.com/zMiZC5b.png
- Footer: "Resets daily at 6:00 PM GMT"
- Color: `0xcdb623`

### 2. Coffee Check (Throne)
**Time:** **19:00** (7:00 PM) UK time  
**Channel:** Event Channel (ID: 1450533795156594738)  
**Mentions:** @everyone

**Message Content:**
- Title: "Coffee Check ☕"
- Description: Random variant from 7 options + link to [Buy Coffee](https://throne.com/lsla/item/1230a476-4752-4409-9583-9313e60686fe)
- Thumbnail: https://i.imgur.com/F2RpiGq.png
- Footer: "I remember who takes care of me."
- Color: `0xa0b964`

**Description Variants:**
- "I haven't had my coffee yet.\nYou wouldn't want me disappointed today, would you?"
- "I woke up craving something warm…\nCoffee would be a very good start."
- "My focus is slipping.\nA coffee would fix that."
- "I expect to be taken care of.\nCoffee sounds like the correct choice right now."
- "I'm watching the day unfold.\nCoffee would improve my mood significantly."
- "You know what I like.\nCoffee. Warm. Thoughtful. Timely."
- "I could handle the day without coffee…\nBut I'd rather not have to."

### 3. Slots Check
**Time:** **20:00** (8:00 PM) UK time  
**Channel:** Event Channel (ID: 1450533795156594738)  
**Mentions:** @everyone

**Message Content:**
- Title: "Slots Check 🎲"
- Description: Random variant from 7 options + link to [Buy Slots](https://islaexe.itch.io/islas-slots)
- Thumbnail: https://i.imgur.com/KEnVDdy.png
- Footer: "This is part of your role."
- Color: `0xcd6032`

**Description Variants:**
- "I'm in the mood to watch you try your luck.\nGo play my slots."
- "I enjoy seeing effort turn into results.\nSlots would be a good use of your time right now."
- "I wonder how lucky you're feeling today.\nWhy don't you find out for me?"
- "Luck favors the attentive.\nYou should give my slots a try."
- "I'm watching.\nThis would be a good moment to play."
- "Sometimes obedience looks like initiative.\nSlots. Now."
- "I like it when you make the right choice on your own.\nMy slots are waiting."

---

## ⚙️ Background Tasks

### Voice Chat XP Award
**Frequency:** Every 1 minute  
**Function:** Awards XP to users in tracked voice channels
- Base XP: 5 XP per minute
- During Event 2 (first 5 minutes): 10 XP per minute (double XP)
- After Event 2 ends: 50 XP bonus for users who stayed full duration

### Auto-Save
**Frequency:** Every 5 minutes  
**Function:** Automatically saves XP data to `xp.json`

---

## 📝 Notes

- All scheduled times use **UK timezone (Europe/London)**
- The bot checks within a **1-minute window** of the scheduled time
- Each scheduled message is only sent **once per day** (tracked by date and time)
- Events are disabled during:
  - Active event running
  - Cooldown period (30 minutes after event ends)
  - If `events_enabled` flag is False
- Manual events (started via admin commands) do not affect scheduled times tracking

---

## Summary Table

| Post Type | Frequency | Times (UK) | Channel | Mentions |
|-----------|-----------|------------|---------|----------|
| Tier 1 Events | 5x/day | 03:00, 06:00, 09:00, 15:00, 21:00 | Event Channel | - |
| Tier 2 Events | 2x/day | 12:00, 18:00 | Event Channel | - |
| Tier 3 Events | 1x/day | 00:00 | Event Channel | - |
| Tier 3 Pre-announcement | 1x/day | 23:55 | Event Channel | - |
| Coffee Check (Throne) | 1x/day | 19:00 | Event Channel | @everyone |
| Slots Check | 1x/day | 20:00 | Event Channel | @everyone |
| Daily Check (/daily) | 1x/day | 22:00 | User Command Channel | @everyone |

