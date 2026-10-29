from pydantic import BaseModel, Field, model_validator
from typing import Literal
from agent.models.enums import ProjectStatus, PaygateTier, EntityType

# Which Flow video family the worker uses for this project's scenes.
# veo        -> Veo 3.1 i2v (1080p). r2v / first+last are unported on batch.
# omni_flash -> Omni Flash (720p, 4/6/8/10s); all frame/ref modes are ported.
VideoModelFamily = Literal["veo", "omni_flash"]
# How a scene's video is made. refs (default, directive D1): prompt + asset references, no image step.
# image: generate a first-frame image, then the video from it (opt-in, manual projects only).
VideoMode = Literal["refs", "image"]


class CharacterInput(BaseModel):
    """Reference entity stub provided at project creation time."""
    name: str
    entity_type: EntityType = "character"
    description: str | None = None
    voice_description: str | None = None  # max ~30 words, characters/creatures only


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    story: str | None = None
    language: str = "en"
    user_paygate_tier: PaygateTier = "PAYGATE_TIER_ONE"
    tool_name: str = "PINHOLE"
    # Optional explicit reuse. When omitted, FlowKit creates a fresh real Flow
    # project through the current batchexecute endpoint.
    flow_project_id: str | None = None
    material: str = Field("realistic", pattern=r"^[a-z0-9][a-z0-9_]{1,63}$")  # material ID from GET /api/materials
    style: str | None = None  # deprecated: use material instead; "3D"→"3d_pixar", "photorealistic"→"realistic"
    allow_music: bool = False  # when True, skip "no background music" suffix in video prompts
    allow_voice: bool = False  # when True, keep character dialogue in video audio (suppress only music/narration)
    video_model_family: VideoModelFamily = "veo"
    characters: list[CharacterInput] | None = None

    @model_validator(mode="before")
    @classmethod
    def map_style_to_material(cls, data):
        if isinstance(data, dict):
            style = data.get("style")
            # Only map if style is provided AND material is not explicitly set
            if style and "material" not in data:
                compat_map = {"3D": "3d_pixar", "3d": "3d_pixar", "photorealistic": "realistic"}
                data["material"] = compat_map.get(style, style.lower().replace(" ", "_"))
        return data


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    story: str | None = None
    thumbnail_url: str | None = None
    language: str | None = None
    status: ProjectStatus | None = None
    user_paygate_tier: PaygateTier | None = None
    narrator_voice: str | None = None
    narrator_ref_audio: str | None = None
    material: str | None = None
    allow_music: bool | None = None
    allow_voice: bool | None = None
    video_mode: VideoMode | None = None
    video_model_family: VideoModelFamily | None = None


class Project(BaseModel):
    id: str
    name: str
    description: str | None = None
    story: str | None = None
    thumbnail_url: str | None = None
    language: str = "en"
    status: str = "ACTIVE"
    user_paygate_tier: str = "PAYGATE_TIER_ONE"
    material: str | None = None
    allow_music: bool = False
    allow_voice: bool = False
    video_model_family: str = "veo"
    video_mode: str = "refs"
    flow_account: str | None = None
    narrator_voice: str | None = None
    narrator_ref_audio: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
