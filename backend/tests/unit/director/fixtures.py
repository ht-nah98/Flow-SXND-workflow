"""Shots hand-translated from the user's PROMPT FMV doc (prompts 1, 2, 3, 6, 9)."""
from agent.director.schemas import (Action, Hook, Beat, CastMember, Sequence, Shot, ShotList, ShotPrompt,
                                    ShotPrompts, Story)

GIRL, BOY, KITCHEN = "Mai", "Nam", "Rustic Kitchen"


def fmv_story() -> Story:
    return Story(
        story_line="Two young lovers bake together, but he puts work first, so she leaves and he bakes alone.",
        message="Love fades when we stop making time for it.",
        viewer_value="A bittersweet ache and a nudge to call someone you love.",
        synopsis="Two young lovers bake a cake together, then break up.",
        director_notes=["Không kể chia tay bằng cãi vã: kể bằng chiếc bánh làm chung rồi làm một mình.",
                        "Hai màn đối xứng cùng một căn bếp: ấm áp ↔ lạnh."],
        hooks=[Hook(at_s=8, beat_id="b1", moment="vệt bột trên má")],
        sequences=[Sequence(id="sq1", title="Baking", act=1, purpose="joy"),
                   Sequence(id="sq2", title="Alone", act=3, purpose="loss")],
        beats=[Beat(id="b1", sequence_id="sq1", summary="baking together", emotion="joy"),
               Beat(id="b2", sequence_id="sq2", summary="he cries alone", emotion="grief")],
        cast=[CastMember(name=GIRL, entity_type="character", description="young woman", continuity_lock="cream apron",
                         image_prompt="portrait of Mai"),
              CastMember(name=BOY, entity_type="character", description="young man", continuity_lock="blue shirt",
                         image_prompt="portrait of Nam"),
              CastMember(name=KITCHEN, entity_type="location", description="rustic wooden kitchen",
                         continuity_lock="window on the left", image_prompt="rustic kitchen")])


def _shot(**kw) -> Shot:
    base = dict(beat_id="b1", mode="r2v", mode_reason="performance-driven", stable_open_s=0,
                cast=[GIRL, BOY, KITCHEN], commands=["/medium-shot", "/handheld"], idea="baking together",
                story_beat="They bake together.", edit_transition_out="cut")
    base.update(kw)
    return Shot(**base)


def fmv_shotlist() -> ShotList:
    return ShotList(shots=[
        # FMV 1 — oneshot opening: one idea, 2 actions, slow handheld pan → valid
        _shot(id="s1", order=1, duration_s=10, actions=[Action(start_s=0, end_s=6, what="mix batter together"),
                                                        Action(start_s=6, end_s=10, what="look at each other and laugh")]),
        # FMV 3 — POV from inside the oven → valid
        _shot(id="s2", order=2, duration_s=10, commands=["/object-pov", "/static"],
              actions=[Action(start_s=0, end_s=5, what="he takes the sponge cake out"),
                       Action(start_s=5, end_s=10, what="she peeks over his shoulder")]),
        # FMV 9 — floor-level low angle, he cries alone → valid
        _shot(id="s3", order=3, beat_id="b2", duration_s=10, cast=[BOY, KITCHEN],
              commands=["/low-angle", "/ground-level", "/push-in"],
              actions=[Action(start_s=0, end_s=6, what="he sits collapsed, crying silently"),
                       Action(start_s=6, end_s=10, what="lightning flash makes him flinch")]),
    ])


def overloaded_fmv_shots() -> list[Shot]:
    """FMV 2 (3 actions) and FMV 6 (4 actions) kept at 10s — must fail the ≤2-actions rule."""
    return [
        _shot(id="x2", order=1, duration_s=10, commands=["/closeup", "/handheld"],
              actions=[Action(start_s=0, end_s=4, what="she stirs batter"),
                       Action(start_s=4, end_s=6, what="he appears behind her"),
                       Action(start_s=6, end_s=10, what="he wipes flour on her cheek, both laugh")]),
        _shot(id="x6", order=2, duration_s=10, cast=[GIRL, KITCHEN], commands=["/pov", "/handheld", "/push-in"],
              actions=[Action(start_s=0, end_s=3, what="she runs up the stairs"),
                       Action(start_s=3, end_s=5, what="she turns and waves"),
                       Action(start_s=5, end_s=8, what="camera closes in"),
                       Action(start_s=8, end_s=10, what="she kisses the lens")]),
    ]


def fmv_prompts() -> ShotPrompts:
    """Prompts in the FMV template (playbook 03)."""
    def p(sid, cast=f"{GIRL}, {BOY}, {KITCHEN}", people=f"{GIRL} và {BOY}"):
        return ShotPrompt(shot_id=sid, end_frame="hai khuôn mặt ở giữa khung", video_prompt=(
            f"Ảnh tham chiếu: {cast}\n"
            f"Nhân vật & trang phục: Giữ nguyên đúng như ảnh tham chiếu đính kèm ({people}, ngoại hình và trang phục không thay đổi).\n"
            f"Bối cảnh: {KITCHEN} như ảnh tham chiếu — nắng xuyên cửa sổ, bụi mịn lấp lánh.\n"
            "Góc quay: Trung cảnh ngang tầm mắt cạnh bàn bếp.\n"
            "Hành động: 0-6s: hai người cùng trộn bột. 6-10s: nhìn nhau bật cười.\n"
            "Chuyển động camera: Oneshot liền mạch, cầm tay rung nhẹ tự nhiên.\n"
            "Ánh sáng & màu sắc: tông ấm, tương phản mềm.\n"
            "Âm thanh: tiếng cười khẽ, tiếng muỗng khuấy bột.\n"
            "Thời lượng: 10 giây, nhịp chậm rãi, không cắt cảnh."))
    return ShotPrompts(prompts=[p("s1"), p("s2"), p("s3", cast=f"{BOY}, {KITCHEN}", people=BOY)])
