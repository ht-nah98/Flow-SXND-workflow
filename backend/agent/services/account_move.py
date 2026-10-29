"""Account rotation, step 4 (docs/thiet-ke/ke-hoach-luan-chuyen-tai-khoan.md; 22/10 the user: Google flagged Hoang for
"unusual activity" mid-film — "Đổi tài khoản làm thôi").

Move a film to another Google account without spending credit: a new Flow project is created in that account, every
asset picture already made is uploaded there again (a media id is useless outside its account), and Flow calls for the
film's local project id are sent under the new project id from then on (`flow_client.PROJECT_ALIASES`). Queued
requests of the film go to the new account; clips already made keep their local files."""
import base64
import logging

import aiohttp

from agent.db import account_crud, crud
from agent.services import flow_client as fc

logger = logging.getLogger(__name__)
_END_REFS = ("horizontal_end_scene_media_id", "vertical_end_scene_media_id")


async def load_aliases() -> None:
    for p in await crud.list_projects():
        if p.get("flow_project_alias"):
            fc.PROJECT_ALIASES[p["id"]] = p["flow_project_alias"]


async def _download(url: str) -> tuple[bytes, str]:
    async with aiohttp.ClientSession() as s, s.get(url, timeout=aiohttp.ClientTimeout(total=60)) as r:
        if r.status != 200 or not r.headers.get("Content-Type", "").startswith("image/"):
            raise ValueError(f"HTTP {r.status}")
        return await r.read(), r.headers["Content-Type"].split(";")[0].strip()


async def _flow_requests(pid: str) -> list[dict]:
    return [q for q in await crud.list_requests(project_id=pid) if q["status"] in ("PENDING", "PROCESSING")]


async def move_project(pid: str, account: str, repair: bool = False) -> dict:
    """Raises ValueError (nothing changed) when the move cannot be done safely.

    repair=True (23/10 Blue Morning): the film stays in its account but gets a new Flow project there, for a film whose
    project was made in another profile ("Không tìm thấy dự án"). Its pictures and pinned frames already belong to the
    account, so nothing is re-uploaded and no pin is dropped."""
    from agent.api.projects import _read_flow_project_id
    project = await crud.get_project(pid)
    if not project:
        raise ValueError("project not found")
    same = project.get("flow_account") == account
    if same and not repair:
        raise ValueError(f"phim đã ở tài khoản {account}")
    client = fc.get_flow_client()
    if not client.connected_accounts().get(account):
        raise ValueError(f"tài khoản {account} chưa kết nối — mở Chrome profile của tài khoản đó (tab Flow + FlowKit)")
    # Work waiting for an offline account is not in flight (the worker only re-checks it): only a connected old
    # account can have a request inside Google right now.
    if (client.connected_accounts().get(project.get("flow_account") or "")
            and any(q["status"] == "PROCESSING" for q in await _flow_requests(pid))):
        raise ValueError("đang có yêu cầu gửi Flow cho phim này — đợi nó xong rồi chuyển")

    # Every picture is fetched before anything changes: a half-moved film would be worse than none.
    pictures = []
    for ch in [] if same else await crud.get_project_characters(pid):
        if not ch.get("media_id"):
            continue
        try:
            pictures.append((ch, *await _download(ch.get("reference_image_url") or "")))
        except Exception as e:  # noqa: BLE001 — reported to the user, nothing moved
            raise ValueError(f"không tải được ảnh '{ch['name']}' ({e}) — chưa chuyển gì") from e

    token = fc.CURRENT_ACCOUNT.set(account)
    try:
        res = await client.create_project(project["name"][:80])
        if res.get("error"):
            raise ValueError(f"không tạo được project Flow ở {account}: {res['error']}")
        new = _read_flow_project_id(res)
        uploaded = []
        for ch, data, mime in pictures:
            up = await client.upload_image(base64.b64encode(data).decode(), mime_type=mime, project_id=new,
                                           file_name=f"{ch.get('slug') or ch['id']}.jpg")
            if not up.get("_mediaId"):
                raise ValueError(f"tải ảnh '{ch['name']}' lên {account} lỗi: {str(up.get('error') or up)[:200]}")
            uploaded.append((ch, up["_mediaId"]))
    finally:
        fc.CURRENT_ACCOUNT.reset(token)

    old = project.get("flow_account")
    for ch, media in uploaded:
        await crud.update_character(ch["id"], media_id=media)
    for v in [] if same else await crud.list_videos(pid):    # chained last frames were uploaded to the old account
        for s in await crud.list_scenes(v["id"]):
            if any(s.get(k) for k in _END_REFS):
                await crud.update_scene(s["id"], **{k: None for k in _END_REFS})
    for q in await _flow_requests(pid):                      # the old account's blocks do not count in the new one
        await crud.update_request(q["id"], retry_count=0, error_message="")   # None is ignored by _update
    await crud.update_project(pid, flow_account=account, flow_project_alias=new)
    fc.PROJECT_ALIASES[pid] = new
    await account_crud.seen(account)
    logger.info("Project %s moved %s → %s (Flow project %s, %d pictures)", pid[:8], old, account, new, len(uploaded))
    return {"project_id": pid, "from": old, "to": account, "flow_project_id": new,
            "pictures": [ch["name"] for ch, _ in uploaded]}
