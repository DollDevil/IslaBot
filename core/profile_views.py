"""
Profile embed builders for IslaBot V2
"""
import discord
from core.profile_stats import make_progress_bar, format_vc_time
from core.data import get_activity_quote, get_profile_stats
from core.config import LEVEL_ROLE_MAP

def build_profile_embed(member: discord.Member, stats: dict) -> discord.Embed:
    """Build the main profile embed"""
    embed = discord.Embed(
        description=stats["quote"],
        color=0x58585f
    )
    
    embed.set_author(
        name=f"{member.display_name}'s Profile",
        icon_url=member.display_avatar.url
    )
    
    # Get rank name from level
    rank_name = "Newcomer"
    for lvl, role_id in sorted(LEVEL_ROLE_MAP.items(), reverse=True):
        if stats["level"] >= lvl:
            role = member.guild.get_role(role_id)
            if role:
                rank_name = role.name
            break
    
    # Rank field
    progress_bar = make_progress_bar(stats["readiness_pct"])
    rank_value = f"🐾 {rank_name}\n⭐ {progress_bar} {stats['readiness_pct']}%\n{stats['blocker_text']}"
    embed.add_field(name="Rank", value=rank_value, inline=True)
    
    # Spacer
    embed.add_field(name="", value="", inline=False)
    
    # Wallet field
    wallet_value = f"🪙 {stats['coins']} Coins\n💰 {stats['lifetime']} Lifetime\n💸 {stats['tax']} Tax\n💳 {stats['debt']} Debt"
    embed.add_field(name="Wallet", value=wallet_value, inline=False)
    
    # Obedience field
    obedience_value = f"🧠 {stats['obedience']}%\n🔥 {stats['streak']}d streak"
    embed.add_field(name="Obedience", value=obedience_value, inline=False)
    
    # Spacer
    embed.add_field(name="", value="", inline=False)
    
    # Orders (three inline fields)
    embed.add_field(name="Orders Done", value=f"🟢 {stats['orders_done']}", inline=True)
    embed.add_field(name="Orders Late", value=f"🟡 {stats['orders_late']}", inline=True)
    embed.add_field(name="Orders Failed", value=f"🔴 {stats['orders_failed']}", inline=True)
    
    embed.set_footer(text="Use /profile info <category> for more information")
    
    return embed

def build_collection_embed(member: discord.Member, stats: dict) -> discord.Embed:
    """Build the collection embed"""
    embed = discord.Embed(
        description="Inventory recorded.",
        color=0x58585f
    )
    
    embed.set_author(
        name=f"{member.display_name}'s Collection",
        icon_url=member.display_avatar.url
    )
    
    # Equipped
    equipped_items = []
    if stats["equipped_collar"]:
        equipped_items.append(f"**Collar:** {stats['equipped_collar']}")
    if stats["equipped_badge"]:
        equipped_items.append(f"**Badge:** {stats['equipped_badge']}")
    equipped_text = "\n".join(equipped_items) if equipped_items else "None equipped"
    embed.add_field(name="Equipped", value=equipped_text, inline=False)
    
    # Badges
    badges = stats["badges_owned"]
    if badges:
        badges_text = ", ".join(badges[:10])
        if len(badges) > 10:
            badges_text += f" and {len(badges) - 10} more"
        embed.add_field(name="Badges", value=badges_text, inline=False)
    else:
        embed.add_field(name="Badges", value="No badges owned", inline=False)
    
    # Collars
    collars = stats["collars_owned"]
    if collars:
        collars_text = ", ".join(collars[:10])
        if len(collars) > 10:
            collars_text += f" and {len(collars) - 10} more"
        embed.add_field(name="Collars", value=collars_text, inline=False)
    else:
        embed.add_field(name="Collars", value="No collars owned", inline=False)
    
    # Interfaces
    interfaces = stats["interfaces_owned"]
    if interfaces:
        interfaces_text = ", ".join(interfaces[:10])
        if len(interfaces) > 10:
            interfaces_text += f" and {len(interfaces) - 10} more"
        embed.add_field(name="Interfaces", value=interfaces_text, inline=False)
    else:
        embed.add_field(name="Interfaces", value="No interfaces owned", inline=False)
    
    return embed

def build_profile_info_embed(member: discord.Member, category: str, stats: dict) -> discord.Embed:
    """Build detailed info embed for a specific category - matches /profile styling"""
    from core.profile_stats import make_progress_bar
    from core.config import LEVEL_ROLE_MAP
    
    # Get rank name from level
    rank_name = "Newcomer"
    for lvl, role_id in sorted(LEVEL_ROLE_MAP.items(), reverse=True):
        if stats["level"] >= lvl:
            role = member.guild.get_role(role_id)
            if role:
                rank_name = role.name
            break
    
    # Same styling as /profile
    embed = discord.Embed(
        description=stats["quote"],
        color=0x58585f
    )
    
    embed.set_author(
        name=f"{member.display_name}'s Profile",
        icon_url=member.display_avatar.url
    )
    
    # Category-specific fields
    if category == "rank":
        progress_bar = make_progress_bar(stats["readiness_pct"])
        rank_value = f"🐾 {rank_name}\n⭐ {progress_bar} {stats['readiness_pct']}%\n{stats['blocker_text']}"
        embed.add_field(name="Rank", value=rank_value, inline=True)
        
        embed.add_field(name="", value="", inline=False)  # Spacer
        
        # Requirements field
        requirements = f"✅ Coins: {stats['coins']}/0\n"
        if stats['obedience'] >= 50:
            requirements += "✅ Obedience: Met\n"
        else:
            requirements += "❌ Obedience: Not met\n"
        if stats['messages_sent'] >= 50 and stats['vc_minutes'] >= 60:
            requirements += "✅ Activity: Met\n"
        else:
            requirements += "❌ Activity: Not met\n"
        if stats['tax'] == 0 and stats['debt'] == 0:
            requirements += "✅ Discipline: Met"
        else:
            requirements += "❌ Discipline: Not met"
        embed.add_field(name="Requirements", value=requirements, inline=False)
        
        embed.add_field(name="", value="", inline=False)  # Spacer
        
        embed.add_field(name="Details", value="Blocker indicates what's preventing rank advancement. Complete requirements to unlock progress.", inline=False)
    
    elif category == "wallet":
        wallet_value = f"🪙 {stats['coins']} Coins\n💰 {stats['lifetime']} Lifetime\n💸 {stats['tax']} Tax\n💳 {stats['debt']} Debt"
        embed.add_field(name="Wallet", value=wallet_value, inline=False)
        
        embed.add_field(name="", value="", inline=False)  # Spacer
        
        embed.add_field(name="Recent Changes", value="Not tracked yet.", inline=False)
        
        embed.add_field(name="", value="", inline=False)  # Spacer
        
        on_cooldown, _ = None, None
        try:
            from core.data import check_daily_cooldown
            on_cooldown, _ = check_daily_cooldown(member.id)
        except:
            pass
        daily_status = "Ready" if not on_cooldown else "Claimed"
        embed.add_field(name="Weekly Claim", value=f"🎁 Status: {daily_status} • Next: Not tracked", inline=False)
    
    elif category == "obedience":
        obedience_value = f"🧠 {stats['obedience']}%\n🔥 {stats['streak']}d streak"
        embed.add_field(name="Obedience", value=obedience_value, inline=False)
        
        embed.add_field(name="", value="", inline=False)  # Spacer
        
        embed.add_field(name="How it's counted", value="Obedience is calculated from your activity, event participation, and consistency. Higher activity increases obedience.", inline=False)
        
        embed.add_field(name="", value="", inline=False)  # Spacer
        
        embed.add_field(name="Last 14 days", value=f"🟢 Done: {stats['orders_done']}\n🟡 Late: {stats['orders_late']}\n🔴 Failed: {stats['orders_failed']}", inline=False)
    
    elif category == "orders":
        if stats['orders_done'] == 0 and stats['orders_late'] == 0 and stats['orders_failed'] == 0:
            embed.add_field(name="Orders", value="Orders are not tracked yet.", inline=False)
        else:
            orders_value = f"🟢 Done: {stats['orders_done']}\n🟡 Late: {stats['orders_late']}\n🔴 Failed: {stats['orders_failed']}"
            embed.add_field(name="Orders", value=orders_value, inline=False)
        
        embed.add_field(name="", value="", inline=False)  # Spacer
        
        embed.add_field(name="Tip", value="Complete orders on time to improve Obedience.", inline=False)
    
    elif category == "activity":
        # Determine tier
        total_activity = stats['messages_sent'] + (stats['vc_minutes'] // 5)
        if total_activity >= 500:
            tier = "High"
        elif total_activity >= 200:
            tier = "Medium"
        else:
            tier = "Low"
        
        activity_value = f"💬 {stats['messages_sent']} messages (7d)\n🎧 {format_vc_time(stats['vc_minutes'])} VC (7d)\n👁 Tier: {tier}"
        embed.add_field(name="Activity", value=activity_value, inline=False)
        
        embed.add_field(name="", value="", inline=False)  # Spacer
        
        tip = "Send more messages and join voice chat to increase your activity tier."
        if tier == "High":
            tip = "Maintain your high activity to stay in good standing."
        embed.add_field(name="Tip", value=tip, inline=False)
    
    elif category == "discipline":
        discipline_value = f"💸 Tax: {stats['tax']}\n💳 Debt: {stats['debt']}"
        embed.add_field(name="Discipline", value=discipline_value, inline=False)
        
        embed.add_field(name="", value="", inline=False)  # Spacer
        
        embed.add_field(name="Details", value="Tax and debt are penalties for rule violations. Keep them at zero to maintain good standing.", inline=False)
    
    elif category == "inventory":
        items = []
        if stats["badges_owned"]:
            badges_list = stats['badges_owned'][:10]
            badges_text = ", ".join(badges_list)
            if len(stats['badges_owned']) > 10:
                badges_text += f" and {len(stats['badges_owned']) - 10} more"
            items.append(f"**Badges:** {badges_text}")
        if stats["collars_owned"]:
            collars_list = stats['collars_owned'][:10]
            collars_text = ", ".join(collars_list)
            if len(stats['collars_owned']) > 10:
                collars_text += f" and {len(stats['collars_owned']) - 10} more"
            items.append(f"**Collars:** {collars_text}")
        if stats["interfaces_owned"]:
            interfaces_list = stats['interfaces_owned'][:10]
            interfaces_text = ", ".join(interfaces_list)
            if len(stats['interfaces_owned']) > 10:
                interfaces_text += f" and {len(stats['interfaces_owned']) - 10} more"
            items.append(f"**Interfaces:** {interfaces_text}")
        
        if items:
            embed.add_field(name="Inventory", value="\n".join(items), inline=False)
        else:
            embed.add_field(name="Inventory", value="No items in inventory", inline=False)
    
    elif category == "badges":
        badges = stats["badges_owned"]
        if badges:
            badges_list = badges[:15]
            badges_text = "\n".join([f"• {badge}" for badge in badges_list])
            if len(badges) > 15:
                badges_text += f"\n... and {len(badges) - 15} more"
            embed.add_field(name="Badges", value=badges_text, inline=False)
        else:
            embed.add_field(name="Badges", value="No badges owned", inline=False)
    
    elif category == "memory":
        memories = []
        if stats["messages_sent"] > 100:
            memories.append("• Active in chat")
        if stats["vc_minutes"] > 300:
            memories.append("• Prefers voice chat")
        if stats["times_gambled"] > 10:
            memories.append("• Enjoys gambling")
        if stats["event_participations"] > 5:
            memories.append("• Participates in events")
        if not memories:
            memories.append("• New member")
        embed.add_field(name="Memory", value="\n".join(memories), inline=False)
    
    else:
        embed.add_field(name="Info", value=f"Category '{category}' not yet implemented.", inline=False)
    
    embed.set_footer(text="Use /profile to return • /profile info <category> for other categories")
    
    return embed

