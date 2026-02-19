
import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, field_validator
from typing import List

from backend.database.core.db import get_db
from backend.database.models.models import AllowedGuild
from backend.api.services.auth_service import get_current_user
from backend.bot.core.bot import bot

router = APIRouter(prefix="/allowed-guilds", tags=["Allowed Guilds"])

class AllowedGuildCreate(BaseModel):
    guild_id: str # Accept string to avoid JSON number precision issues
    name: str | None = None

class AllowedGuildRead(BaseModel):
    id: int
    guild_id: str # Return as string
    name: str | None
    
    @field_validator('guild_id', mode='before')
    def parse_guild_id(cls, v):
        return str(v)

    class Config:
        from_attributes = True

ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

async def is_admin(user = Depends(get_current_user)):
    # Simple check: current user's ID must match ADMIN_USER_ID
    if user.id != ADMIN_USER_ID:
         raise HTTPException(status_code=403, detail="Not authorized")
    return user

@router.get("/", response_model=List[AllowedGuildRead])
async def get_allowed_guilds(
    db: AsyncSession = Depends(get_db),
    admin = Depends(is_admin)
):
    result = await db.execute(select(AllowedGuild))
    return result.scalars().all()

@router.post("/", response_model=AllowedGuildRead)
async def add_allowed_guild(
    guild_in: AllowedGuildCreate,
    db: AsyncSession = Depends(get_db),
    admin = Depends(is_admin)
):
    try:
        # Pydantic might have already parsed to string, but we need int for DB
        gid = int(guild_in.guild_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Guild ID format")

    # Check if exists
    existing = await db.execute(select(AllowedGuild).where(AllowedGuild.guild_id == gid))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Guild already allowed")
        
    new_guild = AllowedGuild(guild_id=gid, name=guild_in.name)
    db.add(new_guild)
    await db.commit()
    await db.refresh(new_guild)
    
    # Manually map back to Pydantic model which expects string
    # Actually Pydantic 'from_attributes' might fail if model has str and db has int?
    # No, Pydantic coercion works. int -> str.
    return new_guild

@router.delete("/{guild_id}")
async def remove_allowed_guild(
    guild_id: str,
    db: AsyncSession = Depends(get_db),
    admin = Depends(is_admin)
):
    gid = int(guild_id)
    # Delete from DB
    await db.execute(delete(AllowedGuild).where(AllowedGuild.guild_id == gid))
    await db.commit()
    
    # Force bot to leave
    guild = bot.get_guild(gid)
    if guild:
        try:
            await guild.leave()
        except Exception as e:
            # Code execution continues even if leave fails (maybe bot already left)
            print(f"Failed to leave guild {guild_id}: {e}")
            
    return {"success": True}
