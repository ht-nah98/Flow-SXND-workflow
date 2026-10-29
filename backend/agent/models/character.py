from pydantic import BaseModel


from agent.models.enums import EntityType


class CharacterCreate(BaseModel):
    name: str
    entity_type: EntityType = "character"
    description: str | None = None
    image_prompt: str | None = None
    voice_description: str | None = None  # max ~30 words
    reference_image_url: str | None = None
    media_id: str | None = None


class CharacterUpdate(BaseModel):
    name: str | None = None
    entity_type: EntityType | None = None
    description: str | None = None
    image_prompt: str | None = None
    voice_description: str | None = None
    reference_image_url: str | None = None
    media_id: str | None = None


class Character(BaseModel):
    id: str
    name: str
    slug: str | None = None
    entity_type: EntityType = "character"
    description: str | None = None
    image_prompt: str | None = None
    voice_description: str | None = None
    reference_image_url: str | None = None
    media_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
