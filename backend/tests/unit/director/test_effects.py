import shutil
import subprocess

import pytest

from agent.director import effects as E


def test_capcut_names_resolve_to_ids():
    assert E.slug("Nháy trắng") == "nhay-trang"
    assert E.slug("Đóng ngang") == "dong-ngang"
    assert E.resolve("Bùng sáng vàng", E.TRANSITIONS) == "bung-sang-vang"
    assert E.resolve("light leak", E.TRANSITIONS) == "bung-sang-vang"
    assert E.resolve("dissolve", E.TRANSITIONS) == "hoa-tan"
    assert E.resolve("Phim cổ điển", E.LOOKS) == "phim-co-dien"
    assert E.resolve("không có thật", E.TRANSITIONS) is None
    assert E.resolve(None, E.LOOKS) is None


def test_unknown_transition_is_a_cut_and_overlap_fits_short_clips():
    clips = [E.ClipEdit("a", 0, 1.0, transition_out="hoa-tan"),     # 0.7s dissolve on a 1s clip → 0.4s
             E.ClipEdit("b", 0, 5, transition_out="xoay 720 độ"),
             E.ClipEdit("c", 0, 5, transition_out="nhay-trang"), E.ClipEdit("d", 0, 5)]
    assert E.plan_transitions(clips) == [("hoa-tan", 0.4), ("cat", 0.0), ("nhay-trang", 0.0)]


def test_xfade_offsets_follow_the_film_so_far():
    clips = [E.ClipEdit("a", 0, 4, transition_out="hoa-tan"), E.ClipEdit("b", 0, 4, transition_out="lot-ngang"),
             E.ClipEdit("c", 0, 4)]
    g = E.film_cmd("ffmpeg", clips, "o.mp4", "720x1280")
    fc = g[g.index("-filter_complex") + 1]
    assert "xfade=transition=fade:duration=0.7:offset=3.300" in fc
    assert "xfade=transition=smoothleft:duration=0.35:offset=6.950" in fc   # 4 + 4 - 0.7 - 0.35


def test_catalog_lists_every_effect():
    text = E.catalog_text()
    for table in (E.LOOKS, E.TRANSITIONS, E.CLIP_FX):
        assert all(k in text for k in table)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg missing")
def test_every_effect_renders(tmp_path):
    """All transitions and effects in two real (tiny) renders: the graph is valid and the length is right."""
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=180x320:r=24:d=3",
                    "-f", "lavfi", "-i", "sine=d=3", "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", str(src)], check=True)
    trs = [k for k in E.TRANSITIONS if k != "cat"]
    fx = list(E.CLIP_FX)
    for part, names in enumerate((trs[:9], trs[9:])):
        clips = [E.ClipEdit(str(src), 0.5, 2.5, audio=(i % 3 != 2), fx=[fx[(part * 10 + i) % len(fx)]],
                            transition_out=names[i] if i < len(names) else None) for i in range(len(names) + 1)]
        out = tmp_path / f"p{part}.mp4"
        cmd = E.film_cmd("ffmpeg", clips, str(out), "180x320", look=list(E.LOOKS)[part + 1])
        cmd[cmd.index("slow")] = "ultrafast"
        r = subprocess.run(cmd, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-800:]
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(out)], capture_output=True, text=True).stdout)
        expected = sum(c.length for c in clips) - sum(d for _, d in E.plan_transitions(clips))
        assert abs(dur - expected) < 0.2


def test_every_film_hides_flows_mark_in_the_bottom_right_corner():
    """24/10: Flow's ✦ showed in both ambient trial clips (copied from the reference pictures); the user chose to hide
    it in the edit, for every film mode. Measured on 1280x720: centre 120px in from the right and bottom edges."""
    assert E.unmark(1920, 1080) == "delogo=x=1692:y=852:w=96:h=96"     # centre (1740, 900) = (1160, 600) at 720p
    assert E.unmark(1080, 1920) == "delogo=x=852:y=1692:w=96:h=96"
    cmd = E.film_cmd("ffmpeg", [E.ClipEdit(src="a.mp4", start=0, end=5)], "out.mp4", "1920x1080")
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert graph.index("delogo") < graph.index("[v0]")
