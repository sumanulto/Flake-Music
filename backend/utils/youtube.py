import asyncio
import logging
import os
import yt_dlp

logger = logging.getLogger(__name__)

async def extract_info(url: str) -> dict:
    """
    Extracts information from a YouTube URL using yt-dlp.
    Returns a dictionary with 'title' and other metadata, or None if failed.
    Runs in a separate thread to avoid blocking the event loop.
    """
    def _extract():
        cookie_file = os.getenv("YTDLP_COOKIE_FILE")
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': 'in_playlist', # fast extraction for playlists
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android']
                }
            },
        }

        if cookie_file:
            ydl_opts['cookiefile'] = cookie_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                return info
            except Exception as e:
                logger.error(f"yt-dlp extraction failed: {e}")
                return None

    return await asyncio.to_thread(_extract)
