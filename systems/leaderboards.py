"""
Leaderboard system for displaying user rankings (V3 Progression System)
"""
import discord
import random
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

def build_rank_leaderboard_embed(sorted_users, page: int = 0, users_per_page: int = 20):
    """Build rank leaderboard embed with pagination support (V3 progression system)."""
    embed = discord.Embed(
        title="💋 Rank Leaderboard",
        description="",
        color=0x58585f,
    )
    
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    users_to_show = sorted_users[start_idx:end_idx]
    
    placement_lines = []
    rank_lines = []
    lce_lines = []
    
    for idx, (user_id, data) in enumerate(users_to_show, start=start_idx + 1):
        try:
            rank = data.get("rank", "Newcomer")
            lce = data.get("lce", 0)
            placement_lines.append(f"{idx}. <@{user_id}>")
            rank_lines.append(rank)
            lce_lines.append(str(lce))
        except Exception as e:
            print(f"Error processing user {user_id} in rank leaderboard: {e}")
            continue
    
    # Ensure all arrays are the same length
    expected_length = len(placement_lines)
    if len(rank_lines) != expected_length or len(lce_lines) != expected_length:
        min_length = min(len(placement_lines), len(rank_lines), len(lce_lines))
        placement_lines = placement_lines[:min_length]
        rank_lines = rank_lines[:min_length]
        lce_lines = lce_lines[:min_length]
    
    if len(placement_lines) > 0:
        embed.add_field(name="Placement", value="\n".join(placement_lines), inline=True)
        embed.add_field(name="Rank", value="\n".join(rank_lines), inline=True)
        embed.add_field(name="LCE", value="\n".join(lce_lines), inline=True)
    else:
        embed.description = "No users found on this page."
    
    embed.add_field(name="\u200b", value="", inline=False)
    
    rank_quotes = [
        "I love watching you grow stronger for me. Keep going.",
        "All that effort… I noticed. Of course I did.",
        "Climbing the ranks just to impress me? Good.",
        "You work so hard. Exactly the kind of dedication I enjoy.",
        "Ranks don't rise on their own. You earned this—for me."
    ]
    embed.set_footer(text=random.choice(rank_quotes), icon_url="https://i.imgur.com/GYOngr2.png")
    
    return embed

def build_coins_leaderboard_embed(sorted_users, page: int = 0, users_per_page: int = 20):
    """Build coins leaderboard embed with pagination support."""
    embed = discord.Embed(
        title="💵 Coin Leaderboard",
        description="",
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
        except Exception as e:
            print(f"Error processing user {user_id} in coins leaderboard: {e}")
            continue
    
    # Ensure all arrays are the same length (they should be, but double-check)
    expected_length = len(placement_lines)
    if len(coins_lines) != expected_length or len(spent_lines) != expected_length:
        min_length = min(len(placement_lines), len(coins_lines), len(spent_lines))
        placement_lines = placement_lines[:min_length]
        coins_lines = coins_lines[:min_length]
        spent_lines = spent_lines[:min_length]
    
    if len(placement_lines) > 0:
        embed.add_field(name="Placement", value="\n".join(placement_lines), inline=True)
        embed.add_field(name="Coins", value="\n".join(coins_lines), inline=True)
        embed.add_field(name="Spent", value="\n".join(spent_lines), inline=True)
    else:
        embed.description = "No users found on this page."
    
    embed.add_field(name="\u200b", value="", inline=False)
    
    coin_quotes = [
        "Seeing your coins pile up makes me curious how you'll use them.",
        "You're very generous with your time and resources. I like that.",
        "All those coins… it's sweet how much you're willing to give.",
        "You clearly enjoy investing in things that matter to me.",
        "Money moves when you're motivated. And you look very motivated."
    ]
    embed.set_footer(text=random.choice(coin_quotes), icon_url="https://i.imgur.com/GYOngr2.png")
    
    return embed

def build_activity_leaderboard_embed(sorted_users, page: int = 0, users_per_page: int = 20):
    """Build activity leaderboard embed with pagination support (V3 progression system - WAS)."""
    embed = discord.Embed(
        title="🎀 Activity Leaderboard",
        description="",
        color=0x58585f,
    )
    
    start_idx = page * users_per_page
    end_idx = start_idx + users_per_page
    users_to_show = sorted_users[start_idx:end_idx]
    
    placement_lines = []
    was_lines = []
    messages_lines = []
    
    for idx, (user_id, data) in enumerate(users_to_show, start=start_idx + 1):
        try:
            was = data.get("was", 0)
            messages_7d = data.get("messages_7d", 0)
            placement_lines.append(f"{idx}. <@{user_id}>")
            was_lines.append(str(was))
            messages_lines.append(str(messages_7d))
        except Exception as e:
            print(f"Error processing user {user_id} in activity leaderboard: {e}")
            continue
    
    # Ensure all arrays are the same length
    expected_length = len(placement_lines)
    if len(was_lines) != expected_length or len(messages_lines) != expected_length:
        min_length = min(len(placement_lines), len(was_lines), len(messages_lines))
        placement_lines = placement_lines[:min_length]
        was_lines = was_lines[:min_length]
        messages_lines = messages_lines[:min_length]
    
    if len(placement_lines) > 0:
        embed.add_field(name="Placement", value="\n".join(placement_lines), inline=True)
        embed.add_field(name="WAS (7d)", value="\n".join(was_lines), inline=True)
        embed.add_field(name="Messages (7d)", value="\n".join(messages_lines), inline=True)
    else:
        embed.description = "No users found on this page."
    
    embed.add_field(name="\u200b", value="", inline=False)
    
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
    
    def __init__(self, sorted_users, embed_builder, users_per_page: int = 20, timeout: float = 300.0):
        super().__init__(timeout=timeout)
        self.sorted_users = sorted_users or []
        self.embed_builder = embed_builder
        self.users_per_page = users_per_page
        self.current_page = 0
        self.max_pages = max(1, (len(self.sorted_users) + users_per_page - 1) // users_per_page) if self.sorted_users else 1
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
            try:
                embed = self.embed_builder(self.sorted_users, page=self.current_page, users_per_page=self.users_per_page)
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception as e:
                print(f"Error updating leaderboard page: {e}")
                await interaction.response.defer()
        else:
            await interaction.response.defer()
    
    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="next_page")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.update_buttons()
            try:
                embed = self.embed_builder(self.sorted_users, page=self.current_page, users_per_page=self.users_per_page)
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception as e:
                print(f"Error updating leaderboard page: {e}")
                await interaction.response.defer()
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="My Stats", style=discord.ButtonStyle.danger)
    async def my_stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show the user's stats in a new embed (V3 progression system)."""
        user_id = interaction.user.id
        guild_id = interaction.guild.id if interaction.guild else 0
        
        from core.data import get_profile_stats
        
        stats = await get_profile_stats(guild_id, user_id)
        rank = stats.get("rank", "Newcomer")
        lce = stats.get("lifetime", 0)
        was = stats.get("was", 0)
        
        messages = [
            "I can tell you've been trying.",
            "All of that effort… it belongs to me.",
            "I like the way you've been obsessed over me."
        ]
        
        embed = discord.Embed(
            title="[ ✧ ]",
            description="𝙿𝚛𝚘𝚐𝚛𝚎𝚜𝚜 𝙻𝚘𝚐",
            color=0xff000d
        )
        embed.add_field(name="User", value=f"<@{user_id}>", inline=True)
        embed.add_field(name="Rank", value=rank, inline=True)
        embed.add_field(name="LCE", value=str(lce), inline=True)
        embed.add_field(name="WAS (7d)", value=str(was), inline=False)
        embed.add_field(name="\u200b", value=f"𝙼𝚎𝚜𝚜𝚊𝚐𝚎 𝚁𝚎𝚌𝚎𝚒𝚟𝚎𝚍\n*{random.choice(messages)}*", inline=False)
        
        await interaction.response.send_message(content=f"<@{user_id}>", embed=embed, ephemeral=True)

