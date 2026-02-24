import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
import psutil
import wavelink
from sqlalchemy import select
from backend.database.core.db import get_db_session
from backend.database.models.models import AllowedGuild

logger = logging.getLogger(__name__)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_guild_allowed(self, guild_id: int) -> bool:
        # Check if it's the Mother Guild
        mother_guild_id = os.getenv("MOTHER_GUILD_ID")
        logger.info(f"Checking guild {guild_id}. Mother Guild ID: {mother_guild_id}")
        
        if mother_guild_id and str(guild_id) == str(mother_guild_id):
            logger.info(f"Guild {guild_id} matched Mother Guild ID.")
            return True

        async with get_db_session() as session:
            result = await session.execute(select(AllowedGuild).where(AllowedGuild.guild_id == guild_id))
            allowed = result.scalar_one_or_none() is not None
            logger.info(f"Guild {guild_id} allowed in DB? {allowed}")
            return allowed

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        logger.info(f"Joined guild: {guild.name} ({guild.id})")
        if not await self.is_guild_allowed(guild.id):
            logger.warning(f"Guild {guild.name} ({guild.id}) is not in the allowed list. Leaving...")
            try:
                # Optional: Send a DM to the guild owner explaining why
                if guild.owner:
                    await guild.owner.send("I am a private bot and this server is not authorized to use me. Please contact the administrator.")
            except Exception as e:
                logger.error(f"Failed to send DM to guild owner: {e}")
            
            await guild.leave()
        else:
            logger.info(f"Guild {guild.name} ({guild.id}) is authorized.")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("AdminCog: Checking unauthorized guilds...")
        for guild in self.bot.guilds:
            logger.info(f"Checking guild on startup: {guild.name} ({guild.id})")
            if not await self.is_guild_allowed(guild.id):
                logger.warning(f"Found unauthorized guild on startup: {guild.name} ({guild.id}). Leaving...")
                await guild.leave()

    @app_commands.command(name="status", description="Show bot and system status info")
    async def status(self, interaction: discord.Interaction):
        """Ephemeral debug panel: system resources + bot + Lavalink nodes."""
        await interaction.response.defer(ephemeral=True)

        # ── System ────────────────────────────────────────────────────────────
        cpu_pct = psutil.cpu_percent(interval=0.3)
        vm      = psutil.virtual_memory()
        du      = psutil.disk_usage("/")

        ram_used  = round(vm.used  / 1024**3, 1)
        ram_total = round(vm.total / 1024**3, 1)
        disk_used  = round(du.used  / 1024**3, 1)
        disk_total = round(du.total / 1024**3, 1)

        system_lines = (
            f"```\n"
            f"== System Info ==\n"
            f"CPU:  {cpu_pct}%\n"
            f"RAM:  {ram_used}/{ram_total}GB ({vm.percent}%)\n"
            f"DISK: {disk_used}/{disk_total}GB ({du.percent:.1f}%)\n"
            f"```"
        )

        # ── Bot ───────────────────────────────────────────────────────────────
        total_players = len(self.bot.voice_clients)
        raw_lat       = self.bot.latency
        latency_ms    = round(raw_lat * 1000, 2) if raw_lat == raw_lat else "N/A"
        bot_version   = os.getenv("BOT_VERSION") or f"v{discord.__version__}"

        bot_lines = (
            f"```\n"
            f"Bot Information\n"
            f"• VERSION:  {bot_version}\n"
            f"• LATENCY:  {latency_ms}ms\n"
            f"• GUILDS:   {len(self.bot.guilds)}\n"
            f"• USERS:    {len(self.bot.users)}\n"
            f"• PLAYERS:  {total_players}\n"
            f"```"
        )

        # ── Nodes ─────────────────────────────────────────────────────────────
        node_blocks = []
        if hasattr(wavelink.Pool, "nodes"):
            for node in wavelink.Pool.nodes.values():
                connected  = node.status == wavelink.NodeStatus.CONNECTED
                dot        = "\U0001f7e2" if connected else "\U0001f534"
                conn_label = "Connected" if connected else "Disconnected"
                ns         = getattr(node, "stats", None)

                address = os.getenv("VITE_API_URL", "N/A")

                if ns and connected:
                    ram_used_mb   = round(ns.memory.used / 1024 / 1024, 1)
                    ram_total_mb  = round(ns.memory.reservable / 1024 / 1024, 1)
                    ram_pct       = round(ram_used_mb / ram_total_mb * 100, 1) if ram_total_mb else 0
                    cpu_ll        = round(ns.cpu.lavalink_load * 100, 1)
                    uptime_sec    = int(ns.uptime / 1000)
                    h, rem = divmod(uptime_sec, 3600)
                    m, s   = divmod(rem, 60)
                    hb     = getattr(node, "heartbeat", float("nan"))
                    lat_ms = round(hb * 1000, 2) if hb == hb else "N/A"

                    node_blocks.append(
                        f"{dot} **{node.identifier} Node** — {conn_label}\n"
                        f"```\n"
                        f"• ADDRESS: {address}\n"
                        f"• PLAYERS: {len(node.players)}\n"
                        f"• CPU:     {cpu_ll}%\n"
                        f"• RAM:     {ram_used_mb}/{ram_total_mb}MB ({ram_pct}%)\n"
                        f"• LATENCY: {lat_ms}ms\n"
                        f"• UPTIME:  {h:02d}:{m:02d}:{s:02d}\n"
                        f"```"
                    )
                else:
                    node_blocks.append(
                        f"{dot} **{node.identifier} Node** — {conn_label}\n"
                        f"```\n"
                        f"• ADDRESS: {address}\n"
                        f"```"
                    )

        embed = discord.Embed(
            title="\U0001f4ca Bot Status",
            color=discord.Color.green() if not self.bot.is_closed() else discord.Color.red(),
        )
        embed.add_field(name="System", value=system_lines, inline=False)
        embed.add_field(name="Bot", value=bot_lines, inline=False)
        for block in node_blocks:
            embed.add_field(name="\u200b", value=block, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
