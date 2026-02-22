import discord
import logging
import asyncio
import time
from discord.ext import voice_recv
from .speech_recognizer import SpeechRecognizer

logger = logging.getLogger(__name__)

class FlakeAudioSink(voice_recv.AudioSink):
    def __init__(self, callback):
        super().__init__()
        import os
        self.companion_logs_enabled = os.getenv("COMPANION_LOGS", "false").lower() == "true"
        self.callback = callback
        self.recognizer = SpeechRecognizer()
        
        # Buffer for PCM data per user (user_id: bytearray)
        self.user_buffers = {}
        # Track last time a user sent a packet (user_id: float timestamp)
        self.user_last_packet = {}
        
        # Increase threshold to 2.0s to allow normal pauses between words
        self.silence_threshold = 2.0 
        self._flush_task = None
        self._running = False

    def wants_opus(self) -> bool:
        return False # We want decoded PCM

    def write(self, user: discord.User | discord.Member, data: voice_recv.VoiceData):
        if not user or getattr(user, "bot", False):
            # Explicitly ignore all Discord bots (including our own music bot)
            # to prevent it from hearing the music playing and hallucinating commands
            return

        user_id = user.id
        
        # Append PCM bytes to buffer
        if user_id not in self.user_buffers:
            self.user_buffers[user_id] = bytearray()
            
        self.user_buffers[user_id].extend(data.pcm)
        self.user_last_packet[user_id] = time.time()

    def cleanup(self):
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
        self.user_buffers.clear()
        self.user_last_packet.clear()

    async def _flush_loop(self):
        self._running = True
        while self._running:
            await asyncio.sleep(0.5)
            now = time.time()
            
            users_to_process = []
            for user_id, last_time in list(self.user_last_packet.items()):
                if now - last_time > self.silence_threshold:
                    if user_id in self.user_buffers and len(self.user_buffers[user_id]) > 0:
                        users_to_process.append(user_id)
            
            for user_id in users_to_process:
                # Extract and clear buffer
                pcm_data = bytes(self.user_buffers[user_id])
                self.user_buffers[user_id].clear()
                del self.user_last_packet[user_id]
                
                # Check minimum length
                # 48000Hz * 2 channels * 2 bytes = 192000 bytes/sec
                # Require at least 1.5 seconds of sustained audio to count as a command
                # This prevents a random mic bump or sigh from triggering the fake mock
                if len(pcm_data) > 192000 * 1.5:
                    asyncio.create_task(self._process_audio(user_id, pcm_data))
                else:
                    if self.companion_logs_enabled:
                        logger.info(f"Audio chunk for user {user_id} was too short ({len(pcm_data)} bytes). Ignoring.")

    async def _process_audio(self, user_id, pcm_bytes):
        if self.companion_logs_enabled:
            logger.info(f"[Companion] Processing audio chunk for user {user_id}...")
        
        transcript = await self.recognizer.recognize(pcm_bytes)
        
        if transcript:
            await self.callback(user_id, transcript)

    @classmethod
    def start_listening(cls, voice_client: voice_recv.VoiceRecvClient, callback):
        sink = cls(callback)
        sink._flush_task = asyncio.create_task(sink._flush_loop())
        voice_client.listen(sink)
        return sink
