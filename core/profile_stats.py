"""
Profile statistics and calculations for IslaBot V2
"""
from core.db import get_activity_7d, fetchone
from core.data import get_level, get_xp
from core.utils import next_level_requirement

# Rank advancement quotes
RANK_QUOTES = {
    ("positive", "stable"): "In Isla's favor. Keep this pace and advance.",
    ("positive", "neutral"): "In Isla's favor. Progress holds, but it isn't accelerating.",
    ("positive", "unstable"): "In Isla's favor. You are progressing, but not evenly.",
    ("neutral", "stable"): "In Isla's review. Your rank remains steady.",
    ("neutral", "neutral"): "In Isla's review. No significant change detected.",
    ("neutral", "unstable"): "In Isla's review. Minor fluctuations observed.",
    ("negative", "unstable"): "In Isla's disapproval. Instability detected.",
    ("negative", "neutral"): "In Isla's disapproval. Rank stability is failing.",
    ("negative", "stable"): "In Isla's disapproval. This rank is at risk.",
}

def make_progress_bar(pct: int, segments: int = 12) -> str:
    """Create a progress bar using ▰ and ▱"""
    filled = int((pct / 100) * segments)
    filled = max(0, min(segments, filled))  # Clamp between 0 and segments
    return "▰" * filled + "▱" * (segments - filled)

def safe_int(value, default=0):
    """Safely convert value to int, returning default if conversion fails"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def format_vc_time(minutes: int) -> str:
    """Format voice chat minutes as 'Xh Ym' or 'Ym'"""
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"

async def calculate_readiness_pct(guild_id, user_id):
    """Calculate readiness percentage based on XP progress toward next level"""
    from core.data import get_level, get_xp
    level = await get_level(user_id, guild_id=guild_id)
    xp = await get_xp(user_id, guild_id=guild_id)
    next_req = next_level_requirement(level)
    if next_req == 0:
        return 100
    pct = int(min(100, (xp / next_req) * 100))
    return pct

def calculate_blocker_locked(readiness_pct):
    """Determine if blocker is locked based on readiness"""
    return readiness_pct < 100

async def calculate_gates_failing_count(guild_id, user_id):
    """Calculate number of failing gates based on activity"""
    activity = await get_activity_7d(guild_id, user_id)
    messages_sent = activity["messages"]
    vc_minutes = activity["vc_minutes"]
    
    # Get gambling stats
    from core.db import fetchone
    profile = await fetchone(
        "SELECT times_gambled FROM user_profile WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    times_gambled = profile["times_gambled"] if profile else 0
    
    failing = 0
    
    # Gate 1: Messages (low threshold)
    if messages_sent < 50:
        failing += 1
    
    # Gate 2: VC time (low threshold)
    if vc_minutes < 60:  # Less than 1 hour
        failing += 1
    
    # Gate 3: Gambling ratio (if gambling too high relative to messages)
    if messages_sent > 0 and times_gambled > messages_sent * 0.5:
        failing += 1
    
    return failing

def determine_sentiment(readiness_pct, blocker_locked):
    """Determine sentiment: positive, neutral, or negative"""
    if readiness_pct >= 75:
        return "positive"
    if readiness_pct >= 60 and not blocker_locked:
        return "positive"
    if readiness_pct < 30:
        return "negative"
    return "neutral"

def determine_stability(readiness_pct, blocker_locked, gates_failing_count):
    """Determine stability: stable, neutral, or unstable"""
    if not blocker_locked or readiness_pct >= 70:
        return "stable"
    if readiness_pct < 40 or gates_failing_count >= 2:
        return "unstable"
    return "neutral"

def select_rank_quote(sentiment: str, stability: str) -> str:
    """Select rank advancement quote based on sentiment and stability"""
    key = (sentiment, stability)
    return RANK_QUOTES.get(key, RANK_QUOTES[("neutral", "neutral")])

# Note: get_profile_stats is now defined in core/data.py
# This module exports helper functions for profile stats calculations

