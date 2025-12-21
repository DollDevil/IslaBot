"""
Configuration constants for IslaBot
"""
import os

# -----------------------------
# Channels configuration
# -----------------------------
ALLOWED_SEND_CHANNELS = [
    1450107538019192832,  # Level up messages
    1407164453094686762,  # Logs channel
    1450628852345868369,  # Event 7 Phase 2 channel
    1450329944549752884,  # Event 7 Phase 3 failed channel
    1450329916146057266,  # Event 7 Phase 3 success channel
]
XP_TRACK_CHANNELS = [
    # Text channels where XP is tracked
    1407167717022109796,
    1412583527332974622,
    1407167072361910292,
    1407164449126617110,
    1450147031745040516,
    1450145080034857031,
    1407166856455913562,
    1450147097524306021,
    1450962305092423760,
    1450628852345868369,
    1450329916146057266,
    1450329944549752884,
    1450693708465967174,  # Event 4 Phase 2 - Woof channel
    1450693722512818196,  # Event 4 Phase 2 - Meow channel
    1451697334034497728,
    1451708265703669822,
]
# Voice channels where XP is tracked
VC_XP_TRACK_CHANNELS = {
    1450201595575795866,
    1450203538352246976,
    1451254356841332808,
}
VC_XP = 5  # XP per minute in voice
MESSAGE_COOLDOWN = 10  # seconds
EXCLUDED_ROLE_IDS = {
    1407164448132698221,  # Admin/Bot role
    1407164448132698220,  # Admin/Bot role
    1411294634843439134,  # Admin/Bot role
    1407164448132698215,  # Admin/Bot role
}  # Users with these roles don't gain XP

# XP Multiplier roles - each adds 0.2x (20%) bonus
MULTIPLIER_ROLES = [1450182197310132365, 1407164448132698218, 1449945175412707460]

# Categories excluded from XP gain
NON_XP_CATEGORY_IDS = {1407164448707313750}

# Channels excluded from XP gain
NON_XP_CHANNEL_IDS = {1449946515882774630, 1411436063842635816, 1449922902760882307, 1450188229734043770}

# Channel multipliers
CHANNEL_MULTIPLIERS = {
    1407167072361910292: 1.2,
    1412583527332974622: 1.2,
    1450145080034857031: 1.1,
    1407166856455913562: 1.1,
    1450147097524306021: 1.1,
}

# XP thresholds per level; after the list, each level adds +10k XP requirement
XP_THRESHOLDS = [10, 100, 500, 2000, 5000, 8000, 11000, 15000, 20000]

# Use sets for quick, type-safe membership checks
XP_TRACK_SET = {int(ch) for ch in XP_TRACK_CHANNELS}
ALLOWED_SEND_SET = {int(ch) for ch in ALLOWED_SEND_CHANNELS}
MULTIPLIER_ROLE_SET = {int(r) for r in MULTIPLIER_ROLES}
EXCLUDED_ROLE_SET = {int(r) for r in EXCLUDED_ROLE_IDS}

# Level -> role mapping
LEVEL_ROLE_MAP = {
    1: 1450113474247004171,
    2: 1450113555478352014,
    5: 1450113470769926327,
    10: 1450111760530018525,
    20: 1450111757606457506,
    30: 1450111754821701743,
    40: 1450128927161979066,
    50: 1450111746932215819,
    75: 1450128929435287635,
    100: 1450128933189324901,
}

# Reply system configuration
REPLY_CHANNEL_ID = 1407167072361910292
LEVEL_2_ROLE_ID = 1450113555478352014
BETA_BOOST_SERVANT_ROLE_IDS = {1407164448132698218, 1450182197310132365, 1449945175412707460}
KITTEN_ROLE_ID = 1407169798944592033
PUPPY_ROLE_ID = 1407170105326174208
PET_ROLE_ID = 1407169870306738199
DEVOTEE_ROLE_ID = 1407164448132698216

# Reply quotes by role priority
REPLY_QUOTES = {
    "level_2": [
        "You took your time introducing yourself… but I'm glad you finally did.",
        "I was wondering when you'd say something about yourself.",
        "You've been here a while. I would have liked to hear from you sooner.",
        "It's good you introduced yourself at last.",
        "Next time, don't keep me waiting.",
    ],
    "beta_boost_servant": [
        "I've read your introduction carefully. I'm glad you're here.",
        "You've earned my attention. Stay close.",
        "Good. I was hoping you'd join us.",
        "I noticed you. That matters more than you think.",
        "You belong here… with me.",
    ],
    "puppy": [
        "Good boy.",
        "That's a good puppy.",
        "I like puppies who listen. You're doing well already.",
        "You did exactly what you were supposed to. Good boy.",
        "Come here. Good puppy.",
    ],
    "kitten": [
        "How sweet. You're curious, aren't you? I like kittens like that.",
        "You introduced yourself beautifully. Such a well-mannered little kitten.",
        "So attentive… I can already tell you enjoy being noticed.",
        "Good girl. I enjoy watching kittens settle in.",
        "You've found a comfortable spot already. Clever kitten.",
    ],
    "pet": [
        "It's nice to find a good pet like you.",
        "Be a good pet for me.",
        "You're doing well already. I like that.",
        "You belong here. Stay close.",
        "Good. I enjoy having pets who listen.",
    ],
    "devotee": [
        "I enjoyed reading your introduction.",
        "Thank you for sharing. I think you'll do well here.",
        "I'm glad you're here.",
        "Welcome. I'll be watching.",
        "Good. You may stay.",
    ],
}

# -----------------------------
# Obedience event config
# -----------------------------
# Event system configuration
EVENT_DURATION_SECONDS = 300  # 5 minutes
EVENT_COOLDOWN_SECONDS = 1800  # 30 minutes after event ends
EVENT_CHANNEL_ID = 1450533795156594738
EVENT_PHASE2_CHANNEL_ID = 1450628852345868369
EVENT_PHASE3_FAILED_CHANNEL_ID = 1450329944549752884
EVENT_PHASE3_SUCCESS_CHANNEL_ID = 1450329916146057266

# Allowed guilds - bot will leave any server not in this list
ALLOWED_GUILDS = {1407164448132698213}  # Main server ID

# Event 2 audio file - can be local path or URL
# For Wispbyte hosting, MUST use a URL (upload to cloud storage, GitHub, or file hosting service)
# Set EVENT_2_AUDIO environment variable to a URL for cloud hosting
EVENT_2_AUDIO = os.getenv("EVENT_2_AUDIO", None)

# Event tiers and scheduling - UK timezone
# Tier 1: 9:00 AM, 3:00 PM, 9:00 PM, 3:00 AM (4 times per day)
# Tier 2: 12:00 PM, 6:00 PM (2 times per day)
# Tier 3: 12:00 AM (1 time per day)
EVENT_SCHEDULE = {
    1: [(3, 0), (6, 0), (9, 0), (15, 0), (21, 0)],  # Tier 1: (hour, minute) in UK time
    2: [(12, 0), (18, 0)],                   # Tier 2: (hour, minute) in UK time
    3: [(0, 0)],                             # Tier 3: (hour, minute) in UK time
}

# Event tier assignments
EVENT_TIER_MAP = {
    1: 1,  # Presence Check - Tier 1
    2: 1,  # Silent Company - Tier 1
    3: 1,  # Hidden Reaction - Tier 1
    4: 2,  # Keyword Prompt - Tier 2
    5: 2,  # Direct Prompt - Tier 2
    6: 1,  # Choice Event - Tier 1
    7: 3,  # Collective Event - Tier 3
}

# Voice channels for Event 2
EVENT_2_VC_CHANNELS = [1451254356841332808]

# Event rewards
EVENT_REWARDS = {
    1: 30,   # Presence check - per message (10s cooldown)
    2: 50,   # Silent company - bonus XP at end
    3: 30,   # Hidden reaction
    4: 50,   # Keyword prompt
    5: 50,   # Direct prompt (20 XP for sorry replies)
    6: {"win": 100, "lose": -200},  # Choice event
    7: {
        "phase1": 50,  # Phase 1 button click
        "phase2_correct": 50,
        "phase2_wrong": -50,
    },
}

# Event 4 role IDs
EVENT_4_WOOF_ROLE = 1450589458675011726
EVENT_4_MEOW_ROLE = 1450685119684808867

# Event 4 channel IDs
EVENT_4_WOOF_CHANNEL_ID = 1450693708465967174
EVENT_4_MEOW_CHANNEL_ID = 1450693722512818196

# Event 7 role IDs
EVENT_7_OPT_IN_ROLE = 1450589443152023583
EVENT_7_SUCCESS_ROLE = 1450285064943571136
EVENT_7_FAILED_ROLE = 1450285246019928104

# Roles that should be cleared when no events are active
EVENT_CLEANUP_ROLES = [
    1450589458675011726,  # EVENT_4_WOOF_ROLE
    1450685119684808867,  # EVENT_4_MEOW_ROLE
    1450285064943571136,  # EVENT_7_SUCCESS_ROLE
    1450285112951574590,
    1450285211932823693,
    1450285246019928104,  # EVENT_7_FAILED_ROLE
    1450285257420181688,
    1450285259890364541,
    1450589443152023583,  # EVENT_7_OPT_IN_ROLE
]

COLLECTIVE_THRESHOLD = 10

# Command permission roles
ADMIN_ROLE_IDS = {1407164448132698221, 1407164448132698220}  # Admin commands
USER_COMMAND_ROLE_ID = 1407164448132698216  # User commands

# Command allowed channels
ADMIN_COMMAND_CHANNEL_ID = 1407164453094686762  # Admin commands only work here
USER_COMMAND_CHANNEL_ID = 1450107538019192832  # User commands only work here

# Channel permission roles
EVENT_PHASE2_ALLOWED_ROLE = 1450589443152023583  # Event 7 Phase 2 channel
EVENT_PHASE3_FAILED_ROLES = {1450285246019928104, 1450285257420181688, 1450285259890364541}  # Failure channel
EVENT_PHASE3_SUCCESS_ROLES = {1450285064943571136, 1450285112951574590, 1450285211932823693}  # Success channel

# Coin system
# 1 coin per 10 XP received
# Level up bonuses defined in LEVEL_COIN_BONUSES
LEVEL_COIN_BONUSES = {
    1: 10,
    2: 50,
    5: 100,
    10: 200,
    20: 300,
    30: 400,
    50: 500,
    75: 750,
    100: 1000,
}

# Command prefix
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

