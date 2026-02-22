import discord
import logging
import asyncio
from discord.ext import commands
from discord.ext import voice_recv
from .audio_sink import FlakeAudioSink

logger = logging.getLogger(__name__)

class ListenerBot(commands.Bot):
    def __init__(self, main_bot_callback, main_bot_id: int):
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.guilds = True
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix="fl!", # Irrelevant, just needed for commands.Bot
            intents=intents,
            help_command=None
        )
        self.main_bot_callback = main_bot_callback
        self.main_bot_id = main_bot_id
        # Keep track of active connections
        self.active_sinks = {}

    async def setup_hook(self):
        logger.info("Voice Listener Bot is starting up...")
        
        # Load Opus for Linux environments if not already loaded
        if not discord.opus.is_loaded():
            try:
                # Try standard linux lib paths
                import ctypes.util
                opus_path = ctypes.util.find_library("opus")
                if opus_path:
                    discord.opus.load_opus(opus_path)
                else:
                    # Fallbacks for common distros
                    try:
                        discord.opus.load_opus("libopus.so.0")
                    except Exception:
                        discord.opus.load_opus("libopus.so")
                logger.info("Loaded Opus natively for Voice Receiving.")
            except Exception as e:
                logger.warning(f"Could not load Opus natively: {e}. You may need to 'apt install libopus0'.")
                
        # Monkey patch discord.opus to prevent crashes on corrupted streams
        if hasattr(discord.opus, 'Decoder'):
            original_decode = discord.opus.Decoder.decode
            def patched_decode(self, data, *, fec=False):
                try:
                    return original_decode(self, data, fec=fec)
                except discord.opus.OpusError as e:
                    logger.debug(f"Ignored OpusError during decode (Corrupted Stream): {e}")
                    # Return 20ms of silence (48000Hz stereo = 960 frames * 2 channels * 2 bytes = 3840 bytes)
                    return b'\x00' * 3840
            
            discord.opus.Decoder.decode = patched_decode
            logger.info("Monkey-patched discord.opus.Decoder to safely ignore corrupted streams.")

    async def on_ready(self):
        logger.info(f"Voice Listener Bot logged in as {self.user} (ID: {self.user.id})")
        # Go invisible/offline to avoid confusing users
        await self.change_presence(status=discord.Status.offline)
        
    async def on_guild_join(self, guild: discord.Guild):
        # Companion bot joined a guild.
        # Ensure the main bot is already in this guild.
        if not guild.get_member(self.main_bot_id):
            logger.info(f"Companion joined {guild.name} but Main Bot ({self.main_bot_id}) is absent. Leaving.")
            
            # Try to find a channel to send the rejection message
            target_channel = next(
                (ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), 
                None
            )
            
            if target_channel:
                try:
                    await target_channel.send("Sorry brother but i cannot live with out my companion invite my companion first")
                except Exception as e:
                    logger.error(f"Failed to send rejection to {guild.name}: {e}")
                    
            await guild.leave()

    async def join_channel(self, text_channel_id: int, voice_channel_id: int):
        """Called by the main bot when /ai enable is used"""
        channel = self.get_channel(voice_channel_id)
        if not channel:
            logger.error(f"Listener bot could not find voice channel {voice_channel_id}")
            return False

        try:
            # Check if already connected to this guild
            if channel.guild.voice_client:
                await channel.guild.voice_client.disconnect(force=True)

            # Connect with voice_recv capability
            vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
            
            # Start listening
            # We pass a callback that includes the text_channel_id so the main bot knows where to reply
            async def handle_transcript(user_id, transcript):
                await self.process_transcript(channel.guild.id, text_channel_id, user_id, transcript)
                
            sink = FlakeAudioSink.start_listening(vc, handle_transcript)
            self.active_sinks[channel.guild.id] = sink
            logger.info(f"Listener bot joined {channel.name} and started FlakeAudioSink.")
            
            # Update presence to show we are listening
            if len(self.active_sinks) > 0:
                await self.change_presence(
                    status=discord.Status.online,
                    activity=discord.Activity(type=discord.ActivityType.listening, name="commands (Hey Flake)")
                )
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to join voice channel: {e}")
            return False

    async def leave_channel(self, guild_id: int):
        """Called by the main bot when /ai disable is used"""
        guild = self.get_guild(guild_id)
        if guild and guild.voice_client:
            sink = self.active_sinks.pop(guild_id, None)
            if sink:
                sink.cleanup()
            await guild.voice_client.disconnect(force=True)
            logger.info(f"Listener bot left guild {guild_id}")
            
            # Go back to offline if we are no longer listening anywhere
            if len(self.active_sinks) == 0:
                await self.change_presence(status=discord.Status.offline)
                
            return True
        return False

    async def process_transcript(self, guild_id: int, text_channel_id: int, user_id: int, transcript: str):
        """
        Parses the transcript for 'hey flake' or variations and triggers the main bot callback.
        """
        text = transcript.lower().strip()
        
        # Possible hotwords (English and potential phonetic Bangla interpretations)
        # Vosk 'small' models often mishear "flake" as "flick", "flea", "placebo", etc.
        hotwords = [
            "hey flake", "hi flake", "hello flake", "hey flex", 
            "hey flick", "এ ফ্লেক", "হে ফ্লেক", "a flick", 
            "any flick", "hey flic", "a plane", "hey fly",
            "hey flack", "play flick", "hey plague"
        ]
        
        # If any variations match the start, or close to it
        matched_hotword = None
        for hw in hotwords:
            if text.startswith(hw):
                matched_hotword = hw
                break
                
        # Fallback: if it's really struggling, just assume if it has "play" or "stop"
        # Since it's a music bot, let's treat generic "play X" as a command if enabled
        fallback_action = None
        if not matched_hotword:
            if "play" in text or "placebo" in text or "bleach" in text:
                fallback_action = "play"
            elif "stop" in text or "pause" in text:
                fallback_action = "stop"
            elif "skip" in text or "next" in text:
                fallback_action = "skip"

        if matched_hotword or fallback_action:
            if matched_hotword:
                command_text = text[len(matched_hotword):].strip()
            else:
                # If doing a fallback catch, parse everything after the action word
                if fallback_action == "play":
                     # Replace common mishearings for "play"
                     text = text.replace("placebo", "play").replace("bleach", "play")
                     try:
                         command_text = text[text.index("play"):]
                     except ValueError:
                         command_text = text
                else:
                     command_text = fallback_action
                     
            
            # Clean up command text (e.g. "hey flake play..." -> "play...")
            # Sometimes Speech API adds punctuation
            command_text = command_text.lstrip(",.!?;: ")
            
            if command_text:
                logger.info(f"Hotword detected! Command: '{command_text}' from user {user_id}")
                # Pass back to main bot
                # main_bot_callback signature: async def cb(guild_id, text_channel_id, user_id, command_string)
                if self.main_bot_callback:
                    asyncio.create_task(self.main_bot_callback(guild_id, text_channel_id, user_id, command_text))
            else:
                logger.info(f"Hotword detected, but no command followed.")
