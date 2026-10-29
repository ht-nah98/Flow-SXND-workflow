"""The script package (learned from the SciCloud sample, 19/10): three readable Markdown files built from the plan,
no AI call. README (the director's intent, how the film is made, what the user can change), the script with its
lines, and the storyboard with every clip's prompt. Written next to the film: phim/<project>/kich-ban/."""
from pathlib import Path

from agent import config
from agent.utils.paths import project_folder

FILES = ("README.md", "kich-ban.md", "phan-canh-prompt.md")
CREDIT_PER_CLIP = 15
CREDIT_PER_IMAGE = 1
KIND = {"character": "Nhân vật", "location": "Bối cảnh", "visual_asset": "Đạo cụ"}
VOICE = {"none": "Không lời", "voiceover": "Lồng tiếng (người kể)", "dialogue": "Nhân vật nói trước camera"}
CREATIVITY = {"faithful": "Bám sát ý tưởng", "balanced": "Cân bằng", "bold": "Bay bổng"}


def clock(s) -> str:
    s = int(round(s or 0))
    return f"{s // 60}:{s % 60:02d}"


def _act_range(seq: dict) -> str:
    if seq.get("start_s") is None or seq.get("end_s") is None:
        return ""
    return f" ({clock(seq['start_s'])}–{clock(seq['end_s'])})"


def _readme(run: dict, title: str, prompts: dict) -> str:
    plan, brief = run["plan"], run["plan"].get("brief") or {}
    story, shots = plan.get("story") or {}, (plan.get("shotlist") or {}).get("shots", [])
    cast = story.get("cast", [])
    ed = plan.get("editor") or {}
    out = [f"# {title} — Gói kịch bản", "",
           "| File | Nội dung |", "|------|----------|",
           "| `README.md` | Ý đồ, cách tạo phim, điểm có thể sửa (file này) |",
           "| `kich-ban.md` | Kịch bản đầy đủ: nhân vật, các màn có mốc giờ, lời thoại |",
           f"| `phan-canh-prompt.md` | {len(shots)} clip: hình, máy quay, thoại, asset, prompt video |", ""]
    if story.get("director_notes"):
        out += ["## Ý đồ của đạo diễn", *[f"{i}. {n}" for i, n in enumerate(story["director_notes"], 1)], ""]
    spine = [("Tuyến truyện", "story_line"), ("Thông điệp", "message"), ("Giá trị cho người xem", "viewer_value"),
             ("Luật & cái giá", "rule_and_cost")]
    if any(story.get(k) for _, k in spine):
        out += ["## Xương sống câu chuyện", *[f"- **{n}**: {story[k]}" for n, k in spine if story.get(k)], ""]
    if story.get("hooks"):
        out += ["## Khoảnh khắc giữ chân",
                *[f"- **{clock(h['at_s'])}** — {h['moment']}" for h in sorted(story["hooks"], key=lambda h: h["at_s"])], ""]
    refs = [c for c in cast if not c.get("provided_image")]
    out += ["## Cách tạo trên Google Flow (Omni Flash)",
            f"- Ngôn ngữ phim: {'tiếng Anh' if brief.get('language', 'en') == 'en' else 'tiếng Việt'} · "
            f"khổ {'9:16' if brief.get('orientation') == 'VERTICAL' else '16:9'} · ~{brief.get('target_s', 60)}s (linh hoạt)"
            f" · giọng: {VOICE.get(brief.get('voice', 'none'), brief.get('voice'))}"
            + (f" — {brief['voice_style']}" if brief.get("voice_style") else ""),
            f"- Mức sáng tạo: {CREATIVITY.get(brief.get('creativity', 'balanced'))}",
            f"- Bước 1 — asset: {len(cast)} ảnh tham chiếu ({len(refs)} cần tạo, ~{len(refs) * CREDIT_PER_IMAGE} credit): "
            "mỗi nhân vật một character sheet, mỗi bối cảnh một ảnh phông trống.",
            f"- Bước 2 — video: {len(shots)} clip 10s, mỗi clip = prompt + ảnh asset của clip (không tạo ảnh trước), "
            f"~{len(shots) * CREDIT_PER_CLIP} credit.",
            "- Bước 3 — dựng: mỗi clip giữ ~5–8s đẹp nhất, nối theo thứ tự, hiệu ứng chuyển cảnh, xuất 1080p.", ""]
    out += ["## Điểm bạn có thể sửa",
            "- Tên nhân vật, trang phục, bối cảnh: sửa trên node asset rồi tạo lại ảnh (các clip dùng asset đó sẽ cần tạo lại).",
            "- Câu thoại, hành động của một clip: sửa prompt trên node cảnh hoặc bấm \"Viết lại clip\".",
            "- Cái kết, độ dài, giọng, mức sáng tạo: góp ý cho đạo diễn để viết lại (không tốn credit trước khi duyệt).", ""]
    if story.get("notes_for_user") or plan.get("warnings"):
        out += ["## Ghi chú", *[f"- ⚠️ {n}" for n in story.get("notes_for_user", [])],
                *[f"- {w}" for w in plan.get("warnings", [])], ""]
    status = (f"Editor chấm {ed['score']}/100." if "score" in ed else
              "Editor đã tắt." if ed.get("skipped") else "Chưa qua editor.")
    done = sum(1 for p in prompts.values() if p.get("done"))
    out += ["## Trạng thái", f"- {status} Video đã có: {done}/{len(shots)} clip.", ""]
    return "\n".join(out)


def _script(run: dict, title: str) -> str:
    plan, brief = run["plan"], run["plan"].get("brief") or {}
    story = plan.get("story") or {}
    out = [f"# {title} — Kịch bản", "",
           f"> **Logline**: {brief.get('logline', '')}",
           f"> **Thể loại / tông**: {brief.get('genre', '')} / {brief.get('tone', '')} · **Độ dài**: ~{brief.get('target_s', 60)}s",
           "", story.get("synopsis", ""), ""]
    by_kind: dict[str, list] = {}
    for c in story.get("cast", []):
        by_kind.setdefault(c["entity_type"], []).append(c)
    for kind, label in KIND.items():
        if by_kind.get(kind):
            out.append(f"## {label}")
            for c in by_kind[kind]:
                out.append(f"- **{c['name']}** — {c.get('description', '')}")
                if c.get("personality"):
                    out.append(f"  - Tính cách: {c['personality']}")
                if c.get("signature"):
                    out.append(f"  - Động tác đặc trưng: {c['signature']}")
            out.append("")
    beats = story.get("beats", [])
    hooks = {h["beat_id"]: h for h in story.get("hooks", [])}
    out.append("## Kịch bản")
    for seq in story.get("sequences", []):
        out += ["", f"### Màn {seq['act']}{_act_range(seq)} — {seq['title']}", f"*{seq.get('purpose', '')}*", ""]
        for b in (b for b in beats if b["sequence_id"] == seq["id"]):
            mark = f" ⏱ **{clock(hooks[b['id']]['at_s'])}**" if b["id"] in hooks else ""
            out.append(f"- **{b['id']}** ({b.get('emotion', '')}){mark}: {b['summary']}")
            if b.get("voice_line"):
                who = "V.O." if brief.get("voice") != "dialogue" else "Thoại"
                out.append(f"  > **{who}**: \"{b['voice_line']}\"")
    return "\n".join(out) + "\n"


def _storyboard(run: dict, title: str, prompts: dict) -> str:
    plan = run["plan"]
    story = plan.get("story") or {}
    shots = sorted((plan.get("shotlist") or {}).get("shots", []), key=lambda s: s["order"])
    beat_seq = {b["id"]: b["sequence_id"] for b in story.get("beats", [])}
    seqs = {s["id"]: s for s in story.get("sequences", [])}
    out = [f"# {title} — Phân cảnh & prompt", "",
           "Mỗi clip 10s, tạo bằng prompt + ảnh asset (r2v). Bản dựng giữ ~5–8s đẹp nhất mỗi clip.", ""]
    current = None
    for s in shots:
        seq = seqs.get(beat_seq.get(s["beat_id"]))
        if seq and seq["id"] != current:
            current = seq["id"]
            out += [f"## Màn {seq['act']}{_act_range(seq)} — {seq['title']}", ""]
        p = prompts.get(s["id"], {})
        camera = " ".join(s.get("commands", []))
        if s.get("transition"):
            t = s["transition"]
            camera += f" · chuyển trong shot từ {t.get('start_s')}s: {t.get('technique')}"
        out += [f"### Clip {s['order']} — {s['idea']}",
                f"- **Hình**: {s.get('story_beat', '')}",
                f"- **Máy quay**: {camera}",
                f"- **Asset**: {', '.join(s.get('cast', []))}"]
        if s.get("voice_line"):
            out.append(f"- **Thoại**: \"{s['voice_line']}\"")
        out += ["- **Prompt video**:", "", "```", p.get("video_prompt") or "(chưa có prompt)", "```", ""]
    return "\n".join(out)


def build(run: dict, title: str, scenes: dict[str, dict] | None = None) -> dict[str, str]:
    """The three files. `scenes` (shot id → scene row) lets the user's own prompt edits on the canvas win."""
    prompts = {p["shot_id"]: dict(p) for p in (run["plan"].get("prompts") or {}).get("prompts", [])}
    for sid, row in (scenes or {}).items():
        p = prompts.setdefault(sid, {})
        if row.get("video_prompt"):
            p["video_prompt"] = row["video_prompt"]
        p["done"] = "COMPLETED" in (row.get("horizontal_video_status"), row.get("vertical_video_status"))
    return {"README.md": _readme(run, title, prompts), "kich-ban.md": _script(run, title),
            "phan-canh-prompt.md": _storyboard(run, title, prompts)}


def write(project: dict, files: dict[str, str]) -> Path:
    folder = Path(config.OUTPUT_DIR) / project_folder(project) / "kich-ban"
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (folder / name).write_text(text, encoding="utf-8")
    return folder
