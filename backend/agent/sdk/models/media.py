"""Media-related value objects used across SDK domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MediaType(str, Enum):
    """Kind of media asset."""
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    UPSCALE = "UPSCALE"


class MediaStatus(str, Enum):
    """Processing status for any media slot."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class MediaAsset:
    """A resolved media artifact (image, video, or upscaled video)."""
    media_id: str | None = None
    url: str | None = None
    status: str = "PENDING"

    @property
    def ready(self) -> bool:
        return self.status == "COMPLETED" and self.media_id is not None


@dataclass
class OrientationSlot:
    """Holds image / video / upscale assets for one orientation (vertical or horizontal)."""
    image: MediaAsset = field(default_factory=MediaAsset)
    video: MediaAsset = field(default_factory=MediaAsset)
    upscale: MediaAsset = field(default_factory=MediaAsset)
    end_scene_media_id: str | None = None


@dataclass
class GenerationResult:
    """Result from a direct SDK execution operation."""
    success: bool
    media_id: str | None = None
    url: str | None = None
    error: str | None = None
    raw: dict | None = field(default=None, repr=False)
