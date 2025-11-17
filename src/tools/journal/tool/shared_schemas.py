
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class EntryCreate(BaseModel):
    title: str
    content: str
    entry_date: str
    journal_id: str
    location: Optional[str] = None
    weather: Optional[str] = None
    prompt_id: Optional[str] = None

class EntryResponse(BaseModel):
    id: str
    title: str
    content: str
    entry_date: str
    location: Optional[str]
    weather: Optional[str]
    journal_id: Optional[str]
    prompt_id: Optional[str]
    word_count: int
    is_pinned: bool
    created_at: str
    updated_at: str

class EntryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    entry_date: Optional[str] = None
    entry_datetime_utc: Optional[str] = None
    entry_timezone: Optional[str] = None
    location: Optional[str] = None
    weather: Optional[str] = None
    is_pinned: Optional[bool] = None

class Mood(BaseModel):
    id: str
    name: str
    icon: str
    category: str
    created_at: datetime
    updated_at: datetime

class MoodLogCreate(BaseModel):
    mood_id: str
    entry_id: str
    note: Optional[str] = None

class MoodLogResponse(BaseModel):
    id: str
    mood_id: str
    note: Optional[str]
    entry_id: Optional[str]
    user_id: str
    created_at: datetime
    logged_date: str
    mood: Mood
    entry_date: Optional[str]

class MoodLogUpdate(BaseModel):
    mood_id: str
    note: Optional[str] = None

class EntryTagResponse(BaseModel):
    entry_id: str
    tag_id: str
    created_at: datetime
    updated_at: datetime

class Tag(BaseModel):
    id: str
    name: str
    user_id: str
    usage_count: int
    created_at: datetime
    updated_at: datetime