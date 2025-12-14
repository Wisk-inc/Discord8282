import discord
from discord import app_commands
from discord.ext import commands, tasks
import requests
import uuid
import time
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Set

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()

bot = commands.Bot(command_prefix="!", intents=intents)

SERVICE_IDS = {
    "views": 229,
    "followers": 228,
    "likes": 232,
    "shares": 235,
    "favorites": 236
}

SERVICE_INFO = {
    "views": {"name": "TikTok Views", "amount": "100 views", "rate": "100 views / 5 min", "color": 0x00FF00, "emoji": "👁️"},
    "followers": {"name": "TikTok Followers", "amount": "10 followers", "rate": "10 followers / 24h", "color": 0xFF6B6B, "emoji": "👤"},
    "likes": {"name": "TikTok Likes", "amount": "10 likes", "rate": "10 likes / 5 min", "color": 0xFF1493, "emoji": "❤️"},
    "shares": {"name": "TikTok Shares", "amount": "20 shares", "rate": "20 shares / 1h", "color": 0x00BFFF, "emoji": "🔄"},
    "favorites": {"name": "TikTok Favorites", "amount": "30 favorites", "rate": "30 favorites / 20 min", "color": 0xFFD700, "emoji": "⭐"}
}

user_cooldowns: Dict[int, Dict[str, datetime]] = {}
auto_tasks: Dict[int, Dict[str, bool]] = {}
auto_messages: Dict[int, Dict[str, discord.Message]] = {}

COOLDOWN_SECONDS = 300

def get_video_id(video_url: str) -> str:
    try:
        response = requests.post(
            "https://zefame-free.com/api_free.php?",
            data={"action": "checkVideoId", "link": video_url},
            timeout=10
        )
        return response.json().get("data", {}).get("videoId", "")
    except:
        return ""

def send_order(service_type: str, video_url: str, video_id: str) -> dict:
    try:
        response = requests.post(
            "https://zefame-free.com/api_free.php?action=order",
            data={
                "service": SERVICE_IDS[service_type],
                "link": video_url,
                "uuid": str(uuid.uuid4()),
                "videoId": video_id
            },
            timeout=10
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def check_cooldown(user_id: int, service_type: str) -> tuple[bool, int]:
    if user_id not in user_cooldowns:
        user_cooldowns[user_id] = {}
    
    if service_type in user_cooldowns[user_id]:
        last_use = user_cooldowns[user_id][service_type]
        elapsed = (datetime.now() - last_use).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            remaining = int(COOLDOWN_SECONDS - elapsed)
            return False, remaining
    return True, 0

def set_cooldown(user_id: int, service_type: str):
    if user_id not in user_cooldowns:
        user_cooldowns[user_id] = {}
    user_cooldowns[user_id][service_type] = datetime.now()

def create_embed(service_type: str, video_url: str, success: bool = True, extra_info: str = "") -> discord.Embed:
    info = SERVICE_INFO[service_type]
    
    if success:
        embed = discord.Embed(
            title=f"{info['emoji']} {info['name']}",
            description=f"**Sending {info['amount']}**\n*This may take a while...*",
            color=info["color"],
            timestamp=datetime.now()
        )
        embed.add_field(name="📎 Video URL", value=f"```{video_url[:50]}...```" if len(video_url) > 50 else f"```{video_url}```", inline=False)
        embed.add_field(name="⏱️ Rate", value=f"`{info['rate']}`", inline=True)
        embed.add_field(name="⏳ Cooldown", value="`5 minutes`", inline=True)
        if extra_info:
            embed.add_field(name="ℹ️ Info", value=extra_info, inline=False)
        embed.set_footer(text="TikTok Botter | Powered by Zefame")
    else:
        embed = discord.Embed(
            title="❌ Error",
            description=extra_info,
            color=0xFF0000,
            timestamp=datetime.now()
        )
        embed.set_footer(text="TikTok Botter")
    
    return embed

def create_cooldown_embed(remaining: int, service_type: str) -> discord.Embed:
    info = SERVICE_INFO[service_type]
    minutes = remaining // 60
    seconds = remaining % 60
    
    embed = discord.Embed(
        title=f"⏰ Cooldown Active",
        description=f"You need to wait before using **{info['name']}** again.",
        color=0xFFA500,
        timestamp=datetime.now()
    )
    embed.add_field(name="⏳ Time Remaining", value=f"`{minutes}m {seconds}s`", inline=True)
    embed.set_footer(text="TikTok Botter")
    return embed

def create_auto_embed(service_type: str, video_url: str, iteration: int = 1) -> discord.Embed:
    info = SERVICE_INFO[service_type]
    
    embed = discord.Embed(
        title=f"🔁 Auto {info['name']}",
        description=f"**Auto-sending {info['amount']}**\n*Running continuously every 5 minutes*",
        color=info["color"],
        timestamp=datetime.now()
    )
    embed.add_field(name="📎 Video URL", value=f"```{video_url[:50]}...```" if len(video_url) > 50 else f"```{video_url}```", inline=False)
    embed.add_field(name="⏱️ Rate", value=f"`{info['rate']}`", inline=True)
    embed.add_field(name="🔄 Iteration", value=f"`#{iteration}`", inline=True)
    embed.add_field(name="📊 Status", value="🟢 **RUNNING**", inline=True)
    embed.set_footer(text="TikTok Botter | Press the button below to stop")
    
    return embed

class StopButton(discord.ui.View):
    def __init__(self, user_id: int, service_type: str):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.service_type = service_type

    @discord.ui.button(label="🛑 Stop Auto", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This button is not for you!", ephemeral=True)
            return
        
        if self.user_id in auto_tasks and self.service_type in auto_tasks[self.user_id]:
            auto_tasks[self.user_id][self.service_type] = False
        
        button.disabled = True
        button.label = "✅ Stopped"
        button.style = discord.ButtonStyle.secondary
        
        embed = discord.Embed(
            title="🛑 Auto Stopped",
            description=f"**Auto {SERVICE_INFO[self.service_type]['name']}** has been stopped.",
            color=0xFF0000,
            timestamp=datetime.now()
        )
        embed.set_footer(text="TikTok Botter")
        
        await interaction.response.edit_message(embed=embed, view=self)

async def run_service(interaction: discord.Interaction, service_type: str, video_url: str):
    can_use, remaining = check_cooldown(interaction.user.id, service_type)
    
    if not can_use:
        embed = create_cooldown_embed(remaining, service_type)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    
    video_id = get_video_id(video_url)
    if not video_id:
        embed = create_embed(service_type, video_url, False, "Could not parse video ID. Please check the URL.")
        await interaction.followup.send(embed=embed)
        return
    
    result = send_order(service_type, video_url, video_id)
    
    if "error" in result:
        embed = create_embed(service_type, video_url, False, f"Error: {result['error']}")
    else:
        set_cooldown(interaction.user.id, service_type)
        status = result.get("message", "Order submitted successfully!")
        embed = create_embed(service_type, video_url, True, f"✅ {status}")
    
    await interaction.followup.send(embed=embed)

async def run_auto_service(interaction: discord.Interaction, service_type: str, video_url: str):
    user_id = interaction.user.id
    
    if user_id not in auto_tasks:
        auto_tasks[user_id] = {}
    
    if service_type in auto_tasks[user_id] and auto_tasks[user_id][service_type]:
        embed = discord.Embed(
            title="⚠️ Already Running",
            description=f"You already have **Auto {SERVICE_INFO[service_type]['name']}** running.\nUse `/stop` to stop all auto tasks first.",
            color=0xFFA500
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    await interaction.response.defer()
    
    video_id = get_video_id(video_url)
    if not video_id:
        embed = create_embed(service_type, video_url, False, "Could not parse video ID. Please check the URL.")
        await interaction.followup.send(embed=embed)
        return
    
    auto_tasks[user_id][service_type] = True
    
    view = StopButton(user_id, service_type)
    embed = create_auto_embed(service_type, video_url, 1)
    message = await interaction.followup.send(embed=embed, view=view)
    
    if user_id not in auto_messages:
        auto_messages[user_id] = {}
    auto_messages[user_id][service_type] = message
    
    send_order(service_type, video_url, video_id)
    
    iteration = 1
    while auto_tasks.get(user_id, {}).get(service_type, False):
        await asyncio.sleep(COOLDOWN_SECONDS)
        
        if not auto_tasks.get(user_id, {}).get(service_type, False):
            break
        
        iteration += 1
        send_order(service_type, video_url, video_id)
        
        try:
            embed = create_auto_embed(service_type, video_url, iteration)
            await message.edit(embed=embed, view=view)
        except:
            pass

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

@bot.tree.command(name="views", description="Send 100 free TikTok views to a video")
@app_commands.describe(video_url="The TikTok video URL or ID")
async def views(interaction: discord.Interaction, video_url: str):
    await run_service(interaction, "views", video_url)

@bot.tree.command(name="followers", description="Send 10 free TikTok followers")
@app_commands.describe(video_url="The TikTok profile URL")
async def followers(interaction: discord.Interaction, video_url: str):
    await run_service(interaction, "followers", video_url)

@bot.tree.command(name="likes", description="Send 10 free TikTok likes to a video")
@app_commands.describe(video_url="The TikTok video URL or ID")
async def likes(interaction: discord.Interaction, video_url: str):
    await run_service(interaction, "likes", video_url)

@bot.tree.command(name="shares", description="Send 20 free TikTok shares to a video")
@app_commands.describe(video_url="The TikTok video URL or ID")
async def shares(interaction: discord.Interaction, video_url: str):
    await run_service(interaction, "shares", video_url)

@bot.tree.command(name="favorites", description="Send 30 free TikTok favorites to a video")
@app_commands.describe(video_url="The TikTok video URL or ID")
async def favorites(interaction: discord.Interaction, video_url: str):
    await run_service(interaction, "favorites", video_url)

@bot.tree.command(name="autoview", description="Automatically send views every 5 minutes")
@app_commands.describe(video_url="The TikTok video URL or ID")
async def autoview(interaction: discord.Interaction, video_url: str):
    await run_auto_service(interaction, "views", video_url)

@bot.tree.command(name="autofollow", description="Automatically send followers every 5 minutes")
@app_commands.describe(video_url="The TikTok profile URL")
async def autofollow(interaction: discord.Interaction, video_url: str):
    await run_auto_service(interaction, "followers", video_url)

@bot.tree.command(name="autolike", description="Automatically send likes every 5 minutes")
@app_commands.describe(video_url="The TikTok video URL or ID")
async def autolike(interaction: discord.Interaction, video_url: str):
    await run_auto_service(interaction, "likes", video_url)

@bot.tree.command(name="autoshare", description="Automatically send shares every 5 minutes")
@app_commands.describe(video_url="The TikTok video URL or ID")
async def autoshare(interaction: discord.Interaction, video_url: str):
    await run_auto_service(interaction, "shares", video_url)

@bot.tree.command(name="autofavorites", description="Automatically send favorites every 5 minutes")
@app_commands.describe(video_url="The TikTok video URL or ID")
async def autofavorites(interaction: discord.Interaction, video_url: str):
    await run_auto_service(interaction, "favorites", video_url)

@bot.tree.command(name="stop", description="Stop all your running auto commands")
async def stop(interaction: discord.Interaction):
    user_id = interaction.user.id
    
    if user_id not in auto_tasks or not any(auto_tasks[user_id].values()):
        embed = discord.Embed(
            title="ℹ️ No Active Tasks",
            description="You don't have any auto tasks running.",
            color=0x3498DB,
            timestamp=datetime.now()
        )
        embed.set_footer(text="TikTok Botter")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    stopped = []
    for service_type in list(auto_tasks[user_id].keys()):
        if auto_tasks[user_id][service_type]:
            auto_tasks[user_id][service_type] = False
            stopped.append(SERVICE_INFO[service_type]["name"])
    
    if user_id in user_cooldowns:
        user_cooldowns[user_id].clear()
    
    embed = discord.Embed(
        title="🛑 All Tasks Stopped",
        description=f"Stopped the following auto tasks:\n" + "\n".join([f"• **{s}**" for s in stopped]),
        color=0xFF0000,
        timestamp=datetime.now()
    )
    embed.add_field(name="🔄 Cooldowns", value="All cooldowns have been reset!", inline=False)
    embed.set_footer(text="TikTok Botter")
    
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_BOT_TOKEN not found in environment variables!")
    else:
        bot.run(TOKEN)
