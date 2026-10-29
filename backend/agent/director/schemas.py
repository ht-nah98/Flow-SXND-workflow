"""Stage outputs of the AI Director (spec §3). Claude must return exactly these shapes."""
import json
from typing import Literal

from pydantic import BaseModel, Field

Duration = Literal[4, 6, 8, 10]
EntityKind = Literal["character", "location", "visual_asset"]


class IdeaImage(BaseModel):
    """A picture the user attached to their idea, as the producer understood it."""
    file: str                       # absolute path, exactly as given in the input
    use: Literal["character", "location", "visual_asset", "mood"]
    name: str | None = None      # for character/location/visual_asset: the cast name it becomes
    description: str


class BriefAnalysis(BaseModel):
    logline: str
    genre: str
    tone: str
    target_s: int = Field(ge=15, le=300)
    orientation: Literal["HORIZONTAL", "VERTICAL"]
    material: str = "realistic"
    language: str = "en"   # directive B4: English films unless the user asks for Vietnamese
    images: list[IdeaImage] = []
    # Spoken audio the idea asks for: "none" (silent film), "voiceover" (an off-screen narrator) or
    # "dialogue" (characters speak on camera). Omni Flash renders the voice inside each clip.
    voice: Literal["none", "voiceover", "dialogue"] = "none"
    voice_style: str | None = None   # one fixed Vietnamese description of the voice, reused in every clip
    # The user's choice on the idea (directive B9), copied in by the pipeline: faithful | balanced | bold.
    creativity: Literal["faithful", "balanced", "bold"] = "balanced"
    style_pack: str | None = None    # styles.PACKS id chosen on the idea; None = the director picks the look
    # Directive B12 (21/10, playbook 09): "continuous" = each clip opens on the previous clip's last frame and the
    # camera carries the transition inside the clip; "cut" = separate clips trimmed and joined in the edit.
    # Old runs without the field were made by the cut rules, so a missing film_mode still reads as "cut"; new ideas
    # default to "continuous" (RunCreate, directive B12 repeated 24/10). "ambient" = no story, one venue (B14, 11).
    film_mode: Literal["continuous", "cut", "keyframe", "ambient"] = "cut"
    venue: str | None = None        # ambient: venues.VENUES id
    reel_s: int | None = None       # ambient: length of the reel that loops (60–120s)
    loop_s: int | None = None       # ambient: length of the looped final video; None = the music's length


class CastMember(BaseModel):
    name: str
    entity_type: EntityKind
    description: str
    continuity_lock: str
    image_prompt: str
    provided_image: str | None = None   # the user's own picture becomes the reference (no generation)
    # Characters (SciCloud sample, 19/10): who they are, not only how they look.
    personality: str = ""   # Vietnamese: temperament and their own way of showing feeling (contrast with the others)
    signature: str = ""     # English: a recurring gesture or habit the camera can show ("tucks hair behind her ear")


class Sequence(BaseModel):
    id: str
    title: str
    act: Literal[1, 2, 3]
    purpose: str
    start_s: int | None = None   # where it sits in the finished film (approximate, directive E1b)
    end_s: int | None = None


class Hook(BaseModel):
    """A moment that keeps the viewer watching (SciCloud sample: one every 25–30s on short-video platforms)."""
    at_s: int                    # approximate second in the film
    beat_id: str
    moment: str                  # Vietnamese: the line or image that lands (quote a voice line if there is one)


class Beat(BaseModel):
    id: str
    sequence_id: str
    summary: str
    emotion: str
    voice_line: str | None = None   # what is said during this beat (brief.voice != "none")


class SourcePart(BaseModel):
    """One part of the user's own idea (an act, scene, event, line) and where the script keeps it."""
    part: str                    # the user's part in a few words, e.g. "Cảnh 1 — cuộc gọi từ bệnh viện"
    beats: list[str] = []        # beat ids that show it
    kept: Literal["full", "compressed", "dropped"] = "full"
    note: str = ""               # how it was compressed, or why it was dropped (Vietnamese, the user reads it)


class Story(BaseModel):
    # The spine, decided before any scene (playbook 01): what happens and why, what it means, what the viewer gets.
    story_line: str = ""       # who wants what, what stands in the way, the choice, the price — cause and effect
    message: str = ""          # one sentence: what the film says about people / life
    viewer_value: str = ""     # what the viewer takes away: emotion, a lesson, laughter, curiosity, information
    rule_and_cost: str = ""    # the magic / temptation's rule and its visible, growing price (empty if none)
    # Adaptation of the user's idea: every part of it, mapped to beats. The idea is the source story, not a prompt.
    source_map: list[SourcePart] = []
    notes_for_user: list[str] = []   # Vietnamese: what the user should decide (length too short, voice off, ...)
    # The director's intent, in Vietnamese: the anti-cliché choice, the structure and why, the title line, the music arc.
    director_notes: list[str] = []
    hooks: list[Hook] = []           # retention moments spread through the film
    synopsis: str
    sequences: list[Sequence]
    beats: list[Beat]
    cast: list[CastMember]


class Action(BaseModel):
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    what: str
    # Continuous mode (playbook 09): a beat is a physical "action" (counted against the Omni Flash limits), a "hold"
    # of the inherited frame, a "camera" move, or a "reaction" (a look, a smile, a laugh). `who` = the cast name.
    kind: Literal["action", "hold", "camera", "reaction"] = "action"
    who: str = ""


class InShotTransition(BaseModel):
    start_s: float = Field(ge=0)
    technique: str
    from_frame: str
    to_frame: str


class Bridge(BaseModel):
    """Directive B7/B11 (19/10): a cut to another time is carried by one thing seen in both shots — the previous shot
    ends on it, this one opens on it (a ringing phone picked up by young Daniel → old Daniel picks up the same phone)."""
    element: str     # English, the concrete object / sound / gesture, written the same way in both prompts
    outgoing: str    # how the previous shot ends on it
    incoming: str    # how this shot opens on it


class Handoff(BaseModel):
    """Continuous mode (directive B12): inside this clip the camera hands the viewer's attention to the next shot —
    following a voice, an eyeline, a person walking, a foreground object sweeping the lens, or a light blooming."""
    motive: Literal["voice", "eyeline", "follow", "occlusion", "light"]
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    what: str        # English: the cue and the camera move ("mother calls off-screen; camera glides down the stairwell")
    to: str          # English: who / what the attention lands on — the next shot opens there


class Shot(BaseModel):
    id: str
    beat_id: str
    order: int = Field(ge=1)
    duration_s: Duration
    idea: str
    story_beat: str
    cast: list[str]
    mode: Literal["i2v", "r2v"]
    mode_reason: str
    actions: list[Action]
    commands: list[str]
    stable_open_s: float = Field(ge=0)
    transition: InShotTransition | None = None
    edit_transition_out: str | None = None   # effects.TRANSITIONS id (CapCut-style), "cat" = plain cut
    edit_fx: list[str] = Field(default_factory=list)   # effects.CLIP_FX ids, at most 2
    voice_line: str | None = None   # the exact words spoken in this clip, if any
    period: str = "present"            # story time of the shot: "present", "past", "last winter", ...
    bridge: Bridge | None = None    # required when period differs from the previous shot (lint time_bridge)
    props: list[str] = Field(default_factory=list)   # each visible prop: count, colour, holder, start → end state
    # Continuous mode (playbook 09): opens on the previous shot's last frame; hands off inside the clip; ends on a
    # frame the next shot can open from. `actions` are then the 4–7 timed beats of one camera journey.
    continues: bool = False
    handoff: Handoff | None = None
    final_frame: str = ""          # English: the FINAL FRAME CONTRACT — who is where, looking where, holding what
    # Keyframe mode (playbook 10, directive B13): the shot opens on a pinned still (`keyframe`, generated from the cast
    # pictures). When the next shot joins (its join_in is not "cut"), this clip ends exactly on the next keyframe.
    keyframe: str = ""             # English image prompt of the opening still: who, where, pose, framing, light
    join_in: Literal["cut", "occlusion", "screen", "action", "whip"] = "cut"   # how the shot before leads into it
    use_s: float | None = None  # seconds of this shot kept in the film (0.8–5); placed by the edit
    # Ambient mode (playbook 11 §3): which of the rotating shot kinds this is — wide / people / detail / stage.
    kind: Literal["", "wide", "people", "detail", "stage"] = ""


class ShotList(BaseModel):
    shots: list[Shot]
    film_look: str | None = None   # effects.LOOKS id: one colour grade for the whole film


class ShotPrompt(BaseModel):
    shot_id: str
    video_prompt: str
    keyframe_prompt: str | None = None
    end_frame: str
    avoid: str = ""        # continuous mode: this clip's own Avoid items, added after the film's avoid_block


class ShotPrompts(BaseModel):
    prompts: list[ShotPrompt]
    # Continuous mode (playbook 09 §4): written once for the whole film and appended to every prompt by the pipeline,
    # so the look and the Avoid list are word-for-word the same in every clip.
    style_block: str = ""
    avoid_block: str = ""


class EditorFix(BaseModel):
    target_stage: Literal["STORY", "SHOTLIST", "PROMPTS"]
    shot_id: str | None = None
    issue: str


class EditorReport(BaseModel):
    score: int = Field(ge=0, le=100)
    checklist: dict[str, bool]
    fixes: list[EditorFix]


class QcItem(BaseModel):
    shot_id: str
    verdict: Literal["PASS", "FAIL"]
    issues: list[str]
    trim_in_s: float = Field(ge=0)
    trim_out_s: float = Field(gt=0)


class QcReport(BaseModel):
    items: list[QcItem]


class LayerScore(BaseModel):
    """Agent Review: one of the four layers, scored 0–10."""
    layer: Literal["story", "clips", "continuity", "edit"]
    score: int = Field(ge=0, le=10)
    note: str                       # Vietnamese, one line: why this score


class ReviewFinding(BaseModel):
    """One problem seen in the film, with its cause and the fix it calls for. Text in Vietnamese except `rule`."""
    layer: Literal["story", "clips", "continuity", "edit"]
    severity: Literal["CRITICAL", "HIGH", "MINOR"]
    scene: int | None = None        # 1-based clip number in the film; a seam names the earlier clip
    shot_id: str | None = None
    clip_t: float | None = None     # seconds inside that clip where it shows
    title: str
    evidence: str                   # what is seen, and on which sheet/frame
    cause: Literal["prompt", "asset", "blocking", "script", "edit", "model_limit", "policy", "other"]
    cause_detail: str
    fix: str                        # the concrete change proposed
    action: Literal["rewrite_prompt", "regen_video", "add_asset", "revise_script", "edit_cut", "add_lesson", "none"]
    rule: str | None = None         # English rule for the playbook when the cause would repeat in other films


class FilmReview(BaseModel):
    summary: str
    strengths: list[str] = []
    scores: list[LayerScore]
    findings: list[ReviewFinding]


class AssistChange(BaseModel):
    """One proposed edit to a node the user selected; the user applies it, nothing changes by itself."""
    kind: Literal["scene", "character"]
    id: str
    field: Literal["video_prompt", "prompt", "description", "image_prompt", "name"]
    value: str
    why: str = ""          # Vietnamese, one line


class AssistReply(BaseModel):
    answer: str                         # Vietnamese: what was done / the answer to a question
    changes: list[AssistChange] = []


class LessonDraft(BaseModel):
    scope: Literal["story", "shotlist", "prompt", "omni_flash", "edit"]
    rule: str
    existing_id: str | None = None      # set to add evidence to an existing lesson
    evidence: list[dict] = []              # [{"shot_id": ..., "issue": ...}]


class Retro(BaseModel):
    lessons: list[LessonDraft]


class SampleShot(BaseModel):
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    content: str            # what happens, in Vietnamese
    framing: str            # shot size
    angle: str              # camera position
    movement: str           # camera movement
    transition_in: str      # how this shot starts: cut, flash, light leak, match cut, whip…
    look: str               # light, colour, effects


class SampleTechnique(BaseModel):
    name: str                                                          # short Vietnamese name
    scope: Literal["story", "shotlist", "prompt", "omni_flash", "edit"]
    rule: str               # an instruction the director can follow next time, in Vietnamese
    how: str                # how to make it: Vietnamese prompt wording for Flow, or the edit/ffmpeg step
    example: str            # where it happens in the sample, with times


class SampleAnalysis(BaseModel):
    title: str
    summary: str            # what the video is and why it works, Vietnamese
    structure: str          # the story/edit structure: acts, rhythm, average shot length
    shots: list[SampleShot]
    techniques: list[SampleTechnique]


def json_schema(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema())
