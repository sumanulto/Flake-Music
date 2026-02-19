import os
import aiohttp
from jose import jwt, JWTError
from datetime import datetime, timedelta
from backend.database.core.db import get_db
from backend.database.models.models import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:5173/auth/callback")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def exchange_code(code: str):
    async with aiohttp.ClientSession() as session:
        data = {
            'client_id': DISCORD_CLIENT_ID,
            'client_secret': DISCORD_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': DISCORD_REDIRECT_URI,
            'scope': 'identify guilds'
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        async with session.post('https://discord.com/api/oauth2/token', data=data, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

async def get_discord_user(access_token: str):
    async with aiohttp.ClientSession() as session:
        headers = {'Authorization': f'Bearer {access_token}'}
        async with session.get('https://discord.com/api/users/@me', headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()

async def get_or_create_user(session: AsyncSession, discord_data: dict, tokens: dict):
    user_id = int(discord_data['id'])
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            id=user_id,
            username=discord_data['username'],
            avatar_url=f"https://cdn.discordapp.com/avatars/{user_id}/{discord_data['avatar']}.png" if discord_data['avatar'] else None,
            access_token=tokens['access_token'],
            refresh_token=tokens['refresh_token']
        )
        session.add(user)
    else:
        user.username = discord_data['username']
        user.avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{discord_data['avatar']}.png" if discord_data['avatar'] else None
        user.access_token = tokens['access_token']
        user.refresh_token = tokens['refresh_token']
    
    
    await session.commit()
    await session.refresh(user)
    return user

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # jwt is already imported from jose at the top of the file
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError: # JWTError is already imported from jose at the top
        raise credentials_exception
        
    stmt = select(User).where(User.id == int(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
        
    return user
