from pydantic import BaseModel
from agent.models.enums import VideoStatus


class VideoCreate(BaseModel):
    project_id: str
    title: str
    description: str | None = None
    display_order: int = 0
    orientation: str | None = None
    target_duration_s: float | None = None


class VideoUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    display_order: int | None = None
    status: VideoStatus | None = None
    orientation: str | None = None
    vertical_url: str | None = None
    horizontal_url: str | None = None
    thumbnail_url: str | None = None
    duration: float | None = None
    target_duration_s: float | None = None
    resolution: str | None = None
    youtube_id: str | None = None
    privacy: str | None = None
    tags: str | None = None


class Video(BaseModel):
    id: str
    project_id: str
    title: str
    description: str | None = None
    display_order: int = 0
    status: str = "DRAFT"
    orientation: str | None = None
    vertical_url: str | None = None
    horizontal_url: str | None = None
    thumbnail_url: str | None = None
    duration: float | None = None
    target_duration_s: float | None = None
    resolution: str | None = None
    youtube_id: str | None = None
    privacy: str = "unlisted"
    tags: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
