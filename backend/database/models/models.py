from sqlalchemy import ForeignKey, BigInteger, String, Boolean, JSON, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.core.db import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True) # Discord ID
    username: Mapped[str] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str] = mapped_column(String, nullable=True)
    access_token: Mapped[str] = mapped_column(String, nullable=True) # Encrypted ideally
    refresh_token: Mapped[str] = mapped_column(String, nullable=True)

    playlists: Mapped[list["Playlist"]] = relationship(back_populates="user")

class Guild(Base):
    __tablename__ = "guilds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True) # Discord Guild ID
    name: Mapped[str] = mapped_column(String, nullable=True)
    icon_url: Mapped[str] = mapped_column(String, nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, default={})
    premium: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships could be added here

class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=True) # Optional: Playlist specific to a guild?

    user: Mapped["User"] = relationship(back_populates="playlists")
    tracks: Mapped[list["PlaylistTrack"]] = relationship(back_populates="playlist", cascade="all, delete-orphan")
    
    is_liked_songs: Mapped[bool] = mapped_column(Boolean, default=False)

class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id"))
    track_data: Mapped[dict] = mapped_column(JSON) # Stores the encoded track or metadata
    added_at: Mapped[str] = mapped_column(String, nullable=True) # ISO Timestamp
    
    playlist: Mapped["Playlist"] = relationship(back_populates="tracks")


class AllowedUser(Base):
    __tablename__ = "allowed_users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    discord_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    username: Mapped[str] = mapped_column(String, nullable=True) # Optional, just for display
    added_at: Mapped[str] = mapped_column(String, nullable=True) # Simple timestamp string or DateTime

class AllowedGuild(Base):
    __tablename__ = "allowed_guilds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=True) # Optional, just for display
    added_at: Mapped[str] = mapped_column(String, nullable=True)
