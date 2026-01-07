"""
Onboarding system for new members - welcome messages, rules, verification flow
"""
import discord
import json
import os
import re

# Bot instance (set by main.py)
bot = None

# Configuration storage file
ONBOARDING_CONFIG_FILE = "data/onboarding_config.json"

# Default role IDs (can be overridden by configuration)
DEFAULT_UNVERIFIED_ROLE_ID = 1449944412632383669
DEFAULT_VERIFIED_ROLE_ID = 1407164448132698216  # Devotee
DEFAULT_BAD_PUP_ROLE_ID = 1456361753674911745

# Onboarding configuration structure
onboarding_config = {
    "channel_id": None,  # Channel to send onboarding messages
    "roles": {
        "Unverified": None,
        "Verified": None,
        "Bad Pup": None
    }
}

def set_bot(bot_instance):
    """Set the bot instance for this module"""
    global bot
    bot = bot_instance

def load_onboarding_config():
    """Load onboarding configuration from file"""
    global onboarding_config
    if os.path.exists(ONBOARDING_CONFIG_FILE):
        try:
            with open(ONBOARDING_CONFIG_FILE, "r") as f:
                onboarding_config = json.load(f)
        except Exception as e:
            print(f"Error loading onboarding config: {e}")
            onboarding_config = {
                "channel_id": None,
                "roles": {
                    "Unverified": None,
                    "Verified": None,
                    "Bad Pup": None
                }
            }
    else:
        # Initialize with defaults
        onboarding_config = {
            "channel_id": None,
            "roles": {
                "Unverified": str(DEFAULT_UNVERIFIED_ROLE_ID),
                "Verified": str(DEFAULT_VERIFIED_ROLE_ID),
                "Bad Pup": str(DEFAULT_BAD_PUP_ROLE_ID)
            }
        }
        save_onboarding_config()

def save_onboarding_config():
    """Save onboarding configuration to file"""
    try:
        os.makedirs(os.path.dirname(ONBOARDING_CONFIG_FILE), exist_ok=True)
        with open(ONBOARDING_CONFIG_FILE, "w") as f:
            json.dump(onboarding_config, f, indent=4)
    except Exception as e:
        print(f"Error saving onboarding config: {e}")

def get_onboarding_channel_id():
    """Get the configured onboarding channel ID"""
    return onboarding_config.get("channel_id")

def get_role_id(role_type):
    """Get role ID for a specific role type (Unverified, Verified, Bad Pup)"""
    role_id = onboarding_config.get("roles", {}).get(role_type)
    if role_id:
        return int(role_id)
    # Fallback to defaults
    defaults = {
        "Unverified": DEFAULT_UNVERIFIED_ROLE_ID,
        "Verified": DEFAULT_VERIFIED_ROLE_ID,
        "Bad Pup": DEFAULT_BAD_PUP_ROLE_ID
    }
    return defaults.get(role_type)

def set_onboarding_channel(channel_id):
    """Set the onboarding channel ID"""
    onboarding_config["channel_id"] = int(channel_id)
    save_onboarding_config()

def set_role(role_type, role_id):
    """Set a role ID for a specific role type"""
    if "roles" not in onboarding_config:
        onboarding_config["roles"] = {}
    onboarding_config["roles"][role_type] = str(int(role_id))
    save_onboarding_config()

def has_bad_pup_role(member):
    """Check if member has Bad Pup role"""
    if not isinstance(member, discord.Member):
        return False
    bad_pup_role_id = get_role_id("Bad Pup")
    return any(int(role.id) == bad_pup_role_id for role in member.roles)

async def send_onboarding_welcome(member):
    """Send the welcome message when a user joins"""
    channel_id = get_onboarding_channel_id()
    if not channel_id:
        print(f"Onboarding channel not configured, skipping welcome for {member.name}")
        return
    
    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"Could not find onboarding channel {channel_id}")
        return
    
    embed = discord.Embed(
        description=f"**{member.guild.name}:** *New User Detected*\n> User: <@{member.id}>\n> Status: Connected\n\n**Instruction:** *Follow the procedure to gain full access.*",
        colour=0x65566c
    )
    
    embed.set_author(
        name="𝚂𝚢𝚜𝚝𝚎𝚖 𝙼𝚎𝚜𝚜𝚊𝚐𝚎",
        icon_url="https://i.imgur.com/irmCXhw.gif"
    )
    
    embed.set_footer(
        text="Having issues? Type /support",
        icon_url="https://i.imgur.com/irmCXhw.gif"
    )
    
    view = RulesButtonView()
    await channel.send(content=f"<@{member.id}>", embed=embed, view=view)

async def send_onboarding_rules(interaction_or_channel, user=None, is_reply=False):
    """Send the rules message"""
    embed = discord.Embed(
        description="<a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682>",
        colour=0x65566c
    )
    
    embed.set_author(
        name="𝚂𝚢𝚜𝚝𝚎𝚖 𝚁𝚞𝚕𝚎𝚜",
        icon_url="https://i.imgur.com/irmCXhw.gif"
    )
    
    embed.add_field(
        name="1. Respect the Operator.",
        value="> Harassment, hate speech and disrespect will result in immediate removal.",
        inline=False
    )
    embed.add_field(
        name="2. Stay On-Topic.",
        value="> Use the correct channels to keep the system clean.",
        inline=False
    )
    embed.add_field(
        name="3. No Spam or Self-Promo.",
        value="> Do not spam, this includes mass pings and all promo.",
        inline=False
    )
    embed.add_field(
        name="4. No Spoilers.",
        value="> Do not spoil Isla's programs.",
        inline=False
    )
    embed.add_field(
        name="5. <:dmsoff:1454433182890987602> Do Not DM Isla.",
        value="> DMs to Isla require a fee in advance.",
        inline=False
    )
    embed.add_field(
        name="",
        value="<a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682><a:blacksparklies:1454433776649113682>",
        inline=False
    )
    
    view = RulesAcceptDeclineView()
    
    if isinstance(interaction_or_channel, discord.Interaction):
        if is_reply:
            await interaction_or_channel.response.send_message(content=f"<@{user.id}>" if user else None, embed=embed, view=view, ephemeral=True)
        else:
            await interaction_or_channel.response.send_message(content=f"||<@{user.id}>||" if user else None, embed=embed, view=view)
    else:
        # It's a channel
        await interaction_or_channel.send(content=f"||<@{user.id}>||" if user else None, embed=embed, view=view)

async def send_rules_accept_1(interaction, member):
    """Send first accept message and give verified role"""
    embed = discord.Embed(
        description=f"Verification complete.\n<a:verifyredv2:1454436023735160923> Access unlocked.\n\nUser experience initialization started.\n<:msg3:1454433017438277652> System message transmitted to <@{member.id}> via DM.",
        colour=0x080707
    )
    
    embed.set_author(
        name="𝚂𝚢𝚜𝚝𝚎𝚖 𝙼𝚎𝚜𝚜𝚊𝚐𝚎",
        icon_url="https://i.imgur.com/irmCXhw.gif"
    )
    
    # Give verified role
    verified_role_id = get_role_id("Verified")
    if verified_role_id:
        role = member.guild.get_role(verified_role_id)
        if role:
            try:
                await member.add_roles(role, reason="Onboarding: Rules accepted")
                print(f"Added Verified role to {member.name}")
            except Exception as e:
                print(f"Error adding Verified role: {e}")
    
    # Remove unverified role
    unverified_role_id = get_role_id("Unverified")
    if unverified_role_id:
        role = member.guild.get_role(unverified_role_id)
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason="Onboarding: Verified")
            except Exception as e:
                print(f"Error removing Unverified role: {e}")
    
    await interaction.response.send_message(content=f"<@{member.id}>", embed=embed, ephemeral=True)

async def send_rules_decline_1(interaction, member):
    """Send first decline message"""
    embed = discord.Embed(
        description="You pressed decline... how bold. Turn around and submit properly <a:breakingmyheart:1454436063169745070>",
        colour=0x080707
    )
    
    embed.set_author(
        name="𝙴𝚛𝚛𝚘𝚛",
        icon_url="https://i.imgur.com/QJQjYkE.gif"
    )
    
    view = RulesAcceptDeclineView2()
    await interaction.response.send_message(content=f"<@{member.id}>", embed=embed, view=view, ephemeral=True)

async def send_rules_accept_2(interaction, member):
    """Send second accept message (after decline) and give verified role"""
    embed = discord.Embed(
        description="You declined... then gave in. I like puppies who learn to submit to their owner.",
        colour=0x080707
    )
    
    embed.set_author(
        name="𝙴𝚛𝚛𝚘𝚛",
        icon_url="https://i.imgur.com/QJQjYkE.gif"
    )
    
    # Give verified role
    verified_role_id = get_role_id("Verified")
    if verified_role_id:
        role = member.guild.get_role(verified_role_id)
        if role:
            try:
                await member.add_roles(role, reason="Onboarding: Rules accepted after decline")
                print(f"Added Verified role to {member.name}")
            except Exception as e:
                print(f"Error adding Verified role: {e}")
    
    # Remove unverified role
    unverified_role_id = get_role_id("Unverified")
    if unverified_role_id:
        role = member.guild.get_role(unverified_role_id)
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason="Onboarding: Verified after decline")
            except Exception as e:
                print(f"Error removing Unverified role: {e}")
    
    await interaction.response.send_message(content=f"<@{member.id}>", embed=embed, ephemeral=True)

async def send_rules_decline_2(interaction, member):
    """Send second decline message and give Bad Pup role"""
    embed = discord.Embed(
        description="You pushed too far this time.\nYour last chance to redeem yourself—type this word for word, and I'll let it slide:\n`I apologize Goddess. I was foolish to decline. I fully submit to your rules now.`\n\nGo on. Type it.",
        colour=0x080707
    )
    
    embed.set_author(
        name="𝙴𝚛𝚛𝚘𝚛",
        icon_url="https://i.imgur.com/QJQjYkE.gif"
    )
    
    # Give Bad Pup role
    bad_pup_role_id = get_role_id("Bad Pup")
    if bad_pup_role_id:
        role = member.guild.get_role(bad_pup_role_id)
        if role:
            try:
                await member.add_roles(role, reason="Onboarding: Declined rules twice")
                print(f"Added Bad Pup role to {member.name}")
            except Exception as e:
                print(f"Error adding Bad Pup role: {e}")
    
    await interaction.response.send_message(content=f"<@{member.id}>", embed=embed, ephemeral=True)

async def send_rules_submission_false(interaction_or_channel, member):
    """Send false submission message"""
    embed = discord.Embed(
        description="That wasn't what I asked for. Be precise, pup.\n\nI want every word as I wrote it:\n`I apologize Goddess. I was foolish to decline. I fully submit to your rules now.`",
        colour=0x080707
    )
    
    embed.set_author(
        name="𝙴𝚛𝚛𝚘𝚛",
        icon_url="https://i.imgur.com/QJQjYkE.gif"
    )
    
    if isinstance(interaction_or_channel, discord.Interaction):
        await interaction_or_channel.response.send_message(content=f"<@{member.id}>", embed=embed, ephemeral=True)
    else:
        # It's a message, reply to it
        await interaction_or_channel.reply(content=f"<@{member.id}>", embed=embed)

async def send_rules_submission_correct(message_or_channel, member):
    """Send correct submission message, remove Bad Pup role, give verified role"""
    embed = discord.Embed(
        description="You actually think that's enough? \nAfter defying me twice?\n\nSend a proper tribute to my [Throne](https://throne.com/lsla). Then maybe I'll soften.",
        colour=0x080707
    )
    
    embed.set_author(
        name="𝙴𝚛𝚛𝚘𝚛",
        icon_url="https://i.imgur.com/QJQjYkE.gif"
    )
    
    embed.set_footer(text="I'll verify you for now, but this is the final warning.")
    
    # Remove Bad Pup role
    bad_pup_role_id = get_role_id("Bad Pup")
    if bad_pup_role_id:
        role = member.guild.get_role(bad_pup_role_id)
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason="Onboarding: Correct submission")
                print(f"Removed Bad Pup role from {member.name}")
            except Exception as e:
                print(f"Error removing Bad Pup role: {e}")
    
    # Give verified role
    verified_role_id = get_role_id("Verified")
    if verified_role_id:
        role = member.guild.get_role(verified_role_id)
        if role:
            try:
                await member.add_roles(role, reason="Onboarding: Correct submission after Bad Pup")
                print(f"Added Verified role to {member.name}")
            except Exception as e:
                print(f"Error adding Verified role: {e}")
    
    # Remove unverified role
    unverified_role_id = get_role_id("Unverified")
    if unverified_role_id:
        role = member.guild.get_role(unverified_role_id)
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason="Onboarding: Verified after submission")
            except Exception as e:
                print(f"Error removing Unverified role: {e}")
    
    if isinstance(message_or_channel, discord.Message):
        await message_or_channel.reply(content=f"<@{member.id}>", embed=embed)
    else:
        await message_or_channel.send(content=f"<@{member.id}>", embed=embed)

def normalize_text(text):
    """Normalize text for comparison (case-insensitive, ignore symbols)"""
    # Convert to lowercase and remove all non-alphanumeric characters except spaces
    normalized = re.sub(r'[^a-z0-9\s]', '', text.lower())
    # Collapse multiple spaces into single space and strip
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def check_submission_text(message_content):
    """Check if message matches the required submission text"""
    required = "I apologize Goddess. I was foolish to decline. I fully submit to your rules now."
    message_normalized = normalize_text(message_content)
    required_normalized = normalize_text(required)
    return message_normalized == required_normalized

# Button Views
class RulesButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Rules", emoji="<:rules1:1454433030553997454>", style=discord.ButtonStyle.primary, custom_id="onboarding_rules_button")
    async def rules_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if isinstance(interaction.user, discord.Member) and has_bad_pup_role(interaction.user):
            await interaction.response.send_message("You cannot use buttons while you have the Bad Pup role.", ephemeral=True)
            return
        await send_onboarding_rules(interaction, interaction.user, is_reply=True)

class RulesAcceptDeclineView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Decline", emoji="<:thumbsdown2:1454433035952062544>", style=discord.ButtonStyle.danger, custom_id="onboarding_rules_decline_1")
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return
        if has_bad_pup_role(interaction.user):
            await interaction.response.send_message("You cannot use buttons while you have the Bad Pup role.", ephemeral=True)
            return
        await send_rules_decline_1(interaction, interaction.user)
    
    @discord.ui.button(label="Accept", emoji="<:like1:1454433384158728242>", style=discord.ButtonStyle.success, custom_id="onboarding_rules_accept_1")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return
        if has_bad_pup_role(interaction.user):
            await interaction.response.send_message("You cannot use buttons while you have the Bad Pup role.", ephemeral=True)
            return
        await send_rules_accept_1(interaction, interaction.user)

class RulesAcceptDeclineView2(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Decline", emoji="<:thumbsdown2:1454433035952062544>", style=discord.ButtonStyle.danger, custom_id="onboarding_rules_decline_2")
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return
        if has_bad_pup_role(interaction.user):
            await interaction.response.send_message("You cannot use buttons while you have the Bad Pup role.", ephemeral=True)
            return
        await send_rules_decline_2(interaction, interaction.user)
    
    @discord.ui.button(label="Submit to Isla", emoji="<:like1:1454433384158728242>", style=discord.ButtonStyle.success, custom_id="onboarding_rules_accept_2")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return
        if has_bad_pup_role(interaction.user):
            await interaction.response.send_message("You cannot use buttons while you have the Bad Pup role.", ephemeral=True)
            return
        await send_rules_accept_2(interaction, interaction.user)

# Load config on module import
load_onboarding_config()

