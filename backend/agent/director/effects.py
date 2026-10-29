"""Edit effects in the style of CapCut, rebuilt with plain ffmpeg filters (no CapCut assets).

Three kinds, named like the CapCut panels they were observed in (slug of the Vietnamese name):
- LOOKS        (Bộ lọc)       a colour grade for the whole film.
- CLIP_FX      (Hiệu ứng)     something that happens inside one clip.
- TRANSITIONS  (Chuyển tiếp)  how one clip hands over to the next.

Most transitions are "edge" effects: the outgoing clip ends into a colour / blur and the incoming clip starts out
of it, with no overlap (concat). Only a few need the two pictures on screen together ("overlap", xfade).
`film_cmd` turns a whole edit into ONE ffmpeg command, so the film is encoded exactly once.
"""
from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass, field
from collections.abc import Callable

logger = logging.getLogger(__name__)

FPS = 24


def slug(name: str) -> str:
    """'Nháy trắng' → 'nhay-trang': CapCut's Vietnamese names and our ids meet here."""
    s = (name or "").strip().lower().replace("đ", "d")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return "-".join("".join(c if c.isalnum() else " " for c in s).split())


# ── Bộ lọc (colour grades) ─────────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Look:
    label: str      # CapCut name it imitates
    use: str        # when to choose it
    chain: str      # ffmpeg filter chain (yuv420p in, any format out)


LOOKS: dict[str, Look] = {
    "goc": Look("Gốc", "giữ màu của Flow", ""),
    "phim-co-dien": Look("Phim cổ điển", "chuyện xưa, hoài niệm, gia đình",
                         "curves=r='0/0.07 1/0.96':g='0/0.05 1/0.93':b='0/0.12 1/0.84',eq=saturation=0.85"),
    "mv-co-dien": Look("MV cổ điển", "tình cảm, ấm áp, hơi bạc màu",
                       "curves=all='0/0.05 0.5/0.52 1/0.95',colorbalance=rs=0.05:bs=-0.06:rm=0.04:bm=-0.05,"
                       "eq=saturation=0.9"),
    "suong-mo-dien-anh": Look("Sương mờ điện ảnh", "mơ màng, buổi sáng, ký ức nhẹ",
                              "curves=all='0/0.08 0.6/0.62 1/0.96',eq=saturation=0.85,colorbalance=bs=0.04:bm=0.02"),
    "hoang-hon-phim-nhua": Look("Hoàng hôn phim nhựa", "điện ảnh teal-cam, phiêu lưu, du lịch",
                                "colorbalance=rs=-0.08:gs=-0.02:bs=0.10:rh=0.10:gh=0.02:bh=-0.10,eq=saturation=1.08"),
    "be-am-ap": Look("Be ấm áp", "ấm cúng, trong nhà, bếp, đồ ăn",
                     "colortemperature=temperature=4600,eq=saturation=0.95"),
    "anh-nen": Look("Ánh nến", "đêm ấm, lãng mạn, Giáng sinh",
                    "colortemperature=temperature=3300,curves=all='0/0.03 1/0.97'"),
    "cham-tinh-lang": Look("Chàm tĩnh lặng", "buồn, cô đơn, trầm lắng",
                           "colortemperature=temperature=8800,eq=saturation=0.82:contrast=1.03"),
    "lanh-vu-tru": Look("Lạnh vũ trụ", "đêm xanh, công nghệ, bí ẩn",
                        "colortemperature=temperature=11000,eq=contrast=1.08:saturation=1.05"),
    "thanh-pho-ve-dem": Look("Thành phố về đêm", "đêm đô thị, đèn neon",
                             "colorbalance=rs=-0.08:bs=0.14:rh=0.14:bh=-0.04,eq=contrast=1.1:saturation=1.2"),
    "anh-phim-den-trang": Look("Ánh phim đen trắng", "hồi tưởng, kịch tính",
                               "hue=s=0,eq=contrast=1.15"),
    "noir-co-dien": Look("Noir cổ điển", "trinh thám, căng thẳng",
                         "hue=s=0,curves=all='0/0 0.25/0.14 0.75/0.86 1/1'"),
    "tong-nau-u-toi": Look("Tông nâu u tối", "ký ức rất xa, ảnh cũ (sepia)",
                           "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131,"
                           "eq=contrast=0.95:brightness=-0.03"),
    "giay-phai": Look("Giấy phai", "đen trắng bạc màu, ảnh kỷ niệm",
                      "hue=s=0,curves=all='0/0.1 1/0.9'"),
}


# ── Hiệu ứng (in-clip effects) ─────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Ctx:
    u: str          # unique label prefix for this clip's graph fragments
    L: float        # clip length in seconds
    w: int
    h: int


@dataclass(frozen=True)
class Fx:
    label: str
    use: str
    make: Callable[[Ctx], str]


def _shake(c: Ctx, amp: int, start: float, end: float, speed: float = 45) -> str:
    on = f"between(t\\,{start:.3f}\\,{end:.3f})"
    return (f"crop={c.w - 2 * amp}:{c.h - 2 * amp}:x='{amp}+{amp}*sin(t*{speed})*{on}':"
            f"y='{amp}+{amp}*cos(t*{speed * 0.85:.1f})*{on}',scale={c.w}:{c.h}")


def _zoom(c: Ctx, expr: str) -> str:
    """Scale by a time expression (≥1) and crop back to the frame: push-ins and punches."""
    return (f"scale=w='{c.w}*({expr})':h='{c.h}*({expr})':eval=frame:flags=bicubic,"
            f"crop={c.w}:{c.h}")


def _glow(c: Ctx, opacity: float = 0.4, sigma: int = 22) -> str:
    return (f"format=gbrp,split[{c.u}p][{c.u}q];[{c.u}q]gblur=sigma={sigma}[{c.u}g];"
            f"[{c.u}p][{c.u}g]blend=all_mode=screen:all_opacity={opacity},format=yuv420p")


def _leak(c: Ctx, at: float, warm=(255, 150, 40)) -> str:
    """A warm light leak sweeping across the frame, peaking at second `at` (screen blend in RGB)."""
    r, g, b = warm
    shape = (f"exp(-((X-(W*(T-{at - 0.6:.3f})))^2+(Y-H*0.35)^2)/(2*(W*0.45)^2))"
             f"*exp(-((T-{at:.3f})^2)/0.18)")
    return (f"format=gbrp[{c.u}c];color=black:s=180x320:r={FPS}:d={c.L:.3f},format=rgb24,"
            f"geq=r='{r}*{shape}':g='{g}*{shape}':b='{b}*{shape}',scale={c.w}:{c.h},format=gbrp[{c.u}l];"
            f"[{c.u}c][{c.u}l]blend=all_mode=screen,format=yuv420p")


def _focus_in(c: Ctx, d: float = 0.8) -> str:
    return (f"split[{c.u}s][{c.u}b];[{c.u}b]gblur=sigma=24[{c.u}bl];"
            f"[{c.u}bl][{c.u}s]blend=all_expr='A*(1-min(T/{d}\\,1))+B*min(T/{d}\\,1)'")


CLIP_FX: dict[str, Fx] = {
    "vien-toi-nhat": Fx("Viền tối nhạt", "dồn mắt vào giữa khung, hợp mọi phim", lambda c: "vignette=PI/5"),
    "hat": Fx("Hạt", "hạt phim; đi cùng phim-co-dien / ký ức", lambda c: "noise=alls=12:allf=t"),
    "nhoe-sang": Fx("Nhòe sáng", "glow mơ màng: ký ức, giấc mơ, khoảnh khắc đẹp", _glow),
    "ro-phim": Fx("Rò phim", "vệt sáng ấm quét qua giữa clip: hoài niệm, ấm áp",
                  lambda c: _leak(c, at=c.L / 2)),
    "lay-net-mo": Fx("Lấy nét mờ", "mở clip từ nhòe sang nét: thức dậy, hồi tưởng bắt đầu",
                     lambda c: _focus_in(c)),
    "ong-kinh-zoom": Fx("Ống kính zoom", "đẩy máy chậm vào (8%) suốt clip: tăng cảm xúc",
                        lambda c: _zoom(c, f"1+0.08*t/{c.L:.3f}")),
    "thu-phong-nho": Fx("Thu phóng nhỏ", "lùi máy chậm (8% → 0): kết, buông",
                        lambda c: _zoom(c, f"1.08-0.08*t/{c.L:.3f}")),
    "lac-qua-lai": Fx("Lắc qua lại", "rung nhẹ cả clip: hồi hộp, cầm tay", lambda c: _shake(c, 8, 0, c.L, 9)),
    "dong-dat": Fx("Động đất", "rung mạnh 0.6s đầu clip: va chạm, cú sốc", lambda c: _shake(c, 26, 0, 0.6)),
    "loi-nho": Fx("Lỗi nhỏ", "lệch màu RGB chớp 0.15s mỗi 2s: công nghệ, nhiễu loạn",
                  lambda c: "rgbashift=rh=14:bh=-14:enable='lt(mod(t\\,2)\\,0.15)'"),
    "mat-mau": Fx("Mất màu", "màu rút dần thành đen trắng: mất mát, ký ức phai",
                  lambda c: f"hue=s='max(0\\,1-t/{c.L:.3f})'"),
    "trang-dan": Fx("Trắng dần", "clip tan vào trắng 1s cuối: kết phim nhẹ nhàng",
                    lambda c: f"fade=t=out:st={max(0.0, c.L - 1):.3f}:d=1:color=white"),
    "toi-dan": Fx("Tối dần", "clip tắt dần vào đen 1s cuối: kết phim",
                  lambda c: f"fade=t=out:st={max(0.0, c.L - 1):.3f}:d=1"),
    "mo-dan": Fx("Mở dần", "clip hiện dần từ đen 1s đầu: mở phim", lambda c: "fade=t=in:st=0:d=1"),
    "dong-ngang": Fx("Đóng ngang", "hai dải đen khép lại 1s cuối như màn kết",
                     lambda c: (f"drawbox=x=0:y=0:w=iw:h='ih/2*min(1\\,max(0\\,(t-{c.L - 1:.3f})))':"
                                f"color=black:t=fill,"
                                f"drawbox=x=0:y='ih-ih/2*min(1\\,max(0\\,(t-{c.L - 1:.3f})))':w=iw:h=ih:"
                                f"color=black:t=fill")),
}


# ── Chuyển tiếp (transitions) ──────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Transition:
    label: str
    use: str
    xfade: str | None = None                 # overlap transition (xfade kind); None = edge transition
    dur: float = 0.0                         # overlap length
    out: Callable[[Ctx], str] | None = None  # end of the outgoing clip
    into: Callable[[Ctx], str] | None = None # start of the incoming clip


def _fade_out(color: str, d: float):
    return lambda c: f"fade=t=out:st={max(0.0, c.L - d):.3f}:d={d}:color={color}"


def _fade_in(color: str, d: float):
    return lambda c: f"fade=t=in:st=0:d={d}:color={color}"


WARM = "0xFFD08A"
TRANSITIONS: dict[str, Transition] = {
    "cat": Transition("Cắt thẳng", "mặc định giữa các góc của cùng một nơi"),
    "nhay-trang": Transition("Nháy trắng", "nhảy thời gian, đổi không gian, mở ký ức",
                             out=_fade_out("white", 0.1), into=_fade_in("white", 0.25)),
    "chop-cat-roi": Transition("Chớp cắt rời", "chớp đen rất nhanh: dồn nhịp, căng thẳng",
                               out=_fade_out("black", 0.12), into=_fade_in("black", 0.15)),
    "bung-sang-vang": Transition("Bùng sáng vàng", "loé sáng ấm: hạnh phúc, kỷ niệm đẹp, hoàng hôn",
                                 out=_fade_out(WARM, 0.15),
                                 into=lambda c: f"fade=t=in:st=0:d=0.4:color={WARM},"
                                                + _leak(c, at=0.15)),
    "thu-phong-loe-sang": Transition("Thu phóng lóe sáng", "đẩy mạnh vào cảnh mới kèm loé trắng: bất ngờ, hành động",
                                     out=_fade_out("white", 0.08),
                                     into=lambda c: _zoom(c, "1+0.3*max(0\\,1-t/0.3)")
                                                    + ",fade=t=in:st=0:d=0.2:color=white"),
    "zoom-giat": Transition("Zoom giật", "cảnh sau bật vào từ to về đúng cỡ: nhịp nhanh, nhạc mạnh",
                            into=lambda c: _zoom(c, "1+0.3*max(0\\,1-t/0.25)")),
    "rung-trang": Transition("Rung trắng", "trắng loé + rung: va chạm, tiếng động lớn",
                             out=_fade_out("white", 0.08),
                             into=lambda c: _shake(c, 22, 0, 0.4) + ",fade=t=in:st=0:d=0.15:color=white"),
    "chop-nhiet": Transition("Chớp nhiệt", "lệch màu chớp ở chỗ cắt: glitch, công nghệ",
                             out=lambda c: f"rgbashift=rh=18:bh=-18:enable='gte(t\\,{c.L - 0.12:.3f})'",
                             into=lambda c: "rgbashift=rh=-18:bh=18:enable='lt(t\\,0.12)'"),
    "hoa-tan": Transition("Hòa tan", "hai cảnh chồng nhau: thời gian trôi chậm, cảm xúc lắng",
                          xfade="fade", dur=0.7),
    "chong-anh-mo-dan": Transition("Chồng ảnh mờ dần", "tối dần rồi hòa sang cảnh sau: chương mới, đêm xuống",
                                   xfade="fadeblack", dur=0.8),
    "phai-xam": Transition("Phai xám", "phai qua xám: từ hiện tại về ký ức", xfade="fadegrays", dur=0.8),
    "lot-ngang": Transition("Lướt ngang", "whip pan: cùng nhịp, nối hai nơi liền mạch",
                            xfade="smoothleft", dur=0.35),
    "lot-doc": Transition("Lướt dọc", "lướt lên/xuống: từ trời xuống đất, từ trên trần xuống",
                          xfade="smoothup", dur=0.35),
    "nhoe-chuyen": Transition("Nhòe chuyển", "nhòe ngang khi chuyển: chuyển động nhanh, vội",
                              xfade="hblur", dur=0.45),
    "lam-mo-pixel": Transition("Làm mờ pixel", "vỡ điểm ảnh: kỹ thuật số, game, ký ức vỡ vụn",
                               xfade="pixelize", dur=0.5),
    "mo-tron": Transition("Mở tròn", "mở từ tâm: hé lộ, bắt đầu câu chuyện", xfade="circleopen", dur=0.6),
    "khoet-ngang": Transition("Khoét ngang", "các dải ngang thay nhau: nhịp đồ hoạ, quảng cáo",
                              xfade="hrslice", dur=0.5),
}

# Words a writer may use for the same thing (English or CapCut synonyms) → our ids.
ALIASES = {
    "cut": "cat", "hard-cut": "cat", "match": "cat", "match-cut": "cat", "cat-thang": "cat",
    "flash": "nhay-trang", "white-flash": "nhay-trang", "flash-trang": "nhay-trang", "chop-trang": "nhay-trang",
    "dip-to-black": "chop-cat-roi", "flash-den": "chop-cat-roi", "chop-den": "chop-cat-roi",
    "light-leak": "bung-sang-vang", "ro-sang": "bung-sang-vang",
    "dissolve": "hoa-tan", "crossfade": "hoa-tan", "cross-dissolve": "hoa-tan",
    "fade-to-black": "chong-anh-mo-dan", "fade-black": "chong-anh-mo-dan",
    "whip": "lot-ngang", "whip-pan": "lot-ngang", "swish": "lot-ngang", "luot-ngang": "lot-ngang",
    "zoom-punch": "zoom-giat", "punch-in": "zoom-giat", "glitch": "chop-nhiet",
    "blur": "nhoe-chuyen", "pixelize": "lam-mo-pixel", "iris": "mo-tron",
    "vignette": "vien-toi-nhat", "grain": "hat", "film-grain": "hat", "glow": "nhoe-sang",
    "push-in": "ong-kinh-zoom", "shake": "lac-qua-lai", "desaturate": "mat-mau",
    "fade-out": "toi-dan", "fade-in": "mo-dan", "warm": "be-am-ap", "cold": "cham-tinh-lang",
    "vintage": "phim-co-dien", "black-and-white": "anh-phim-den-trang", "sepia": "tong-nau-u-toi",
    "teal-orange": "hoang-hon-phim-nhua",
}


def resolve(name: str | None, table: dict) -> str | None:
    """Our id for a name the writer gave (id, CapCut name, alias), or None when it is not in `table`."""
    if not name:
        return None
    s = slug(name)
    s = ALIASES.get(s, s)
    return s if s in table else None


def catalog_text() -> str:
    """The menu shown to the director: ids with when to use them."""
    def block(title, table):
        return f"{title}:\n" + "\n".join(f"- {k} ({v.label}): {v.use}" for k, v in table.items())
    return "\n\n".join([block("film_look (Bộ lọc, cả phim)", LOOKS),
                        block("edit_transition_out (Chuyển tiếp sang clip sau)", TRANSITIONS),
                        block("edit_fx (Hiệu ứng trong clip, tối đa 2)", CLIP_FX)])


# ── One command for the whole film ─────────────────────────────────────────────────────────────────────────────
@dataclass
class ClipEdit:
    src: str
    start: float
    end: float
    audio: bool = True
    fx: list[str] = field(default_factory=list)
    transition_out: str | None = None

    @property
    def length(self) -> float:
        return round(self.end - self.start, 3)


def plan_transitions(clips: list[ClipEdit]) -> list[tuple[str, float]]:
    """(id, overlap seconds) for every join; unknown names become a cut, overlaps fit both clips."""
    joins = []
    for a, b in zip(clips, clips[1:]):
        tid = resolve(a.transition_out, TRANSITIONS) or "cat"
        if a.transition_out and tid == "cat" and slug(a.transition_out) not in ("cat", "cut"):
            logger.info("unknown transition %r → cut", a.transition_out)
        t = TRANSITIONS[tid]
        d = min(t.dur, 0.4 * min(a.length, b.length)) if t.xfade else 0.0
        joins.append((tid, round(d, 3)))
    return joins


# Flow stamps a ✦ in the bottom-right corner of every picture it makes, and r2v clips copy it from their reference
# pictures (22/10 Old Walt SH04; 24/10 both ambient trial clips). Measured on 1280x720 clips: centre 120px from the
# right and bottom edges, ~50px wide. The user chose to hide it in the edit (24/10), for every film mode.
MARK_INSET = 120        # px from the right/bottom edge to the mark's centre, on a 720p clip
MARK_BOX = 64           # px square covered, on a 720p clip


def unmark(w: int, h: int) -> str:
    """delogo over Flow's ✦, for a clip already scaled to w x h (a 16:9 or 9:16 Flow clip fills the frame)."""
    k = min(w, h) / 720
    box, inset = round(MARK_BOX * k), round(MARK_INSET * k)
    return f"delogo=x={w - inset - box // 2}:y={h - inset - box // 2}:w={box}:h={box}"


def film_cmd(ffmpeg: str, clips: list[ClipEdit], out: str, size: str, look: str | None = None,
             crf: int = 16) -> list[str]:
    """Trim, scale, hide Flow's ✦, grade, add effects and transitions, encode once."""
    w, h = (int(x) for x in size.split("x"))
    look_id = resolve(look, LOOKS) or "goc"
    grade = LOOKS[look_id].chain
    joins = plan_transitions(clips)
    args = [ffmpeg, "-y"]
    for c in clips:
        args += ["-ss", f"{c.start:.3f}", "-t", f"{c.length:.3f}", "-i", c.src]
    g = []
    for i, c in enumerate(clips):
        steps = [f"setpts=PTS-STARTPTS,scale={w}:{h}:flags=lanczos:force_original_aspect_ratio=decrease,"
                 f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS},format=yuv420p,{unmark(w, h)}"]
        if grade:
            steps.append(grade)
        for k, name in enumerate(c.fx[:2]):
            fid = resolve(name, CLIP_FX)
            if fid:
                steps.append(CLIP_FX[fid].make(Ctx(u=f"c{i}f{k}", L=c.length, w=w, h=h)))
        if i > 0 and TRANSITIONS[joins[i - 1][0]].into:
            steps.append(TRANSITIONS[joins[i - 1][0]].into(Ctx(u=f"c{i}ti", L=c.length, w=w, h=h)))
        if i < len(clips) - 1 and TRANSITIONS[joins[i][0]].out:
            steps.append(TRANSITIONS[joins[i][0]].out(Ctx(u=f"c{i}to", L=c.length, w=w, h=h)))
        steps.append("format=yuv420p,setsar=1,settb=AVTB")
        g.append(f"[{i}:v]" + ",".join(steps) + f"[v{i}]")
        if c.audio:
            g.append(f"[{i}:a]asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,"
                     f"apad,atrim=0:{c.length:.3f}[a{i}]")
        else:
            g.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{c.length:.3f}[a{i}]")
    v, a, acc = "v0", "a0", clips[0].length
    for i, (tid, d) in enumerate(joins, start=1):
        t = TRANSITIONS[tid]
        if t.xfade and d > 0:
            g.append(f"[{v}][v{i}]xfade=transition={t.xfade}:duration={d}:offset={acc - d:.3f}[x{i}]")
            g.append(f"[{a}][a{i}]acrossfade=d={d}[y{i}]")
            acc += clips[i].length - d
        else:
            g.append(f"[{v}][v{i}]concat=n=2:v=1:a=0[x{i}]")
            g.append(f"[{a}][a{i}]concat=n=2:v=0:a=1[y{i}]")
            acc += clips[i].length
        v, a = f"x{i}", f"y{i}"
    g.append(f"[{v}]format=yuv420p[vout]")
    return args + ["-filter_complex", ";".join(g), "-map", "[vout]", "-map", f"[{a}]",
                   "-r", str(FPS), "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-profile:v", "high",
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                   "-movflags", "+faststart", out]
