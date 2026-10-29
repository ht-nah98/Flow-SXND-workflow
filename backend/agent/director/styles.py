"""Style packs (learned from the gonghaosnail skill library, 19/10): one look for the whole film.
Each pack = core rules that never change (light, palette, lens, texture), variables the story may change, the usual
deviations and how to correct them, and the edit grade. The writer, director and DP all read the chosen pack; the
DP writes its `marker` into every prompt's lighting line (machine-checked)."""
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class StylePack:
    id: str
    name: str                 # Vietnamese, shown on the 💡 node
    suits: str                # Vietnamese: what kind of film it fits
    core: tuple[str, ...]     # English, fixed in every prompt and reference image
    variables: tuple[str, ...]  # English: what may change from clip to clip
    deviations: tuple[str, ...]  # English: "if X happens → write Y"
    marker: str               # English phrase every video prompt's lighting line must contain
    film_look: str            # effects.LOOKS id for the edit
    sample: str = ""          # where the look was learned
    extra: dict = field(default_factory=dict)


PACKS: dict[str, StylePack] = {p.id: p for p in [
    StylePack(
        id="natural-youth", name="Thanh xuân · nắng tự nhiên", sample="SciCloud 《三分心动》, skill 青春情愫·自然光电影",
        suits="học đường, tình cảm nhẹ, tuổi trẻ, vlog",
        core=("soft natural daylight, slightly overexposed highlights", "fresh cyan-green and cream palette",
              "35mm lens, shallow depth of field, gentle film grain", "subtle, unstaged character movement"),
        variables=("time of day (morning, noon, golden hour)", "place (court, classroom, campus path)", "wardrobe"),
        deviations=("skin looks plastic → add 'natural skin texture, no beauty filter'",
                    "colours too saturated → add 'muted, airy colours'"),
        marker="soft natural daylight", film_look="be-am-ap"),
    StylePack(
        id="warm-indie", name="Ấm áp · MV indie", sample="FMV Bánh kem & tình yêu",
        suits="tình cảm, gia đình, ký ức đẹp, quảng cáo ấm",
        core=("warm golden window light with floating dust", "honey and cream palette, soft contrast",
              "handheld oneshot with gentle natural shake", "indie / lofi music-video feel"),
        variables=("night version: lamp light instead of sun", "rain on the window for sad beats"),
        deviations=("image turns too yellow → add 'true colours, no yellow cast'",
                    "camera too steady → add 'handheld, gentle natural shake'"),
        marker="warm golden", film_look="mv-co-dien"),
    StylePack(
        id="feature-animation", name="Hoạt hình 3D điện ảnh", sample="Trailer BOTTOMLESS",
        suits="ngụ ngôn, phiêu lưu, trẻ em, phép màu",
        core=("feature animation film still quality", "volumetric light and rim light, rich contrast",
              "cinematic lens, shallow depth of field", "expressive acting with anticipation and weight"),
        variables=("palette per act (warm poverty → night blue → gold → storm grey)", "scale of the world"),
        deviations=("looks like a toy render → add 'feature film lighting, detailed textures'",
                    "faces drift between clips → name the character sheet and repeat key features"),
        marker="volumetric light", film_look="goc"),
    StylePack(
        id="southern-nostalgia", name="Hoài niệm · phim 35mm", sample="Daniel (Christian Blues)",
        suits="mất mát, chữa lành, quá khứ – hiện tại, gia đình",
        core=("35mm film grain, gentle halation", "past: warm tungsten and golden sun; present: cold blue-grey",
              "practical lights only (lamps, windows, porch bulbs)", "slow, patient camera"),
        variables=("past vs present grade", "season and weather", "interior vs porch"),
        deviations=("past and present look the same → write the warm/cold contrast in Lighting & color",
                    "too clean and digital → add '35mm film grain, slight halation'"),
        marker="35mm film grain", film_look="hoang-hon-phim-nhua"),
    StylePack(
        id="rain-noir", name="Đêm mưa · điện ảnh lạnh", sample="mẫu cảnh đêm (thư viện skill, phim ngắn)",
        suits="hồi hộp, cô đơn, thành phố, bí ẩn",
        core=("night rain, wet reflective streets", "teal and sodium-orange palette, deep blacks",
              "anamorphic lens, light streaks", "low-key light from practicals and neon"),
        variables=("indoor vs street", "rain intensity"),
        deviations=("image too dark to read → add 'faces lit by a practical source'",
                    "rain looks fake → add 'real rain streaks catching the light'"),
        marker="night rain", film_look="thanh-pho-ve-dem"),
    StylePack(
        id="ink-minimal", name="Thuỷ mặc · tối giản", sample="skill 白壁水墨·留白电影",
        suits="cổ trang, thiền, kiến trúc, thơ",
        core=("white lime walls, ink-grey clothing, black wood", "large negative space, restrained composition",
              "soft overcast light", "muted ink palette with one accent colour"),
        variables=("accent colour", "season (snow, mist, bare branches)"),
        deviations=("frame too busy → add 'large empty space, one subject'",
                    "colours too vivid → add 'desaturated ink tones'"),
        marker="negative space", film_look="giay-phai"),
]}


def get(pack_id: str | None) -> StylePack | None:
    return PACKS.get(pack_id or "")


def as_payload(pack_id: str | None) -> dict | None:
    """What the writer, director and DP receive as `style_pack`."""
    p = get(pack_id)
    return {k: v for k, v in asdict(p).items() if k not in ("extra",)} if p else None


def catalog() -> list[dict]:
    return [{"id": p.id, "name": p.name, "suits": p.suits, "core": list(p.core)} for p in PACKS.values()]
