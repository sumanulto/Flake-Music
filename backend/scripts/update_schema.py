import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from dotenv import load_dotenv

# Load env before importing db
load_dotenv()

from sqlalchemy import text
from backend.database.core.db import engine

async def update_schema():
    async with engine.begin() as conn:
        print("Adding is_liked_songs to playlists...")
        await conn.execute(text("ALTER TABLE playlists ADD COLUMN IF NOT EXISTS is_liked_songs BOOLEAN DEFAULT FALSE;"))
        
        print("Adding added_at to playlist_tracks...")
        await conn.execute(text("ALTER TABLE playlist_tracks ADD COLUMN IF NOT EXISTS added_at VARCHAR;"))
        
        print("Schema update complete.")

if __name__ == "__main__":
    asyncio.run(update_schema())
