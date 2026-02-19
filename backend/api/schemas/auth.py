from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: str | None = None

class UserResponse(BaseModel):
    id: int
    username: str
    avatar_url: str | None

class GuildPreview(BaseModel):
    id: str
    name: str
    icon: str | None
    permissions: int
