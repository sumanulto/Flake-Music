import os
import asyncio
import discord
import wavelink
import logging
from discord.ext import commands
from itertools import cycle

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
        self.status_messages = self._load_status_messages()
        self._status_cycle = cycle(self.status_messages)
        self.status_rotation_seconds = self._load_status_rotation_seconds()
        self._presence_task = None

    def _load_status_messages(self):
        default_messages = [
            "Listening to your commands!",
            "Ready to play music!",
            "Type /play to start music!",
            "Invite me to your server!",
        ]
        messages = []
        for i in range(1, 5):
            value = os.getenv(f"BOT_STATUS_MESSAGE_{i}", "").strip()
            if value:
                messages.append(value)
        return messages or default_messages

    def _load_status_rotation_seconds(self):
        raw_value = os.getenv("BOT_STATUS_ROTATION_SECONDS", "1").strip()
        try:
            seconds = float(raw_value)
            return max(0.1, seconds)
        except ValueError:
            logger.warning("Invalid BOT_STATUS_ROTATION_SECONDS='%s'. Falling back to 1 second.", raw_value)
            return 1.0

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
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=next(self._status_cycle),
            )
        )
        if self._presence_task is None or self._presence_task.done():
            self._presence_task = asyncio.create_task(self.setup_presence_rotation())

    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        logger.info(f"Wavelink Node connected: {payload.node.identifier}")

    async def on_presence_update_tick(self):
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=next(self._status_cycle),
            )
        )

    async def setup_presence_rotation(self):
        while not self.is_closed():
            try:
                await self.on_presence_update_tick()
            except Exception as e:
                logger.error(f"Failed to update bot presence: {e}")
            await asyncio.sleep(self.status_rotation_seconds)

bot = MusicBot()
