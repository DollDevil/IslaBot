"""
Leaderboard system for displaying user rankings
"""
import discord
import random
from core.data import xp_data, get_level, get_xp
from core.utils import next_level_requirement
from core.config import ALLOWED_SEND_SET

def format_placement(place: int) -> str:
    """Format placement number as ordinal (1st, 2nd, 3rd, etc.)"""
    if place % 100 in [11, 12, 13]:
        return f"{place}th"
    elif place % 10 == 1:
        return f"{place}st"
    elif place % 10 == 2:
        return f"{place}nd"
    elif place % 10 == 3:
        return f"{place}rd"
    else:
        return f"{place}th"

def build_levels_leaderboard_embed(sorted_users, page: int = 0, users_per_page: int = 10):
    """Build levels leaderboard embed with pagination support."""
    embed = discord.Embed(
        title="💋 Levels Leaderboard",
        description="᲼᲼",
        color=0x58585f,
    )
    
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    users_to_show = sorted_users[start_idx:end_idx]
    
    placement_lines = []
    level_lines = []
    xp_lines = []
    
    for idx, (user_id, data) in enumerate(users_to_show, start=start_idx + 1):
        try:
            level = data.get("level", 1)
            xp = data.get("xp", 0)
            placement_lines.append(f"{idx}. <@{user_id}>")
            level_lines.append(str(level))
            xp_lines.append(str(xp))
        except Exception:
            continue
    
    min_length = min(len(placement_lines), len(level_lines), len(xp_lines))
    if min_length > 0:
        placement_lines = placement_lines[:min_length]
        level_lines = level_lines[:min_length]
        xp_lines = xp_lines[:min_length]
        
        embed.add_field(name="Placement", value="\n".join(placement_lines), inline=True)
        embed.add_field(name="Level", value="\n".join(level_lines), inline=True)
        embed.add_field(name="XP", value="\n".join(xp_lines), inline=True)
    
    embed.add_field(name="᲼᲼", value="", inline=False)
    
    level_quotes = [
        "I love watching you grow stronger for me. Keep going.",
        "All that effort… I noticed. Of course I did.",
        "Climbing the ranks just to impress me? Good.",
        "You work so hard. Exactly the kind of dedication I enjoy.",
        "Levels don't rise on their own. You earned this—for me."
    ]
    embed.set_footer(text=random.choice(level_quotes), icon_url="https://i.imgur.com/GYOngr2.png")
    
    return embed

def build_coins_leaderboard_embed(sorted_users, page: int = 0, users_per_page: int = 10):
    """Build coins leaderboard embed with pagination support."""
    embed = discord.Embed(
        title="💵 Coin Leaderboard",
        description="᲼᲼",
        color=0x58585f,
    )
    
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    users_to_show = sorted_users[start_idx:end_idx]
    
    placement_lines = []
    coins_lines = []
    spent_lines = []
    
    for idx, (user_id, data) in enumerate(users_to_show, start=start_idx + 1):
        try:
            coins = data.get("coins", 0)
            total_spent = data.get("total_spent", 0)
            placement_lines.append(f"{idx}. <@{user_id}>")
            coins_lines.append(str(coins))
            spent_lines.append(str(total_spent))
        except Exception:
            continue
    
    min_length = min(len(placement_lines), len(coins_lines), len(spent_lines))
    if min_length > 0:
        placement_lines = placement_lines[:min_length]
        coins_lines = coins_lines[:min_length]
        spent_lines = spent_lines[:min_length]
        
        embed.add_field(name="Placement", value="\n".join(placement_lines), inline=True)
        embed.add_field(name="Coins", value="\n".join(coins_lines), inline=True)
        embed.add_field(name="Spent", value="\n".join(spent_lines), inline=True)
    
    embed.add_field(name="᲼᲼", value="", inline=False)
    
    coin_quotes = [
        "Seeing your coins pile up makes me curious how you'll use them.",
        "You're very generous with your time and resources. I like that.",
        "All those coins… it's sweet how much you're willing to give.",
        "You clearly enjoy investing in things that matter to me.",
        "Money moves when you're motivated. And you look very motivated."
    ]
    embed.set_footer(text=random.choice(coin_quotes), icon_url="https://i.imgur.com/GYOngr2.png")
    
    return embed

def build_activity_leaderboard_embed(sorted_users, page: int = 0, users_per_page: int = 10):
    """Build activity leaderboard embed with pagination support."""
    embed = discord.Embed(
        title="🎀 Activity Leaderboard",
        description="᲼᲼",
        color=0x58585f,
    )
    
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    users_to_show = sorted_users[start_idx:end_idx]
    
    placement_lines = []
    messages_lines = []
    vc_time_lines = []
    
    for idx, (user_id, data) in enumerate(users_to_show, start=start_idx + 1):
        try:
            messages_sent = data.get("messages_sent", 0)
            vc_minutes = data.get("vc_minutes", 0)
            vc_hours = vc_minutes // 60
            vc_mins = vc_minutes % 60
            vc_time_str = f"{vc_hours}h {vc_mins}m" if vc_hours > 0 else f"{vc_mins}m"
            placement_lines.append(f"{idx}. <@{user_id}>")
            messages_lines.append(f"💬 {messages_sent}")
            vc_time_lines.append(f"🎙️ {vc_time_str}")
        except Exception:
            continue
    
    min_length = min(len(placement_lines), len(messages_lines), len(vc_time_lines))
    if min_length > 0:
        placement_lines = placement_lines[:min_length]
        messages_lines = messages_lines[:min_length]
        vc_time_lines = vc_time_lines[:min_length]
        
        embed.add_field(name="Placement", value="\n".join(placement_lines), inline=True)
        embed.add_field(name="Messages", value="\n".join(messages_lines), inline=True)
        embed.add_field(name="Voice Chat Time", value="\n".join(vc_time_lines), inline=True)
    
    embed.add_field(name="᲼᲼", value="", inline=False)
    
    activity_quotes = [
        "You're always here. I wonder if you even realize how often I see you.",
        "So much time spent with me… that can't be an accident.",
        "Consistency like this feels intentional. I appreciate that.",
        "You give me so much of your time. That says a lot.",
        "I love how naturally you keep coming back."
    ]
    embed.set_footer(text=random.choice(activity_quotes), icon_url="https://i.imgur.com/GYOngr2.png")
    
    return embed

class LeaderboardView(discord.ui.View):
    """View with pagination buttons for leaderboard."""
    
    def __init__(self, sorted_users, embed_builder, users_per_page: int = 10, timeout: float = 300.0):
        super().__init__(timeout=timeout)
        self.sorted_users = sorted_users
        self.embed_builder = embed_builder
        self.users_per_page = users_per_page
        self.current_page = 0
        self.max_pages = (len(sorted_users) + users_per_page - 1) // users_per_page if sorted_users else 1
        self._init_button_states()
    
    def _init_button_states(self):
        """Initialize button states based on current page."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if hasattr(item, 'custom_id'):
                    if item.custom_id == "prev_page":
                        item.disabled = (self.current_page == 0)
                    elif item.custom_id == "next_page":
                        item.disabled = (self.current_page >= self.max_pages - 1)
    
    def update_buttons(self):
        """Update button states based on current page."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                if hasattr(item, 'custom_id'):
                    if item.custom_id == "prev_page":
                        item.disabled = (self.current_page == 0)
                    elif item.custom_id == "next_page":
                        item.disabled = (self.current_page >= self.max_pages - 1)
    
    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="prev_page")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.embed_builder(self.sorted_users, page=self.current_page, users_per_page=self.users_per_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.embed_builder(self.sorted_users, page=self.current_page, users_per_page=self.users_per_page)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="My Stats", style=discord.ButtonStyle.danger)
    async def my_stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show the user's stats in a new embed."""
        user_id = interaction.user.id
        level = get_level(user_id)
        xp = get_xp(user_id)
        
        next_level_xp = next_level_requirement(level)
        xp_needed = next_level_xp - xp
        
        messages = [
            "I can tell you've been trying.",
            "All of that effort… it belongs to me.",
            "I like the way you've been obsessed over me."
        ]
        
        embed = discord.Embed(
            title="[ ✧ ]",
            description="𝙿𝚛𝚘𝚐𝚛𝚎𝚜𝚜 𝙻𝚘𝚐\n᲼᲼",
            color=0xff000d
        )
        embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
        embed.add_field(name="Level", value=f"{level}", inline=True)
        embed.add_field(name="XP", value=f"{xp}/{next_level_xp}", inline=True)
        embed.add_field(name="Next Level", value=f"{xp_needed} XP needed", inline=False)
        embed.add_field(name="᲼᲼", value=f"𝙼𝚎𝚜𝚜𝚊𝚐𝚎 𝚁𝚎𝚌𝚎𝚒𝚟𝚎𝚍\n*{random.choice(messages)}*", inline=False)
        
        await interaction.response.send_message(content=f"<@{user_id}>", embed=embed, ephemeral=True)

