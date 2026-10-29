"""The run's 📋 Nhật ký (21/10): every step with the reasons it was sent back, what the AI did, what Flow was asked —
in Vietnamese, with the scene number, so the user sees why a line is red without asking in chat."""
from agent.db import crud
from agent.director import store


# lint rule → short Vietnamese name. The English message stays as the detail.
RULE_VI = {
    # Ambient mode (directive B14, playbook 11)
    "amb_one_venue": "Phim không khí chỉ có một bối cảnh", "amb_no_characters": "Phim không khí không có nhân vật",
    "amb_details": "Quá nhiều ảnh chi tiết (tối đa 2)", "amb_venue_crowd": "Ảnh bối cảnh phải có khán giả kín chỗ", "amb_one_sequence": "Phim không khí chỉ có một đoạn",
    "amb_reel_length": "Số shot không khớp độ dài vòng hình", "amb_kind": "Shot thiếu loại (toàn / khán giả / chi tiết / sân khấu)",
    "amb_no_voice": "Phim không khí không có lời nói", "amb_plain_cut": "Phim không khí chỉ cắt thẳng giữa các shot",
    "amb_no_action": "Người chỉ có trạng thái, không có hành động", "amb_states": "Quá nhiều trạng thái trong một clip",
    "amb_one_camera": "Mỗi clip đúng một chuyển động máy chậm", "amb_slow_camera": "Máy quay quá nhanh / rung",
    "amb_open_wide": "Vòng hình phải mở bằng toàn cảnh", "amb_loop_seam": "Shot cuối không được là toàn cảnh (chỗ lặp)",
    "amb_rotate": "Hai shot cùng loại liền nhau", "amb_variety": "Ít loại shot / quá nhiều toàn cảnh",
    "amb_prompt_words": "Prompt phim không khí quá ngắn / dài", "amb_references": "Prompt thiếu dòng References",
    "amb_no_text": "Có chữ / logo đọc được", "amb_performer_face": "Lộ mặt người biểu diễn (Flow có thể chặn)",
    "story_spine": "Thiếu xương sống truyện", "director_notes": "Thiếu ý đồ đạo diễn", "hooks": "Thiếu khoảnh khắc giữ chân",
    "source_map": "Bỏ sót phần truyện của anh", "prop_single": "Ảnh đạo cụ chứa nhiều vật",
    "total_duration": "Độ dài phim lệch xa", "cast_unknown": "Tên nhân vật không có trong truyện",
    "too_many_refs": "Quá nhiều ảnh tham chiếu", "location_ref": "Thiếu ảnh bối cảnh",
    "mode_r2v": "Không phải chế độ prompt + asset", "clip_duration": "Độ dài clip sai",
    "r2v_no_refs": "Clip không có ảnh tham chiếu", "beat_unknown": "Nhịp truyện không tồn tại",
    "unknown_command": "Lệnh máy quay lạ", "group_duplicate": "Hai lệnh máy cùng nhóm",
    "movement_count": "Quá nhiều chuyển động máy", "conflict": "Hai lệnh máy mâu thuẫn", "macro": "Lệnh máy ghép sai",
    "action_compound": "Một hành động bị nhồi nhiều cử chỉ", "actions_count": "Quá nhiều hành động",
    "action_range": "Hành động ra ngoài thời lượng clip", "action_overlap": "Hai hành động chồng nhau",
    "transition_timing": "Chuyển cảnh sai thời điểm", "transition_plus_movement": "Chuyển cảnh kèm chuyển động khác",
    "voice_too_long": "Câu thoại quá dài", "order": "Thứ tự cảnh sai", "empty_sequence": "Đoạn truyện không có cảnh",
    "time_bridge": "Nhảy thời gian không có cầu nối", "place_jump": "Đổi nơi không có lý do",
    "recurring_prop": "Đồ vật lặp lại chưa có ảnh", "beats_count": "Số nhịp trong clip sai",
    "beat_too_long": "Một nhịp viết quá dài", "hold_open": "Đầu clip chưa giữ khung đứng yên",
    "handoff_timing": "Chuyển cảnh sai thời điểm", "action_during_handoff": "Có người hành động lúc máy chuyển",
    "continues_first": "Clip đầu không thể nối tiếp", "handoff_missing": "Thiếu cách chuyển sang cảnh sau",
    "final_frame_missing": "Thiếu mô tả khung kết", "time_jump_light": "Nhảy thời gian không qua ánh sáng",
    "entrance": "Nhân vật xuất hiện từ hư không", "missing_prompt": "Cảnh chưa có prompt",
    "style_pack": "Thiếu dấu hiệu gói phong cách", "missing_block": "Prompt thiếu một mục",
    "duration_block": "Mục thời lượng sai", "constraints": "Thiếu câu giữ nguyên nhân vật",
    "timestamps": "Mốc giây sai", "voice_line": "Câu thoại không khớp", "extra_person": "Nhắc người không có trong cảnh",
    "keyframe": "Có prompt ảnh khung đầu", "asset_named": "Gọi sai tên đạo cụ", "twin_objects": "Hai vật giống nhau từ một ảnh",
    "camera_object": "Prompt tả máy quay như một vật", "photo_faces": "Ảnh trong cảnh lộ mặt người (Flow sẽ chặn)", "news_look": "Trông như bản tin truyền hình thật (Flow sẽ chặn)", "abstract_final_frame": "Khung cuối là hình trừu tượng (loé sáng, cận cực) — cảnh sau sẽ bị cắt cứng", "flip_action": "Lật / rút vật phẳng — Flow không làm được", "camera_beat_short": "Chuyển động máy quá ngắn — Flow sẽ cắt", "lens_gaze": "Nhân vật nhìn vào ống kính", "kf_keyframe": "Ảnh keyframe tả thiếu / quá dài", "kf_cast": "Keyframe không nêu tên nhân vật / bối cảnh", "kf_cast_missing": "Keyframe có người không có ảnh tham chiếu", "kf_use": "Thiếu độ dài dùng trong phim (0.8–5s)", "kf_one_thing": "Shot keyframe làm nhiều việc", "kf_join": "Keyframe không khớp cách nối (che / màn hình / nhoè)", "kf_first_join": "Shot đầu không thể nối từ shot trước", "kf_place_change": "Đổi nơi bằng cắt giữa hành động", "kf_both_ends": "Shot nối hai đầu phải dùng trọn 4s", "kf_prompt_len": "Prompt keyframe quá ngắn / dài", "kf_template": "Prompt keyframe dùng mẫu liền mạch", "kf_end": "Prompt không kết vào keyframe shot sau", "bridge_prompt": "Prompt thiếu vật nối cảnh",
    "too_long": "Prompt quá dài", "movement_sequence": "Hai chuyển động không ghi thứ tự",
    "transition_prompt": "Prompt chuyển cảnh thiếu khung ổn định", "style_block": "Thiếu khối phong cách chung",
    "avoid_block": "Thiếu danh sách cần tránh chung", "cont_open": "Prompt thiếu câu nối khung trước",
    "seconds": "Các khối SECOND sai", "handoff_prompt": "Prompt không đặt chuyển cảnh đúng giây",
    "final_frame_contract": "Prompt thiếu FINAL FRAME CONTRACT", "camera_language": "Prompt thiếu Camera language",
    "sound_block": "Prompt thiếu Sound / No music",
}
REQ_VI = {"GENERATE_CHARACTER_IMAGE": "Tạo ảnh asset", "REGENERATE_CHARACTER_IMAGE": "Tạo lại ảnh asset",
          "EDIT_CHARACTER_IMAGE": "Sửa ảnh asset", "GENERATE_VIDEO_REFS": "Tạo video", "GENERATE_VIDEO": "Tạo video",
          "REGENERATE_VIDEO": "Tạo lại video", "GENERATE_IMAGE": "Tạo ảnh cảnh", "UPSCALE_VIDEO": "Nâng chất lượng video"}


async def build(run: dict) -> dict:
    from agent.director.pipeline import STAGE_VI
    plan = run.get("plan") or {}
    shots = (plan.get("shotlist") or {}).get("shots") or []
    scene_of_shot = {s["id"]: s["order"] for s in shots}
    ids = plan.get("ids") or {}
    scene_of_row = {sc: scene_of_shot.get(sid) for sid, sc in (ids.get("scenes") or {}).items()}
    entity_of_row = {cid: name for name, cid in (ids.get("entities") or {}).items()}
    steps = []
    for s in await store.list_steps(run["id"]):
        issues = [{"rule": i.get("rule"), "label": RULE_VI.get(i.get("rule"), i.get("rule")),
                   "shot_id": i.get("shot_id"), "scene": scene_of_shot.get(i.get("shot_id")),
                   "message": i.get("message", ""), "severity": i.get("severity", "error")}
                  for i in (s.get("lint") or []) if isinstance(i, dict)]
        steps.append({"id": s["id"], "stage": s["stage"], "label": STAGE_VI.get(s["stage"], s["stage"]),
                      "attempt": s["attempt"], "status": s["status"], "duration_ms": s.get("duration_ms"),
                      "created_at": s["created_at"], "issues": issues})
    events = [{k: e[k] for k in ("id", "kind", "level", "title", "data", "created_at")}
              for e in await store.list_events(run["id"])]
    requests = []
    if run.get("project_id"):
        for r in await crud.list_requests(project_id=run["project_id"]):
            requests.append({"id": r["id"], "type": r["type"], "label": REQ_VI.get(r["type"], r["type"]),
                             "status": r["status"], "scene": scene_of_row.get(r.get("scene_id")),
                             "entity": entity_of_row.get(r.get("character_id")),
                             # a request that finished keeps the message of an earlier retry: show it only when failed
                             "error": r.get("error_message") if r["status"] == "FAILED" else None,
                             "retries": r.get("retry_count", 0), "created_at": r["created_at"],
                             "updated_at": r["updated_at"]})
        requests.reverse()   # oldest first, like the rest of the log
    return {"run_id": run["id"], "status": run["status"], "stage": run["stage"],
            "stage_label": STAGE_VI.get(run["stage"], run["stage"]), "gate": run.get("gate"),
            "steps": steps, "events": events, "requests": requests}
