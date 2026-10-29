---
name: flow-video-playbook
description: Use when planning, scripting, prompting, generating, editing or debugging Google Flow / Omni Flash videos with FlowKit + Flow Canvas, when the user gives feedback on a film or a new instruction, or a new sample video to learn from.
---
# Flow video playbook

Knowledge lives in `backend/agent/director/knowledge/playbook/` (relative to the flow-canvas repo root) (Vietnamese).

## Read first, every time
1. `00-loi-dan-nguoi-dung.md` — ALL of the user's standing directives with their original words and dates.
   Highest authority; injected into every director role by `brain.py`. Lines marked ⚠️ are ones the AI already
   forgot once (r2v default, 5–8s cuts, story spine, voice, physics, multi-location films, idea → AI builds the
   script). Where each rule lives: roles/*.md say HOW (one place per rule), 00 says WHAT the user wants. Run its "Tự kiểm" checklist before
   presenting any script or spending credits.
2. `07-nhat-ky-bai-hoc.md` — log of every film attempt: what failed, root cause, fix.
3. `08-quy-tac-lam-viec.md` — how to work with this user (credits need approval, no subagents, Vietnamese replies,
   outputs in `../phim/<project>_<id8>/final.mp4` (FLOWKIT_OUTPUT_DIR), port 8100 untouchable).

Then the step file you need: 01-kich-ban (story spine + script), 02-asset (character sheets, EMPTY location plates),
03-prompt-video (r2v template, camera library), 04-dung-phim (cut rhythm, export), 05-xu-ly-loi (failures),
06-hieu-ung (CapCut-style effects rebuilt in ffmpeg — never download CapCut assets), samples/ (studied films).

## Thinking traps already hit
- A coverage lesson (many angles of one sequence) is NOT a rule to keep the film in one place.
- The user gives IDEAS; the writer invents the world (places, past, people). Only a pasted full story is adapted.
- Target length is approximate; never pad or cut a story to hit seconds.
- A cut to another story time needs a bridge seen in BOTH clips (phone young Daniel lifts = phone old Daniel lifts);
  props keep count/colour/hand across clips. Machine-checked (`period`/`bridge`/`props`, lint time_bridge, props_block).
- A rule the user had to repeat is a missing lint. The playbook itself has taught wrong things (one main location,
  3-timestamp template, 1–3 refs vs lint 7) — check docs against lint constants.
- Full table of the 9 recurring mistakes: `07-nhat-ky-bai-hoc.md` → "Đúc kết 14–20/10". Read it first.

## When the user says something new
1. Add it to `00-loi-dan-nguoi-dung.md` immediately, in the right section, with the quote and date
   (⚠️ if it repeats something already there — that means it was forgotten).
2. Enforce it in code where a machine can check it (`lint.py`, schemas, roles/*.md), with a test.
3. After a film, add a row to `07-nhat-ky-bai-hoc.md`; fold any new rule back into 00.
4. Commit in the flow-canvas repo.

## New sample video
Follow `samples/_cach-hoc-video-mau.md`: understand the STORY (line, message, value, rule & cost — ask the user if
unsure), not only the shots; update topic files (🧪 new, ✅ proven) and commit.
