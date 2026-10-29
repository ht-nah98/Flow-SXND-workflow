from pydantic import BaseModel
from agent.models.enums import ChainType, SceneSource, StatusType


class SceneCreate(BaseModel):
    video_id: str
    display_order: int = 0
    prompt: str
    image_prompt: str | None = None
    video_prompt: str | None = None
    transition_prompt: str | None = None
    character_names: list[str] | None = None
    parent_scene_id: str | None = None
    chain_type: ChainType = "ROOT"
    source: SceneSource | None = None


class SceneUpdate(BaseModel):
    prompt: str | None = None
    image_prompt: str | None = None
    video_prompt: str | None = None
    character_names: list[str] | None = None
    parent_scene_id: str | None = None
    chain_type: ChainType | None = None
    source: SceneSource | None = None
    display_order: int | None = None

    vertical_image_url: str | None = None
    vertical_image_media_id: str | None = None
    vertical_image_status: StatusType | None = None
    vertical_video_url: str | None = None
    vertical_video_media_id: str | None = None
    vertical_video_status: StatusType | None = None
    vertical_upscale_url: str | None = None
    vertical_upscale_media_id: str | None = None
    vertical_upscale_status: StatusType | None = None

    horizontal_image_url: str | None = None
    horizontal_image_media_id: str | None = None
    horizontal_image_status: StatusType | None = None
    horizontal_video_url: str | None = None
    horizontal_video_media_id: str | None = None
    horizontal_video_status: StatusType | None = None
    horizontal_upscale_url: str | None = None
    horizontal_upscale_media_id: str | None = None
    horizontal_upscale_status: StatusType | None = None

    vertical_end_scene_media_id: str | None = None
    horizontal_end_scene_media_id: str | None = None

    transition_prompt: str | None = None

    trim_start: float | None = None
    trim_end: float | None = None
    duration: float | None = None
    narrator_text: str | None = None


class Scene(BaseModel):
    id: str
    video_id: str
    display_order: int = 0
    prompt: str | None = None
    image_prompt: str | None = None
    video_prompt: str | None = None
    character_names: list[str] | None = None  # parsed from JSON
    parent_scene_id: str | None = None
    chain_type: str = "ROOT"
    source: str | None = "root"

    vertical_image_url: str | None = None
    vertical_image_media_id: str | None = None
    vertical_image_status: str = "PENDING"
    vertical_video_url: str | None = None
    vertical_video_media_id: str | None = None
    vertical_video_status: str = "PENDING"
    vertical_upscale_url: str | None = None
    vertical_upscale_media_id: str | None = None
    vertical_upscale_status: str = "PENDING"

    horizontal_image_url: str | None = None
    horizontal_image_media_id: str | None = None
    horizontal_image_status: str = "PENDING"
    horizontal_video_url: str | None = None
    horizontal_video_media_id: str | None = None
    horizontal_video_status: str = "PENDING"
    horizontal_upscale_url: str | None = None
    horizontal_upscale_media_id: str | None = None
    horizontal_upscale_status: str = "PENDING"

    vertical_end_scene_media_id: str | None = None
    horizontal_end_scene_media_id: str | None = None

    transition_prompt: str | None = None

    trim_start: float | None = None
    trim_end: float | None = None
    duration: float | None = None
    narrator_text: str | None = None

    created_at: str | None = None
    updated_at: str | None = None
