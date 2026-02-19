import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, field_validator
from typing import List

from backend.database.core.db import get_db
from backend.database.models.models import AllowedUser
from backend.api.services.auth_service import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

class AllowedUserCreate(BaseModel):
    discord_id: str
    username: str | None = None

class AllowedUserRead(BaseModel):
    id: int
    discord_id: str # Return as string preventing precision loss
    username: str | None
    
    @field_validator('discord_id', mode='before')
    def parse_discord_id(cls, v):
        return str(v)

    class Config:
        from_attributes = True

ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

async def is_admin(user = Depends(get_current_user)):
    # Simple check: current user's ID must match ADMIN_USER_ID
    if user.id != ADMIN_USER_ID:
         raise HTTPException(status_code=403, detail="Not authorized")
    return user

@router.get("/", response_model=List[AllowedUserRead])
async def get_allowed_users(
    db: AsyncSession = Depends(get_db),
    admin = Depends(is_admin)
):
    result = await db.execute(select(AllowedUser))
    return result.scalars().all()

@router.post("/", response_model=AllowedUserRead)
async def add_allowed_user(
    user_in: AllowedUserCreate,
    db: AsyncSession = Depends(get_db),
    admin = Depends(is_admin)
):
    # Check if exists
    # user_in.discord_id is str, DB expects int
    did = int(user_in.discord_id)
    existing = await db.execute(select(AllowedUser).where(AllowedUser.discord_id == did))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already allowed")
        
    new_user = AllowedUser(discord_id=did, username=user_in.username)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.delete("/{discord_id}")
async def remove_allowed_user(
    discord_id: str,
    db: AsyncSession = Depends(get_db),
    admin = Depends(is_admin)
):
    did = int(discord_id)
    await db.execute(delete(AllowedUser).where(AllowedUser.discord_id == did))
    await db.commit()
    return {"success": True}
