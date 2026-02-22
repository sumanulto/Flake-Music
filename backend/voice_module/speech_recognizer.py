import os
import json
import logging
import asyncio
from typing import Optional
from vosk import Model, KaldiRecognizer

logger = logging.getLogger(__name__)

class SpeechRecognizer:
    def __init__(self):
        self.companion_logs_enabled = os.getenv("COMPANION_LOGS", "false").lower() == "true"
        
        # Load local Vosk Model
        model_path = os.getenv("VOSK_MODEL_PATH", "./backend/models/vosk-model-small-en-us-0.15")
        
        if not os.path.exists(model_path):
            logger.error(f"[Companion] Vosk model not found at {model_path}. Voice recognition will not work.")
            self.model = None
            return
            
        if self.companion_logs_enabled:
            logger.info(f"[Companion] Loading Free Vosk Model into RAM from {model_path}...")
            
        try:
            self.model = Model(model_path)
            # Discord gives 48000Hz stereo
            self.discord_rate = 48000
            # Vosk small models are trained on 16000Hz mono
            self.vosk_rate = 16000
            if self.companion_logs_enabled:
                logger.info("[Companion] Vosk Model Loaded Successfully.")
        except Exception as e:
            logger.error(f"[Companion] Failed to load Vosk model: {e}")
            self.model = None

    async def recognize(self, audio_data: bytes) -> Optional[str]:
        """
        Processes raw PCM audio bytes locally using Vosk Speech Recognition.
        """
        if not self.model:
            return None
            
        # Audio conversion: Discord gives 48000 Hz, 16-bit, stereo.
        # Vosk expects 16000 Hz, 16-bit, mono.
        import audioop
        
        # 1. Convert Stereo to Mono
        mono_audio = audioop.tomono(audio_data, 2, 0.5, 0.5)
        
        # 2. Resample from 48000 to 16000
        converted_audio, _State = audioop.ratecv(mono_audio, 2, 1, self.discord_rate, self.vosk_rate, None)
        
        def run_kaldi(pcm_bytes):
            # Create a fresh recognizer per chunk to clear context history between pauses
            rec = KaldiRecognizer(self.model, self.vosk_rate)
            # AcceptWaveform returns True if silence found, False if speech.
            # We just want the final result of the chunk.
            rec.AcceptWaveform(pcm_bytes)
            return rec.FinalResult()

        try:
            loop = asyncio.get_event_loop()
            result_json_str = await loop.run_in_executor(None, run_kaldi, converted_audio)
            result_dict = json.loads(result_json_str)
            
            transcript = result_dict.get("text", "").strip()
            
            if transcript:
                if self.companion_logs_enabled:
                    logger.info(f"[Companion-Vosk] Recognized: '{transcript}'")
                return transcript
                
            return None
        except Exception as e:
            logger.error(f"[Companion] Local Vosk Recognition Failed: {e}")
            return None
