import aiohttp
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from backend.api.middleware.auth_middleware import get_current_user
from backend.database.models.models import User
from backend.bot.core.bot import bot

router = APIRouter(prefix="/guilds", tags=["Guilds"])

@router.get("/")
async def get_guilds(current_user: User = Depends(get_current_user)):
    async with aiohttp.ClientSession() as session:
        headers = {'Authorization': f'Bearer {current_user.access_token}'}
        async with session.get('https://discord.com/api/users/@me/guilds', headers=headers) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=resp.status, detail="Failed to fetch guilds from Discord")
            user_guilds = await resp.json()

    # Filter guilds where user has Manage Server (0x20) or Administrator (0x8)
    # And add "bot_in_guild" flag
    manageable_guilds = []
    for g in user_guilds:
        permissions = int(g['permissions'])
        if (permissions & 0x20) == 0x20 or (permissions & 0x8) == 0x8:
             # Check if bot is in guild
             guild_obj = bot.get_guild(int(g['id']))
             g['bot_in_guild'] = guild_obj is not None
             manageable_guilds.append(g)
             
    return manageable_guilds
