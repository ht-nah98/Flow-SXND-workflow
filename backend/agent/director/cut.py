"""Final cut: QC trims → ffmpeg trim/normalize/concat/music (spec stage CUT)."""
import asyncio
import shutil
import subprocess
from pathlib import Path

from agent.director import effects
from agent.services import post_process, video_reviewer


VOICE_WINDOW = (1.0, 7.0)   # prompts time speech inside 1.5–6.5s; keep a margin so no word is cut
MAX_HOLD_S = 8.0            # directive E1: cut every 5–8s; a silent clip never holds longer
CUT_MAX_OVER = 1.4          # directive E1b: the film follows its material, up to 1.4 × the length asked


def _window(a: float, b: float, length: float, focus) -> tuple[float, float]:
    """A `length` window inside [a, b]: around the action (`focus`) when it fits, else ending on its payoff."""
    if not focus or length >= b - a:
        return a, a + length
    fs, fe = max(a, focus[0]), min(b, focus[1])
    w0 = fs - (length - (fe - fs)) / 2 if fe - fs <= length else fe - length
    w0 = min(max(w0, a), b - length)
    return w0, w0 + length


def _shorten(t: list[float], need: float, focus) -> None:
    """Take `need` seconds off a window: what lies outside the action first, then the head — never the payoff.
    Without a known action the tail goes, as before."""
    if not focus:
        t[1] -= need
        return
    head = min(need, max(0.0, focus[0] - t[0]))
    t[0] += head
    need -= head
    tail = min(need, max(0.0, t[1] - focus[1]))
    t[1] -= tail
    t[0] += need - tail


def plan_trims(clips: list[dict], target_s: float, min_clip: float = 2.0) -> list[tuple[float, float]]:
    """QC windows (the usable part of each clip), each silent one held at most MAX_HOLD_S. The length asked is
    approximate: the film is only shortened when it runs past CUT_MAX_OVER × target_s. Then silent clips give up
    time first, and voiced clips lose their tail after the spoken stretch (VOICE_WINDOW). A spoken word is never
    cut: a film a few seconds long is better than a cut word.

    21/10 (Agent Review F3): `focus` = (first action start, last action end) of the shot. Windows used to start at
    the QC trim-in and lose their tail, so every clip kept its first ~5s and the hug, the dropped receiver and the
    hand on the glass never reached the film. Now a window sits on the action and shortening spares the payoff."""
    trims, focus = [], []
    for c in clips:
        a, b = float(c["trim_in"]), float(c["trim_out"])
        if c.get("voice"):
            a, b = min(a, VOICE_WINDOW[0]), max(b, VOICE_WINDOW[1])
        a = max(0.0, min(a, c["duration"]))
        b = max(a, min(b, c["duration"]))
        f = c.get("focus")
        f = (max(a, float(f[0])), min(b, float(f[1]))) if f and float(f[1]) > float(f[0]) else None
        if not c.get("voice"):
            a, b = _window(a, b, min(b - a, MAX_HOLD_S), f)
        trims.append([a, b])
        focus.append(f and (max(a, f[0]), min(b, f[1])))
    limit = CUT_MAX_OVER * target_s

    def shrink(room: list[float], keep_end: bool = False):
        excess = sum(b - a for a, b in trims) - limit
        spare = sum(room)
        if excess > 0 and spare > 0:
            ratio = min(1.0, excess / spare)
            for t, r, f in zip(trims, room, focus):
                if keep_end:
                    _shorten(t, r * ratio, f)
                else:
                    t[1] -= r * ratio

    if sum(b - a for a, b in trims) > limit:
        shrink([0.0 if c.get("voice") else max(0.0, (b - a) - min_clip) for c, (a, b) in zip(clips, trims)], keep_end=True)
        shrink([max(0.0, b - max(a + min_clip, VOICE_WINDOW[1])) if c.get("voice") else 0.0
                for c, (a, b) in zip(clips, trims)])
    return [(round(a, 3), round(b, 3)) for a, b in trims]


FILM_FPS = 24    # Omni Flash renders 24 fps; 30 would only duplicate frames
FILM_CRF = 16    # above visually lossless: the master must never look worse than the Flow clips
FILM_SIZE = {"VERTICAL": "1080x1920", "HORIZONTAL": "1920x1080"}
# Flow's best output is 720p. The master is scaled once (lanczos) to 1080p: no new detail, but
# YouTube gives 1080p uploads a far higher bitrate than 720p, so the viewer sees the clips' full quality.


def _ok(result: bool, step: str):
    if not result:
        raise RuntimeError(f"ffmpeg {step} failed")


def _render_film(cmd: list[str]) -> bool:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        post_process.logger.error("film encode failed: %s", r.stderr[-600:])
    return r.returncode == 0


async def render_cut(clip_paths: list[str], trims: list[tuple[float, float]], out_path: str,
                     size: str, music_path: str | None = None, edit: dict | None = None) -> str:
    """The whole film in ONE encode: trims, scale, colour grade (film_look), clip effects and transitions
    (effects.py). `edit` = {"look": id, "clips": [{"fx": [...], "transition_out": id}, ...]}; absent → plain cuts."""
    out = Path(out_path)
    work = out.parent / "_dung-phim" / "work"
    work.mkdir(parents=True, exist_ok=True)
    edit = edit or {}
    per = edit.get("clips") or []
    clips = [effects.ClipEdit(src, a, b, _has_audio(src),
                              fx=list((per[i] if i < len(per) else {}).get("fx") or []),
                              transition_out=(per[i] if i < len(per) else {}).get("transition_out"))
             for i, (src, (a, b)) in enumerate(zip(clip_paths, trims))]
    merged = work / "merged.mp4"
    cmd = effects.film_cmd(post_process._ffmpeg_bin(), clips, str(merged), size, edit.get("look"), crf=FILM_CRF)
    _ok(await asyncio.to_thread(_render_film, cmd), "film encode")
    if music_path:
        _ok(await asyncio.to_thread(post_process.add_music, str(merged), music_path, str(out)), "music")
    else:
        merged.replace(out)
    return str(out)


# Ambient mode (directive B14, playbook 11 §7): the reel is the clips whole, plain cuts, muted; the video is the reel
# looped under the music. The reel is the one encode; looping copies its video stream, so quality is not lost again.
REEL_FADE_S = (3.0, 4.0)   # music fade in / out (the sample fades in over its first 4s)
REEL_CLIP_S = 8.0          # an ambient clip, used whole


async def render_reel(clip_paths: list[str], out_path: str, size: str) -> str:
    """One loop of the ambient reel: every clip whole, plain cuts, no clip sound, Flow's ✦ hidden, one encode."""
    clips = [effects.ClipEdit(src, 0.0, probe_duration(src) or REEL_CLIP_S, audio=False) for src in clip_paths]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    cmd = effects.film_cmd(post_process._ffmpeg_bin(), clips, out_path, size, None, crf=FILM_CRF)
    _ok(await asyncio.to_thread(_render_film, cmd), "reel encode")
    return out_path


def loop_cmd(ffmpeg: str, reel: str, out: str, length_s: float, music: str | None) -> list[str]:
    """The reel repeated to length_s, its video stream copied (no second encode); the music, faded, as the sound."""
    args = [ffmpeg, "-y", "-stream_loop", "-1", "-i", reel]
    if music:
        fin, fout = REEL_FADE_S
        args += ["-i", music, "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k",
                 "-af", f"afade=t=in:d={fin},afade=t=out:st={max(0.0, length_s - fout):.3f}:d={fout}"]
    else:
        args += ["-map", "0:v", "-an"]
    return args + ["-t", f"{length_s:.3f}", "-c:v", "copy", "-movflags", "+faststart", out]


async def loop_reel(reel: str, out_path: str, loop_s: int | None, music: str | None) -> str:
    """The finished ambient video: as long as the music (or loop_s); with neither, the reel itself."""
    length = (probe_duration(music) if music else None) or loop_s
    if not length:
        shutil.copyfile(reel, out_path)
        return out_path
    cmd = loop_cmd(post_process._ffmpeg_bin(), reel, out_path, float(length), music)
    _ok(await asyncio.to_thread(_render_film, cmd), "reel loop")
    return out_path


def _has_audio(path: str) -> bool:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                              "-of", "csv=p=0", path], capture_output=True, text=True, timeout=30).stdout.strip()
        return bool(out)
    except (OSError, subprocess.TimeoutExpired):
        return True


async def local_clip(scene: dict, orientation: str, dest_dir: Path) -> Path:
    prefix = "vertical" if orientation == "VERTICAL" else "horizontal"
    url, media_id = scene.get(f"{prefix}_video_url"), scene.get(f"{prefix}_video_media_id")
    local = video_reviewer._local_media_path(url)
    if local:
        return local
    dest = dest_dir / f"{scene['id']}-{(media_id or 'x')[:8]}.mp4"   # one file per take, so a new take is fetched
    if dest.exists():
        return dest
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        await video_reviewer._download_video(url, dest)
    except Exception:
        await video_reviewer._download_via_get_media(media_id, dest)
    return dest


def probe_duration(path: str) -> float | None:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                             capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out) if out else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


CHAIN_HEAD_S = 0.3   # a continuing clip opens on the frame the one before ended on: drop the repeat, keep the rest


CHAIN_TAIL_HOLD_S = 2.5   # the longest still settle kept at the end of a clip that hands on to the next


def chain_trims(shots: list) -> list[list[float]]:
    """Continuous mode (directive B12, playbook 09 §7): each clip used almost whole. At a join inside a chain the cut
    lands on motion (Agent Review of Old Walt, 22/10 — joins scored 5/10): the incoming clip starts where its inherited
    hold ends, at its first movement, because Flow redraws the inherited frame a little differently (hand lifted,
    smile gone, tarp overhead) and two still frames side by side show every difference; the outgoing clip keeps at
    most CHAIN_TAIL_HOLD_S of its final still hold (two 4s holds met at each join and stalled the film)."""
    out, prev = [], None
    for i, s in enumerate(shots):
        beats = sorted(getattr(s, "actions", None) or [], key=lambda a: a.start_s)
        joined = s.continues and prev is not None and prev.order == s.order - 1
        head = 0.0
        if joined:
            first = beats[0] if beats else None
            hold = (first.end_s if first and first.kind == "hold" and first.start_s == 0
                    and first.end_s < s.duration_s / 2 else CHAIN_HEAD_S)
            head = min(max(CHAIN_HEAD_S, float(hold)), 1.5)
        end = float(s.duration_s)
        nxt = shots[i + 1] if i + 1 < len(shots) else None
        if nxt is not None and nxt.continues and nxt.order == s.order + 1 and len(beats) > 1 \
                and beats[-1].kind == "hold":
            end = min(end, float(beats[-1].start_s) + CHAIN_TAIL_HOLD_S)
        out.append([head, end])
        prev = s
    return out


def keyframe_trims(shots: list) -> list[list[float]]:
    """Keyframe mode (playbook 10 §6): a joined shot starts at 0s (on its pinned still) and a shot the next one joins
    runs to its end (on the next still); use_s seconds are kept, placed against those pinned ends."""
    out = []
    for i, s in enumerate(shots):
        dur = float(s.duration_s)
        keep = min(float(s.use_s or 3.0), dur)
        joined_in = i > 0 and s.join_in != "cut" and shots[i - 1].order == s.order - 1
        nxt = shots[i + 1] if i + 1 < len(shots) else None
        joins_out = nxt is not None and nxt.join_in != "cut" and nxt.order == s.order + 1
        if joined_in and joins_out:
            out.append([0.0, dur])
        elif joined_in:
            out.append([0.0, keep])
        elif joins_out:
            out.append([round(dur - keep, 2), dur])
        else:
            out.append([round((dur - keep) / 2, 2), round((dur + keep) / 2, 2)])
    return out


def keyframe_edit(edit: dict, shots: list) -> dict:
    """The join is inside the picture (occlusion, screen, action, whip): never an added transition there."""
    clips = [dict(c) for c in edit["clips"]]
    for i, s in enumerate(shots[1:]):
        if s.join_in != "cut" and shots[i].order == s.order - 1:
            clips[i]["transition_out"] = "cat"
    return dict(edit, clips=clips)


def chain_edit(edit: dict, shots: list) -> dict:
    """Inside a chain the join is the camera's own move: never an added transition there; between chains keep the
    chosen one."""
    clips = [dict(c) for c in edit["clips"]]
    for i, s in enumerate(shots[1:]):
        if s.continues and shots[i].order == s.order - 1:
            clips[i]["transition_out"] = "cat"
    return dict(edit, clips=clips)
