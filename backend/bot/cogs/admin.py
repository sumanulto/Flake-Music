import discord
from discord.ext import commands
import logging
import os
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

async def setup(bot):
    await bot.add_cog(AdminCog(bot))
