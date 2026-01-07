"""
V3 Progression System - Core computation logic
Based on Coins, Obedience14, Activity/WAS, Orders, Tax, Debt, and Rank ladder
"""
import datetime
from core.db import fetchone, fetchall, execute, _now_iso, _today_str

# Rank ladder based on Lifetime Coins Earned (LCE)
RANK_LADDER = [
    {"name": "Newcomer", "lce_min": 0, "lce_max": 999},
    {"name": "Follower", "lce_min": 1000, "lce_max": 4999},
    {"name": "Devotee", "lce_min": 5000, "lce_max": 14999},
    {"name": "Servant", "lce_min": 15000, "lce_max": 49999},
    {"name": "Submissive", "lce_min": 50000, "lce_max": 99999},
    {"name": "Obedient", "lce_min": 100000, "lce_max": 249999},
    {"name": "Loyal", "lce_min": 250000, "lce_max": 499999},
    {"name": "Dedicated", "lce_min": 500000, "lce_max": 999999},
    {"name": "Devoted", "lce_min": 1000000, "lce_max": 4999999},
    {"name": "Master", "lce_min": 5000000, "lce_max": None},
]

# Gates for eligible rank (minimum requirements)
GATES = {
    "Newcomer": [],
    "Follower": [{"type": "messages_7d", "min": 10}, {"type": "was", "min": 100}],
    "Devotee": [{"type": "messages_7d", "min": 30}, {"type": "was", "min": 300}, {"type": "obedience14", "min": 50}],
    "Servant": [{"type": "messages_7d", "min": 50}, {"type": "was", "min": 500}, {"type": "obedience14", "min": 60}],
    "Submissive": [{"type": "messages_7d", "min": 100}, {"type": "was", "min": 1000}, {"type": "obedience14", "min": 70}],
    "Obedient": [{"type": "messages_7d", "min": 200}, {"type": "was", "min": 2000}, {"type": "obedience14", "min": 80}],
    "Loyal": [{"type": "messages_7d", "min": 400}, {"type": "was", "min": 4000}, {"type": "obedience14", "min": 85}],
    "Dedicated": [{"type": "messages_7d", "min": 600}, {"type": "was", "min": 6000}, {"type": "obedience14", "min": 90}],
    "Devoted": [{"type": "messages_7d", "min": 1000}, {"type": "was", "min": 10000}, {"type": "obedience14", "min": 95}],
    "Master": [{"type": "messages_7d", "min": 2000}, {"type": "was", "min": 20000}, {"type": "obedience14", "min": 98}],
}

async def compute_dap_for_day(guild_id: int, user_id: int, day: str) -> int:
    """Compute Daily Activity Points (DAP) for a specific day with caps per spec"""
    row = await fetchone(
        "SELECT messages, vc_minutes, events, presence_ticks FROM activity_daily WHERE guild_id = ? AND user_id = ? AND day = ?",
        (guild_id, user_id, day)
    )
    
    if not row:
        return 0
    
    messages = row["messages"] or 0
    vc_minutes = row["vc_minutes"] or 0
    events = row["events"] or 0
    presence_ticks = row["presence_ticks"] or 0
    
    # DAP formula: messages + (vc_minutes / 2) + (events * 10) + (presence_ticks * 2)
    # With caps: messages max 100/day, vc_minutes max 480/day (8 hours), events max 10/day
    messages_capped = min(messages, 100)
    vc_minutes_capped = min(vc_minutes, 480)
    events_capped = min(events, 10)
    
    dap = messages_capped + (vc_minutes_capped // 2) + (events_capped * 10) + (presence_ticks * 2)
    return dap

async def compute_was(guild_id: int, user_id: int) -> int:
    """Compute Weekly Activity Score (WAS) from last 7 days activity_daily"""
    seven_days_ago = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7)).date().isoformat()
    
    rows = await fetchall(
        "SELECT day FROM activity_daily WHERE guild_id = ? AND user_id = ? AND day >= ? ORDER BY day",
        (guild_id, user_id, seven_days_ago)
    )
    
    was = 0
    for row in rows:
        day = row["day"]
        dap = await compute_dap_for_day(guild_id, user_id, day)
        was += dap
    
    return was

async def compute_obedience14(guild_id: int, user_id: int) -> dict:
    """Compute Obedience14 from last 14 days order_runs with streak bonus and decay rule"""
    fourteen_days_ago = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=14)).date().isoformat()
    
    rows = await fetchall(
        """SELECT accepted_at, completed_at, status, completed_late 
           FROM order_runs 
           WHERE guild_id = ? AND user_id = ? AND accepted_at >= ? 
           ORDER BY accepted_at""",
        (guild_id, user_id, fourteen_days_ago)
    )
    
    done = 0
    late = 0
    failed = 0
    
    for row in rows:
        status = row["status"]
        completed_late = row["completed_late"]
        
        if status == "completed":
            if completed_late:
                late += 1
            else:
                done += 1
        elif status == "failed":
            failed += 1
    
    total_orders = done + late + failed
    
    # Obedience14 = (done * 100 + late * 50 - failed * 25) / max(total_orders, 1) * 100
    # Minimum 0, maximum 100
    if total_orders == 0:
        obedience_pct = 50  # Default if no orders
    else:
        obedience_score = (done * 100) + (late * 50) - (failed * 25)
        obedience_pct = max(0, min(100, (obedience_score / total_orders)))
    
    # Calculate streak (consecutive completed orders without failure)
    streak_days = 0
    if rows:
        # Count backwards from most recent
        for row in reversed(rows):
            if row["status"] == "completed":
                streak_days += 1
            elif row["status"] == "failed":
                break
    
    # Apply streak bonus: +1% per day of streak, max +10%
    streak_bonus = min(10, streak_days)
    obedience_pct = min(100, obedience_pct + streak_bonus)
    
    # Decay rule: if no orders completed today, reduce by 1%
    today = _today_str()
    today_completed = await fetchone(
        """SELECT COUNT(*) as count FROM order_runs 
           WHERE guild_id = ? AND user_id = ? AND status = 'completed' 
           AND DATE(completed_at) = ?""",
        (guild_id, user_id, today)
    )
    
    if today_completed and today_completed["count"] == 0:
        obedience_pct = max(0, obedience_pct - 1)
    
    return {
        "obedience_pct": int(obedience_pct),
        "streak_days": streak_days,
        "done": done,
        "late": late,
        "failed": failed,
        "total": total_orders
    }

def compute_coin_rank(lce: int) -> str:
    """Compute rank based on Lifetime Coins Earned"""
    for rank in reversed(RANK_LADDER):
        if lce >= rank["lce_min"]:
            if rank["lce_max"] is None or lce <= rank["lce_max"]:
                return rank["name"]
    return "Newcomer"

async def compute_eligible_rank(guild_id: int, user_id: int) -> dict:
    """Compute eligible rank based on gates (minimum requirements)"""
    # Get current metrics
    activity = await get_activity_7d(guild_id, user_id)
    was = await compute_was(guild_id, user_id)
    obedience = await compute_obedience14(guild_id, user_id)
    
    messages_7d = activity["messages"]
    was_score = was
    obedience14 = obedience["obedience_pct"]
    
    # Find highest rank where all gates are passed
    eligible_rank = "Newcomer"
    for rank_name, gates in GATES.items():
        if not gates:
            eligible_rank = rank_name
            continue
        
        all_gates_passed = True
        for gate in gates:
            gate_type = gate["type"]
            gate_min = gate["min"]
            
            if gate_type == "messages_7d" and messages_7d < gate_min:
                all_gates_passed = False
                break
            elif gate_type == "was" and was_score < gate_min:
                all_gates_passed = False
                break
            elif gate_type == "obedience14" and obedience14 < gate_min:
                all_gates_passed = False
                break
        
        if all_gates_passed:
            eligible_rank = rank_name
    
    return {
        "rank": eligible_rank,
        "messages_7d": messages_7d,
        "was": was_score,
        "obedience14": obedience14
    }

async def compute_final_rank(guild_id: int, user_id: int, lce: int) -> dict:
    """Compute final rank: min(coin_rank, eligible_rank)"""
    coin_rank = compute_coin_rank(lce)
    eligible_data = await compute_eligible_rank(guild_id, user_id)
    eligible_rank = eligible_data["rank"]
    
    # Convert ranks to indices to compare
    rank_names = [r["name"] for r in RANK_LADDER]
    coin_idx = rank_names.index(coin_rank) if coin_rank in rank_names else 0
    eligible_idx = rank_names.index(eligible_rank) if eligible_rank in rank_names else 0
    
    final_idx = min(coin_idx, eligible_idx)
    final_rank = rank_names[final_idx]
    
    return {
        "coin_rank": coin_rank,
        "eligible_rank": eligible_rank,
        "final_rank": final_rank,
        "eligible_data": eligible_data
    }

async def compute_readiness_pct(guild_id: int, user_id: int, next_rank_name: str) -> int:
    """Compute readiness percentage toward next rank (weighted progress across gates)"""
    if next_rank_name not in GATES:
        return 100
    
    gates = GATES[next_rank_name]
    if not gates:
        return 100
    
    # Get current metrics
    activity = await get_activity_7d(guild_id, user_id)
    was = await compute_was(guild_id, user_id)
    obedience = await compute_obedience14(guild_id, user_id)
    
    messages_7d = activity["messages"]
    was_score = was
    obedience14 = obedience["obedience_pct"]
    
    # Calculate progress for each gate
    total_progress = 0
    total_weight = 0
    
    for gate in gates:
        gate_type = gate["type"]
        gate_min = gate["min"]
        weight = 1  # Equal weight for now
        
        if gate_type == "messages_7d":
            progress = min(100, int((messages_7d / gate_min) * 100)) if gate_min > 0 else 100
        elif gate_type == "was":
            progress = min(100, int((was_score / gate_min) * 100)) if gate_min > 0 else 100
        elif gate_type == "obedience14":
            progress = min(100, int((obedience14 / gate_min) * 100)) if gate_min > 0 else 100
        else:
            progress = 0
        
        total_progress += progress * weight
        total_weight += weight
    
    readiness_pct = int(total_progress / total_weight) if total_weight > 0 else 0
    return min(100, readiness_pct)

async def compute_blocker(guild_id: int, user_id: int, next_rank_name: str) -> str:
    """Find the most limiting gate; show (current/required) or (current <= limit)"""
    if next_rank_name not in GATES:
        return "🔓 Ready"
    
    gates = GATES[next_rank_name]
    if not gates:
        return "🔓 Ready"
    
    # Get current metrics
    activity = await get_activity_7d(guild_id, user_id)
    was = await compute_was(guild_id, user_id)
    obedience = await compute_obedience14(guild_id, user_id)
    
    messages_7d = activity["messages"]
    was_score = was
    obedience14 = obedience["obedience_pct"]
    
    # Find the gate with lowest progress percentage
    worst_gate = None
    worst_progress = 100
    
    for gate in gates:
        gate_type = gate["type"]
        gate_min = gate["min"]
        
        if gate_type == "messages_7d":
            progress = (messages_7d / gate_min) * 100 if gate_min > 0 else 100
            if progress < worst_progress:
                worst_progress = progress
                worst_gate = {"type": "Messages (7d)", "current": messages_7d, "required": gate_min}
        elif gate_type == "was":
            progress = (was_score / gate_min) * 100 if gate_min > 0 else 100
            if progress < worst_progress:
                worst_progress = progress
                worst_gate = {"type": "WAS", "current": was_score, "required": gate_min}
        elif gate_type == "obedience14":
            progress = (obedience14 / gate_min) * 100 if gate_min > 0 else 100
            if progress < worst_progress:
                worst_progress = progress
                worst_gate = {"type": "Obedience", "current": obedience14, "required": gate_min}
    
    if worst_gate and worst_progress < 100:
        return f"🚧 {worst_gate['type']} ({worst_gate['current']}/{worst_gate['required']})"
    
    return "🔓 Ready"

async def weekly_claim_amount(guild_id: int, user_id: int, was: int, obedience14: int, streak_days: int) -> dict:
    """Calculate weekly claim amount with clamps + garnish to debt"""
    # Base formula: WAS / 10 + (Obedience14 / 10) + (Streak * 5)
    base_amount = (was // 10) + (obedience14 // 10) + (streak_days * 5)
    
    # Clamp between 50 and 5000
    claim_amount = max(50, min(5000, base_amount))
    
    # Garnish to debt: 10% goes to debt if debt > 0
    debt_row = await fetchone(
        "SELECT debt FROM discipline_state WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id)
    )
    debt = debt_row["debt"] if debt_row else 0
    
    garnish_amount = 0
    if debt > 0:
        garnish_amount = int(claim_amount * 0.10)
        claim_amount -= garnish_amount
    
    return {
        "claim_amount": claim_amount,
        "garnish_amount": garnish_amount,
        "base_amount": base_amount
    }

# Import helper function
async def get_activity_7d(guild_id: int, user_id: int):
    """Get activity stats for last 7 days"""
    from core.db import get_activity_7d as _get_activity_7d
    return await _get_activity_7d(guild_id, user_id)

