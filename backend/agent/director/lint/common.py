"""Shared lint pieces: the issue type, shared rules and helpers used by several film modes. Split from lint.py on 23/10 (code moved, not changed)."""
import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LintIssue:
    rule: str
    shot_id: str | None
    message: str
    severity: Literal["error", "warning"] = "error"


def errors(issues: list[LintIssue]) -> list[LintIssue]:
    return [i for i in issues if i.severity == "error"]


_STOP = {"with", "from", "into", "onto", "that", "this", "their", "there", "slowly", "while", "over", "under"}


def mentions(element: str, text: str) -> bool:
    """The bridge element is named in the prompt: its content words (4+ letters) all appear, in any order/inflection
    prefix ("rubbing" ~ "rubs" is not matched, so keep the noun phrase short — the director writes it so)."""
    words = [w for w in re.findall(r"[^\W\d_]+", element.lower()) if len(w) > 3 and w not in _STOP]
    low = text.lower()
    return all(w[:5] in low for w in words) if words else element.lower() in low


def _norm_period(p: str) -> str:
    return re.sub(r"\s+", " ", (p or "present").strip().lower())
MAX_ACTION_WORDS = 14
_CAMERA_OBJECT = re.compile(r"\btripod|\bcamera (?:is |was )?(?:placed|positioned|set up|mounted|sits|stands|rests)\b"
                            r"|\bon an? (?:slider|gimbal|dolly|crane)\b|\bcamera operator|\bfilm crew|\bboom mic"
                            r"|máy quay (?:đặt|dựng)|chân máy", re.I)
# 22/10 Old Walt SH06: "the print … picture turned toward the lens … sharp in the foreground" → Flow drew sharp
# photoreal soldiers' faces inside the photo and its output filter deleted the clip twice (MEDIA_REMOVED,
# NO_MEDIA_CREATED). SH02, same references, passed: "a small faded grey square, too soft to read; no faces readable".
_PHOTO_PROP = re.compile(r"photo|portrait|picture|print|snapshot|polaroid|ảnh", re.I)
_PHOTO_SHOWN = re.compile(r"(?:picture|image|faces?|front)\b[^.]{0,40}\b(?:toward|towards|facing|to) (?:the )?"
                          r"(?:lens|camera|viewer)|\bfaces? (?:are |is )?(?:visible|readable|clear|sharp)", re.I)
_PHOTO_SAFE = re.compile(r"\baway\b|\bback\b|\bunreadable|not readable|too soft|no faces?|blur", re.I)


def _photo_faces(vp: str, props: set[str]) -> str | None:
    """The sentence that shows a photograph's picture to the lens, if any (the model then invents faces in it)."""
    names = [n.lower() for n in props if _PHOTO_PROP.search(n)]
    if not names:
        return None
    for sent in re.split(r"(?<=[.!?\n])", vp):
        low = sent.lower()
        if any(n in low for n in names + ["the print", "the photo"]) and _PHOTO_SHOWN.search(sent) \
                and not _PHOTO_SAFE.search(sent):
            return sent.strip()
    return None


# 22/10 Leo Marsh (keyframe test): every clip that looked like a real TV news broadcast — a photoreal anchor at a
# news desk, "ON AIR" / "LIVE" lettering, a TV airing a person — was refused by Flow ("could put a reputation at risk
# or misrepresent current events"; our side only sees NO_MEDIA_CREATED), 4 clips × 3 tries. The same story passed once
# the studio became a plain white room with a cartoon sun and no lettering.
_NEWS_LOOK = re.compile(r"\bon[ -]air\b|\blive (?:in|now|on|broadcast|feed|report)|\bbreaking news|\bnews ?(?:anchor|desk|"
                        r"report|broadcast|cast|room|ticker|banner)|\banchor desk|\bnewscast|\bbroadcast|\breporter|"
                        r"\bbản tin|\bphát sóng|\blên sóng", re.I)


def _news_look(text: str) -> str | None:
    """The words that make a clip read as a real news broadcast, if any (Flow refuses those)."""
    m = _NEWS_LOOK.search(text or "")
    return m.group(0) if m else None


NEWS_LOOK_MSG = ("reads as a real TV news broadcast: Flow refuses it as \"could misrepresent current events\" "
                 "(NO_MEDIA_CREATED). Drop news cues — no ON AIR / LIVE lettering, no news desk, no TV airing a person; "
                 "use a plain studio with a cartoon or abstract screen")
_COMPOUND = re.compile(r"\bthen\b|\brồi\b|\bsau đó\b|;")


def _words(text: str) -> str:
    """Lower-case words only, so a spoken line matches whatever quotes or punctuation surround it."""
    return " ".join(re.findall(r"\w+", text.lower()))
# (2) Flat things cannot be flipped or slid out: SH01 photo "slides out of the pocket" just appeared; SH02 "turns it
#     face-up" was lifted to the lens and put back; SH06 flip swapped the object. Start the object in the state needed.
_FLIP = re.compile(r"\b(?:turns?|turning|flips?|flipping)\b[^.]{0,30}\b(?:over|face[- ]?(?:up|down)|around)\b"
                   r"|\bslides? out of\b|\bpulls? (?:it )?out of (?:the|a|its) (?:pocket|sleeve|envelope)", re.I)
# (3) "An unseen photographer" / "toward the camera": the actors look straight into the lens (SH03, SH04).
_LENS_GAZE = re.compile(r"\bphotographer\b|\b(?:looks?|looking|glances?|grins?|smiles?|stares?)\b[^.]{0,25}\b(?:at|into|toward|towards) "
                        r"(?:the )?(?:lens|camera)\b", re.I)
