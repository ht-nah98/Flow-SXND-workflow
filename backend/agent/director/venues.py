"""Venues for the ambient mode (directive B14, playbook 11 §2): the kinds of live performance the user can pick on the
idea. One video = one venue, one look. The writer turns the chosen venue (plus the user's own words) into the one
location picture; the DP writes the look into the film's style_block. The canvas lists them from GET /venues."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Venue:
    id: str
    name: str        # Vietnamese, shown on the 💡 node
    explain: str     # Vietnamese: what the video looks like, so the user knows what they pick (directive G2)
    place: str       # English: the venue as the location picture shows it
    look: str        # English: the palette and light every clip shares
    details: str     # English: what the detail and people shots show


VENUES: dict[str, Venue] = {v.id: v for v in [
    Venue(id="worship-arena", name="Worship · sân vận động",
          explain="Đêm nhạc thờ phượng trong sân vận động khổng lồ: biển người, đèn điện thoại, tay giơ lên (như mẫu Heaven Sound).",
          place="a vast indoor arena with many curved tiers of seats, a distant stage with large LED screens and a lighting truss",
          look="deep purple and magenta stage wash, cool white spotlight beams from the truss, thousands of phone lights in the stands, light haze",
          details="open palms, a hand on the chest, eyes closed, slow clapping, a single raised hand against the crowd"),
    Venue(id="church-choir", name="Nhà thờ · hợp xướng",
          explain="Buổi hát thánh ca trong nhà thờ cổ: vòm cao, ánh nến, cửa kính màu, dàn hợp xướng nhìn từ sau lưng.",
          place="a tall stone church nave with wooden pews, stained-glass windows and a choir loft",
          look="warm candlelight with coloured light beams through stained glass, soft dust in the air",
          details="candles, open hymn books, folded hands, the choir seen from behind"),
    Venue(id="jazz-club", name="Quán jazz",
          explain="Đêm jazz trong quán nhỏ: bàn tròn, khói mờ, ánh hổ phách, nhạc công ngược sáng.",
          place="a small intimate jazz club with round tables, table lamps and a low stage",
          look="amber lamp light, soft smoke haze, deep shadows, brass highlights",
          details="a glass on a table, piano keys, the glint of a saxophone, listeners nodding slowly"),
    Venue(id="symphony-hall", name="Dàn nhạc giao hưởng",
          explain="Buổi hoà nhạc giao hưởng trong khán phòng gỗ: sân khấu sáng, khán phòng tối, nhạc trưởng nhìn từ sau lưng.",
          place="a wooden concert hall with balconies and a brightly lit orchestra stage",
          look="warm golden stage light, dark auditorium, polished wood reflections",
          details="violin scrolls and bows, sheet music stands, the conductor seen from behind, listeners in the dark"),
    Venue(id="outdoor-acoustic", name="Acoustic ngoài trời",
          explain="Buổi diễn acoustic lúc hoàng hôn trên bãi cỏ hoặc bờ hồ: dây đèn, người ngồi trên chăn.",
          place="a lawn by a lake at sunset with string lights over a small wooden stage",
          look="golden-hour orange fading to blue, warm string-light bokeh",
          details="an acoustic guitar, people sitting on picnic blankets, string lights, swaying heads"),
    Venue(id="rock-festival", name="Lễ hội rock",
          explain="Đêm lễ hội rock ngoài trời: sân khấu lớn, đèn quét đỏ–xanh, pháo giấy, tay giơ cao.",
          place="a huge open-air festival stage at night in front of a field full of people",
          look="red and blue sweeping beams, smoke, confetti in the light",
          details="raised hands, shoulders of the people in front, confetti falling through the beams"),
]}


def get(venue_id: str | None) -> Venue | None:
    return VENUES.get(venue_id or "")


def catalog() -> list[dict]:
    return [asdict(v) for v in VENUES.values()]
