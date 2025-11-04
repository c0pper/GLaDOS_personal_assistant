
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