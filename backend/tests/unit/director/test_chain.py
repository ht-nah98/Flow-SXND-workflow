"""Directive B12 (playbook 09 §6): a continuous film is made chain by chain, each clip from the last frame before."""
import subprocess

import pytest

from agent.director import chain
from agent.director.schemas import Action
from tests.unit.director.fixtures import _shot


def _s(i, continues):
    return _shot(id=f"s{i}", order=i, duration_s=8, continues=continues,
                 actions=[Action(start_s=0, end_s=8, what="hold", kind="hold")])


def test_shots_split_into_chains_where_a_shot_does_not_continue():
    shots = [_s(1, False), _s(2, True), _s(3, True), _s(4, False), _s(5, True)]
    assert [[s.id for s in c] for c in chain.chains(shots)] == [["s1", "s2", "s3"], ["s4", "s5"]]


@pytest.fixture
def fake_flow(monkeypatch):
    log, status = [], {}

    async def gen(s):
        log.append(("gen", s.id))
        return f"r-{s.id}"

    async def wait(ids, run_id=None):
        return {i: {"status": status.get(i, "COMPLETED")} for i in ids}

    async def link(run, prev, cur):
        log.append(("link", prev.id, cur.id))
        return "m"

    async def noop(*a, **k):
        return None
    monkeypatch.setattr(chain.production, "wait_requests", wait)
    monkeypatch.setattr(chain, "link", link)
    monkeypatch.setattr(chain.store, "update_run", noop)
    return gen, log, status


async def test_a_chain_is_made_in_order_each_clip_after_the_frame_before_it(fake_flow):
    gen, log, _ = fake_flow
    run = {"id": "r", "plan": {"ids": {}}}
    await chain.make_all(run, [_s(1, False), _s(2, True), _s(3, True)], gen)
    assert log == [("gen", "s1"), ("link", "s1", "s2"), ("gen", "s2"), ("link", "s2", "s3"), ("gen", "s3")]
    assert run["plan"]["failed"] == {}


async def test_a_failed_clip_stops_its_chain_but_not_the_others(fake_flow):
    gen, log, status = fake_flow
    status["r-s1"] = "FAILED"
    run = {"id": "r", "plan": {"ids": {}}}
    await chain.make_all(run, [_s(1, False), _s(2, True), _s(3, False)], gen)
    assert ("gen", "s2") not in log and ("gen", "s3") in log
    assert run["plan"]["failed"] == {"s1": "video", "s2": chain.BLOCKED}
    status.clear()                                   # s1 made again (retry / by hand): s2 is no longer blocked
    await chain.make_all(run, [_s(1, False), _s(2, True)], gen)
    assert run["plan"]["failed"] == {} and log[-1] == ("gen", "s2")


def test_the_last_frame_is_cut_from_the_real_clip(tmp_path):
    clip = tmp_path / "c.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=24:duration=2",
                    "-pix_fmt", "yuv420p", str(clip)], check=True)
    out = chain.last_frame(clip, tmp_path / "f" / "last.jpg")
    assert out.is_file() and out.stat().st_size > 1000


async def test_the_frame_is_linked_once_per_take(monkeypatch, tmp_path):
    scenes = {"S1": {"id": "S1", "horizontal_video_media_id": "take-1"}, "S2": {"id": "S2"}}
    uploads, updates = [], []

    async def get_scene(i):
        return scenes[i]

    async def update_scene(i, **kw):
        updates.append((i, kw))

    async def local_clip(scene, ori, d):
        return tmp_path / "c.mp4"

    async def upload(path, pid):
        uploads.append(path.name)
        return f"m{len(uploads)}"

    async def noop(*a, **k):
        return None
    monkeypatch.setattr(chain.crud, "get_scene", get_scene)
    monkeypatch.setattr(chain.crud, "update_scene", update_scene)
    monkeypatch.setattr(chain.cut_mod, "local_clip", local_clip)
    monkeypatch.setattr(chain, "_upload", upload)
    monkeypatch.setattr(chain, "last_frame", lambda clip, out: out)
    monkeypatch.setattr(chain.store, "update_run", noop)
    run = {"id": "r", "plan": {"ids": {"project_id": "p", "scenes": {"s1": "S1", "s2": "S2"}},
                               "brief": {"orientation": "HORIZONTAL"}}}
    prev, cur = _s(1, False), _s(2, True)
    assert await chain.link(run, prev, cur) == "m1"
    assert await chain.link(run, prev, cur) == "m1" and len(uploads) == 1        # same take: reused
    assert updates == [("S2", {"horizontal_end_scene_media_id": "m1"})]
    scenes["S1"]["horizontal_video_media_id"] = "take-2"                         # a new take of s1
    assert await chain.link(run, prev, cur) == "m2"


def test_a_continuous_film_is_cut_almost_whole_with_no_added_transition_inside_a_chain():
    from agent.director import cut
    shots = [_s(1, False), _s(2, True), _s(4, True), _s(5, False)]   # s3 dropped: s4 follows s2 in the film
    assert cut.chain_trims(shots) == [[0.0, 8.0], [cut.CHAIN_HEAD_S, 8.0], [0.0, 8.0], [0.0, 8.0]]
    edit = {"look": None, "clips": [{"shot_id": s.id, "fx": [], "transition_out": "nhay-trang"} for s in shots]}
    out = cut.chain_edit(edit, shots)
    assert [c["transition_out"] for c in out["clips"]] == ["cat", "nhay-trang", "nhay-trang", "nhay-trang"]


def test_joins_inside_a_chain_cut_on_motion():
    """Agent Review of Old Walt (22/10): joins scored 5/10 — the inherited frame is redrawn slightly differently and two
    still frames side by side show it; two 4s still holds met at each join. Start on the first movement, keep ≤2.5s
    of the final hold."""
    from agent.director import cut

    def shot(i, continues, beats):
        return _shot(id=f"s{i}", order=i, duration_s=10, continues=continues,
                     actions=[Action(start_s=a, end_s=b, what="x", kind=k) for a, b, k in beats])
    a = shot(1, False, [(0, 2, "hold"), (2, 5, "action"), (5, 6, "camera"), (6, 10, "hold")])
    b = shot(2, True, [(0, 1.2, "hold"), (1.2, 4, "action"), (4, 6, "camera"), (6, 10, "reaction")])
    assert cut.chain_trims([a, b]) == [[0.0, 8.5], [1.2, 10.0]]
