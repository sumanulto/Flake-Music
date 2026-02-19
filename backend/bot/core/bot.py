import os
import discord
import wavelink
import logging
from discord.ext import commands

logger = logging.getLogger(__name__)

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # Load Cogs
        for filename in os.listdir("./backend/bot/cogs"):
            if filename.endswith(".py") and filename != "__init__.py":
                try:
                    await self.load_extension(f"backend.bot.cogs.{filename[:-3]}")
                    logger.info(f"Loaded extension: {filename}")
                except Exception as e:
                    logger.error(f"Failed to load extension {filename}: {e}")

        # Sync Slash Commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

        # Connect to Wavelink
        lavalink_host = os.getenv("LAVALINK_HOST", "lavalink")
        lavalink_port = os.getenv("LAVALINK_PORT", "2333")
        lavalink_password = os.getenv("LAVALINK_PASSWORD", "youshallnotpass")
        lavalink_uri = f"http://{lavalink_host}:{lavalink_port}"
        
        nodes = [wavelink.Node(uri=lavalink_uri, password=lavalink_password)]
        await wavelink.Pool.connect(nodes=nodes, client=self, cache_capacity=100)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        logger.info(f"Wavelink Node connected: {payload.node.identifier}")

bot = MusicBot()
