"""Plan → FlowKit project/entities/video/scenes (spec stage INGEST). Idempotent per run."""
import json
import logging
import mimetypes
import uuid
from pathlib import Path

from agent.api.projects import _read_flow_project_id
from agent.db import crud
from agent.director import store
from agent.director.schemas import ShotList, ShotPrompts, Story
from agent.services.flow_client import CURRENT_ACCOUNT, get_flow_client

logger = logging.getLogger(__name__)


async def _flow_project_id(name: str) -> str:
    """Local project id must equal the Flow project uuid (every Flow RPC is scoped to it)."""
    client = get_flow_client()
    if not client.connected:
        return str(uuid.uuid4())
    res = await client.create_project(name, "PINHOLE")
    if res.get("error"):
        raise RuntimeError(f"Flow project creation failed: {res['error']}")
    return _read_flow_project_id(res)


def _home(client) -> str | None:
    home = getattr(client, "home_account", None)
    return home() if callable(home) else getattr(client, "last_account", None)


def video_mode_for(film_mode: str | None) -> str:
    """How the script node makes a clip: a keyframe film goes still → video, the others prompt + asset pictures.
    23/10: set from the start (the concert film's node showed "Prompt + asset" until INGEST)."""
    return "image" if film_mode == "keyframe" else "refs"


async def create_project(name: str, brief: dict) -> dict:
    """The run's project exists from the start, so the canvas can follow the director at work."""
    # The film lives in the account whose profile created its Flow project (account rotation, 19/10), so that account
    # is chosen first and the project is made there. 23/10 Blue Morning: with three profiles connected the project went
    # to whichever answered, the film was bound to another — that account had no such project, every clip came back
    # NO_MEDIA_CREATED.
    account = CURRENT_ACCOUNT.get() or _home(get_flow_client())
    token = CURRENT_ACCOUNT.set(account) if account else None
    try:
        pid = await _flow_project_id(name)
    finally:
        if token:
            CURRENT_ACCOUNT.reset(token)
    project = await crud.create_project(name=name, id=pid, material=brief.get("style") or "realistic",
                                        language=brief.get("language") or "en", user_paygate_tier="PAYGATE_TIER_TWO",
                                        video_model_family="omni_flash")
    if brief.get("film_mode") == "keyframe":
        project = await crud.update_project(project["id"], video_mode=video_mode_for("keyframe")) or project
    if account:
        project = await crud.update_project(project["id"], flow_account=account) or project
    return {"project_id": project["id"], "video_id": None, "entities": {}, "scenes": {}}


async def upload_reference(cid: str, project_id: str, path: str) -> bool:
    """Make the user's own picture the entity's reference. False (generate instead) when it cannot be uploaded."""
    from agent.api.assets import _record_upload, _signed_image_url
    from agent.api.flow import _upload_image_bytes
    client = get_flow_client()
    if not client.connected or not Path(path).is_file():
        return False
    try:
        name = Path(path).name
        mime = mimetypes.guess_type(name)[0] or "image/jpeg"
        up = await _upload_image_bytes(client, Path(path).read_bytes(), project_id=project_id,
                                       mime_type=mime, file_name=name)
        url = await _signed_image_url(client, up["media_id"])
        await _record_upload(cid, project_id, up["media_id"], url, name)
        await crud.update_character(cid, media_id=up["media_id"], reference_image_url=url)
        return True
    except Exception as e:  # the asset falls back to a generated reference (budgeted at the SCRIPT gate)
        logger.warning("upload of %s for %s failed: %s", path, cid, e)
        return False


async def _new_entity(project_id: str, c) -> str:
    ch = await crud.create_character(name=c.name, entity_type=c.entity_type,
                                     description=f"{c.description}. {c.continuity_lock}",
                                     image_prompt=c.image_prompt)
    await crud.link_character_to_project(project_id, ch["id"])
    if c.provided_image:
        await upload_reference(ch["id"], project_id, c.provided_image)
    return ch["id"]


def _scene_fields(s, p, style: str = "") -> dict:
    """The scene title is the shot's one idea. Keyframe mode (B13, playbook 10): the scene image is the shot's opening
    still — its keyframe plus the film's style block, generated from the scene's cast pictures."""
    image = f"{s.keyframe.strip()}\n\n{style.strip()}".strip() if s.keyframe else None
    return dict(prompt=s.idea, image_prompt=image, video_prompt=p.video_prompt)


async def _save(run: dict) -> None:
    await store.update_run(run["id"], plan=run["plan"])


async def ingest(run: dict) -> dict:
    """Create project/entities/video/scenes, persisting ids after every step so a crash resumes."""
    plan = run["plan"]
    brief, story = plan["brief"], Story.model_validate(plan["story"])
    shots = ShotList.model_validate(plan["shotlist"])
    sp = ShotPrompts.model_validate(plan["prompts"])
    prompts = {p.shot_id: p for p in sp.prompts}
    name = brief["logline"][:80]
    ids = plan.get("ids")
    if not ids:
        ids = plan["ids"] = await create_project(name, {"style": brief["material"]})
        await store.update_run(run["id"], project_id=ids["project_id"], plan=plan)
    # Keep the name the project got from the user's own words (the video takes it too).
    name = (await crud.get_project(ids["project_id"]))["name"]
    await crud.update_project(ids["project_id"], story=story.synopsis, material=brief["material"],
                              language=brief["language"],
                              **({"video_mode": "image"} if brief.get("film_mode") == "keyframe" else {}))
    for c in story.cast:
        if c.name not in ids["entities"]:
            ids["entities"][c.name] = await _new_entity(ids["project_id"], c)
            await _save(run)
    if not ids["video_id"]:
        video = await crud.create_video(project_id=ids["project_id"], title=name,
                                        orientation=brief["orientation"],
                                        target_duration_s=brief["target_s"])
        ids["video_id"] = video["id"]
        await _save(run)
    for s in sorted(shots.shots, key=lambda s: s.order):
        if s.id in ids["scenes"]:
            continue
        f = _scene_fields(s, prompts[s.id], sp.style_block)
        sc = await crud.create_scene(video_id=ids["video_id"], display_order=s.order - 1,
                                     prompt=f["prompt"], image_prompt=f["image_prompt"],
                                     video_prompt=f["video_prompt"], character_names=s.cast)
        await crud.update_scene(sc["id"], duration=s.duration_s, video_mode=s.mode,
                                shot_spec=json.dumps(s.model_dump(), ensure_ascii=False))
        ids["scenes"][s.id] = sc["id"]
        await _save(run)
    return ids


async def sync_scenes(run: dict) -> dict:
    """After a revision: push the changed plan into the already-created scenes/entities."""
    plan = run["plan"]
    ids = plan["ids"]
    story = Story.model_validate(plan["story"])
    shots = ShotList.model_validate(plan["shotlist"])
    sp = ShotPrompts.model_validate(plan["prompts"])
    prompts = {p.shot_id: p for p in sp.prompts}
    await crud.update_project(ids["project_id"], story=story.synopsis)
    for c in story.cast:
        if c.name not in ids["entities"]:
            ids["entities"][c.name] = await _new_entity(ids["project_id"], c)
    keep = set()
    for s in shots.shots:
        fields = dict(_scene_fields(s, prompts[s.id], sp.style_block), display_order=s.order - 1,
                      character_names=json.dumps(s.cast), duration=s.duration_s, video_mode=s.mode,
                      shot_spec=json.dumps(s.model_dump(), ensure_ascii=False))
        if s.id in ids["scenes"]:
            await crud.update_scene(ids["scenes"][s.id], **fields)
        else:
            sc = await crud.create_scene(video_id=ids["video_id"], display_order=s.order - 1,
                                         prompt=fields["prompt"], character_names=s.cast)
            await crud.update_scene(sc["id"], **fields)
            ids["scenes"][s.id] = sc["id"]
        keep.add(s.id)
    for sid in [k for k in ids["scenes"] if k not in keep]:
        await crud.delete_scene(ids["scenes"].pop(sid))
    return ids
