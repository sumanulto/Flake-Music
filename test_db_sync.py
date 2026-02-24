import asyncio
import logging
from dotenv import load_dotenv
load_dotenv()

# MUST BE LOADED AFTER DOTENV
from backend.database.core.db import init_db

logging.basicConfig(level=logging.INFO)

async def test_sync():
    print("Testing DB INIT")
    try:
        await init_db()
        print("Success")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_sync())
