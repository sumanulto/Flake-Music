import asyncio
import logging
import os
import yt_dlp
import httpx

logger = logging.getLogger(__name__)

async def extract_info(url: str) -> dict:
    """
    Extracts information from a YouTube URL using yt-dlp.
    Returns a dictionary with 'title' and other metadata, or None if failed.
    If yt-dlp fails (e.g., datacenter IP block), it falls back to the public YouTube oEmbed API.
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
                logger.error(f"yt-dlp extraction failed for {url}: {e}")
                return None

    # Try yt-dlp first
    result = await asyncio.to_thread(_extract)
    
    # If yt-dlp succeeds, return it
    if result is not None:
        return result
        
    # DEADLY FALLBACK: If yt-dlp is blocked by YouTube's aggressive "Sign in to confirm you're not a bot",
    # we can use YouTube's public oEmbed API for single videos. The oEmbed API is meant for embedding 
    # and is almost never IP-blocked by datacenters.
    logger.info(f"Attempting oEmbed fallback for: {url}")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"https://www.youtube.com/oembed?url={url}&format=json")
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"oEmbed successfully recovered metadata for: {url}")
                return {
                    "title": data.get("title"),
                    "artist": data.get("author_name"),
                    "uploader": data.get("author_name")
                }
            else:
                logger.warning(f"oEmbed fallback failed with status {resp.status_code}")
    except Exception as fallback_err:
        logger.error(f"oEmbed fallback crashed: {fallback_err}")
        
    return None
