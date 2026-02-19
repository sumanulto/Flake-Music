from pydantic import BaseModel

class PlayRequest(BaseModel):
    query: str
    guild_id: int

class MusicStatus(BaseModel):
    guild_id: int
    is_playing: bool
    title: str | None
    author: str | None
    position: int
    duration: int
    volume: int
    queue: list[str]

class VolumeRequest(BaseModel):
    volume: int

class SeekRequest(BaseModel):
    position: int
