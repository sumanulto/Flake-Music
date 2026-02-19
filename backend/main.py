import asyncio
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import Bot and Database
from backend.bot.core.bot import bot
from backend.database.core.db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up FastAPI and Discord Bot...")
    await init_db()
    asyncio.create_task(bot.start(os.getenv("DISCORD_TOKEN")))
    yield
    # Shutdown
    logger.info("Shutting down...")
    await bot.close()

app = FastAPI(
    title="Discord Music Bot Impl",
    description="Backend API for Discord Music Bot Control Panel",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Discord Music Bot API is running"}

from backend.api.routes import auth_router, guilds_router, music_router, websocket_router, users, bot as bot_routes, playlist, allowed_guilds
# Import models to ensure they are registered with Base.metadata
from backend.database.models.models import AllowedUser, AllowedGuild

app.include_router(auth_router, prefix="/api/v1")
app.include_router(guilds_router, prefix="/api/v1")
app.include_router(music_router, prefix="/api/v1")
app.include_router(playlist.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(allowed_guilds.router, prefix="/api/v1")
app.include_router(bot_routes.router, prefix="/api/v1") # Bot router is usually separate from v1 if it's internal/control


app.include_router(websocket_router) # WS usually doesn't have api prefix, or does it? User req: /ws is endpoint? No spec, but usually separate. Route is /ws/{guild_id} so we add it directly.

