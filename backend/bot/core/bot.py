import os
import sys
import asyncio
import discord
import wavelink
import logging
from discord.ext import commands
from itertools import cycle

logger = logging.getLogger(__name__)

class MusicBot(commands.Bot):
    def __init__(self):
        # Companion bot listener
        self.listener_bot = None
        if os.getenv("VOICE_MODULE_ENABLED", "false").lower() == "true":
            from backend.voice_module.listener_bot import ListenerBot
            
            async def voice_callback(guild_id, text_channel_id, user_id, command_text):
                music_cog = self.get_cog("Music")
                if music_cog:
                    await music_cog._handle_voice_command(guild_id, text_channel_id, user_id, command_text)

            self.listener_bot = ListenerBot(voice_callback, main_bot_id=0) # Will be set in on_ready

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
        self._verify_watermarks()
        
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

        # Mute discord.ext.voice_recv excessive RTCP logs unless explicitly requested
        if os.getenv("COMPANION_LOGS", "false").lower() != "true":
            logging.getLogger("discord.ext.voice_recv").setLevel(logging.ERROR)
            
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
        
        # Inject main bot ID into listener bot now that we know it
        if self.listener_bot:
            self.listener_bot.main_bot_id = self.user.id
            
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=next(self._status_cycle),
            )
        )
        if self._presence_task is None or self._presence_task.done():
            self._presence_task = asyncio.create_task(self.setup_presence_rotation())

    async def on_guild_remove(self, guild: discord.Guild):
        # If the main bot is removed/kicked from a guild, ensure the listener bot leaves too
        if self.listener_bot:
            listener_guild = self.listener_bot.get_guild(guild.id)
            if listener_guild:
                logger.info(f"Main bot removed from {guild.name}. Forcing companion to leave.")
                await listener_guild.leave()

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

    def _verify_watermarks(self):
        try:
            # Check backend music.py
            music_path = os.path.join("backend", "bot", "cogs", "music.py")
            if os.path.exists(music_path):
                with open(music_path, "r", encoding="utf-8") as f:
                    music_content = f.read()
                    if "Designed by Kraftamine" not in music_content:
                        logger.critical("CRITICAL: Watermark 'Designed by Kraftamine' missing from backend/bot/cogs/music.py. The bot will not start.")
                        os._exit(1)
            else:
                logger.warning(f"Watermark verification skipped: {music_path} not found.")

            # Check frontend Login.tsx
            login_path = os.path.join("frontend", "src", "pages", "Login.tsx")
            if os.path.exists(login_path):
                with open(login_path, "r", encoding="utf-8") as f:
                    login_content = f.read()
                    if "Flake Music. All rights reserved." not in login_content:
                        logger.critical("CRITICAL: Copyright text missing from frontend/src/pages/Login.tsx. The bot will not start.")
                        os._exit(1)
                    if "Kraftamine" not in login_content or "sumanulto" not in login_content:
                        logger.critical("CRITICAL: Credits missing from frontend/src/pages/Login.tsx. The bot will not start.")
                        os._exit(1)
            else:
                logger.warning(f"Watermark verification skipped: {login_path} not found.")
                
            logger.info("Watermarks verified successfully.")
        except Exception as e:
            logger.critical(f"CRITICAL: Failed to verify watermarks: {e}. The bot will not start.")
            os._exit(1)

bot = MusicBot()
