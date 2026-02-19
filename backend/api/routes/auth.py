from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.core.db import get_db
from backend.api.services.auth_service import exchange_code, get_discord_user, get_or_create_user, create_access_token, get_current_user
from backend.api.schemas.auth import Token, GuildPreview
import logging
import aiohttp
from typing import List

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger(__name__)

import os
from sqlalchemy import select
from backend.database.models.models import AllowedUser, User

# ... (imports)

@router.post("/callback", response_model=Token)
async def auth_callback(code: str, db: AsyncSession = Depends(get_db)):
    try:
        # Exchange code for Discord token
        tokens = await exchange_code(code)
        
        # Get User Info from Discord
        discord_user = await get_discord_user(tokens['access_token'])
        
        
        # --- ACCESS CONTROL CHECK ---
        user_id = int(discord_user['id'])
        admin_id = int(os.getenv("ADMIN_USER_ID", "0"))
        
        is_allowed = False
        if user_id == admin_id:
            is_allowed = True
        else:
            # Check DB
            result = await db.execute(select(AllowedUser).where(AllowedUser.discord_id == user_id))
            if result.scalar_one_or_none():
                is_allowed = True
                
        if not is_allowed:
            # Send DM to user
            try:
                from backend.bot.core.bot import bot
                user = await bot.fetch_user(user_id)
                if user:
                    await user.send("You are not allowed to access the dashboard. Please contact an administrator for permission.")
            except Exception as e:
                logger.error(f"Failed to send DM to unauthorized user {user_id}: {e}")

            raise HTTPException(status_code=403, detail="Access Forbidden: You are not on the allowlist.")
        # -----------------------------
        
        # Create or Update User in DB
        user = await get_or_create_user(db, discord_user, tokens)
        
        # Generate JWT
        access_token = create_access_token(data={"sub": str(user.id)})
        
        return {"access_token": access_token, "token_type": "bearer"}

    except Exception as e:
        logger.error(f"Error in auth callback: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/guilds", response_model=List[GuildPreview])
async def get_user_guilds(current_user = Depends(get_current_user)):
    url = "https://discord.com/api/users/@me/guilds"
    # User model has access_token
    if not current_user.access_token:
         raise HTTPException(status_code=401, detail="No access token found for user")
         
    headers = {"Authorization": f"Bearer {current_user.access_token}"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status == 401:
                raise HTTPException(status_code=401, detail="Discord token expired or invalid")
            resp.raise_for_status()
            guilds = await resp.json()
            
    # Filter for MANAGE_GUILD (0x20) or ADMIN (0x8)
    # Permissions are string in JSON
    manage_guild_perm = 0x20
    admin_perm = 0x8
    
    allowed_guilds = []
    
    for g in guilds:
        perms = int(g.get("permissions", "0"))
        if (perms & manage_guild_perm) == manage_guild_perm or (perms & admin_perm) == admin_perm:
             allowed_guilds.append(GuildPreview(
                 id=g['id'],
                 name=g['name'],
                 icon=g['icon'],
                 permissions=perms
             ))
             
    return allowed_guilds

@router.get("/me", response_model=None)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": str(current_user.id), # Return as string to avoid JS precision loss
        "username": current_user.username,
        "avatar_url": current_user.avatar_url
    }
