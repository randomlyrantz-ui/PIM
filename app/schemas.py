from datetime import datetime

from pydantic import BaseModel, Field


class SourceCreate(BaseModel):
    name: str
    url: str


class SourceRead(BaseModel):
    id: int
    name: str
    url: str
    source_type: str
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DomainCreate(BaseModel):
    name: str
    description: str
    keywords: list[str] = Field(default_factory=list)


class DomainRead(BaseModel):
    id: int
    name: str
    description: str
    keywords: list[str]


class ArticleRead(BaseModel):
    id: int
    title: str
    url: str
    summary: str | None
    stance: str | None
    contrarian_flag: bool
    source: str
    published_at: datetime | None


class FeedbackCreate(BaseModel):
    positive: bool | None = None
    label: str | None = None
