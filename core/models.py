"""
Core data models for Profile & Engagement API

Defines UserProfile for database storage and Comment for API responses.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from pydantic import BaseModel


class UserProfile(SQLModel, table=True):
    """
    User profile model stored in SQLite database for avatar caching.
    """

    username: str = Field(primary_key=True, max_length=255)
    nickname: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=1024)
    avatar_data_url: Optional[str] = Field(
        default=None, max_length=65536
    )  # Base64 data can be large
    source: Optional[str] = Field(
        default=None, max_length=50
    )  # live, scraper, generator, initials
    priority: Optional[int] = Field(default=100)  # Lower = higher priority
    image_hash: Optional[str] = Field(
        default=None, max_length=128
    )  # For detecting changes
    last_checked_at: Optional[datetime] = Field(default=None)
    expires_at: Optional[datetime] = Field(default=None)


class Comment(BaseModel):
    """
    Comment model for streaming TikTok comments.
    Not stored in database - used for API responses only.
    """

    username: str
    text: str
    timestamp_ms: int
    source: str = "tiktok"  # For future extensibility
