# Shot-writing rules (v2: Omni Flash r2v, the FMV method)

## Omni Flash hard limits
- Every clip is reference-to-video (r2v): the prompt plus 2–4 reference images: the people, ALWAYS the location photo, then at most 2 props (machine-checked).
  Never plan a keyframe / first-frame image.
- Every clip is exactly 10 seconds. The edit keeps ~5s of each; the film length follows the story (target is approximate).
- A clip holds at most 2 actions. More actions break the video.
- A clip holds at most 1 transition, and it may only start after 2–3 seconds of stable framing.
  Example: close on a coffee cup, hold, then pull back to reveal the whole room.
- One main idea per clip. A great film is many single-idea clips cut together, not one clip doing everything.
- Avoid what Flow deletes or renders badly: knives, cuts, blood, injuries, violence; readable text; crowds;
  complex hand work; fast multi-person choreography. A hand holds one object; on a bike both hands stay on the bars.

## Continuity comes from the references
Each character is ONE character sheet (close-up + full-body front + side profile + back) reused in every clip; each location
is ONE photo of the empty set reused in every clip there. Say so in every prompt: "Giữ nguyên đúng như ảnh tham chiếu".
Within a sequence, vary the camera place (wide, close, object POV, ceiling, outside the window, floor level). The
film itself moves through as many locations and times as the story needs (directive B3b); shared references keep it
one film across places.

## Rules
1. Lock continuity before camera: face, hair, wardrobe, key props, location geometry and light.
2. Action and camera are two timelines. The subject has up to 2 timed beats; the camera does one primary camera job.
3. Place the camera physically: "từ bên trong lò nướng nhìn ra", "đặt trên sàn nhà hướng lên", "từ trần nhà nhìn thẳng xuống",
   "từ ngoài cửa sổ nhìn vào".
4. Default camera: oneshot, handheld with gentle natural shake (not jerky). It reads as real footage.
5. Put the main action in 2–8s: the first and last seconds are usually trimmed.
6. Light, colour and atmosphere carry the mood (warm golden sun + dust for joy; cold blue-grey night rain for grief).
7. Never stack conflicting commands: /static + any move; /handheld + /gimbal|/steadicam|/robot-arm;
   /low-angle + /high-angle|/overhead; /zoom-in + /dolly-in; /pov + /over-shoulder; two macros.

## Physics first
Omni Flash breaks when a prompt asks for the impossible. Every action is a real cause and effect the camera can see:
weight, contact, gravity, liquids. Nothing appears from nothing, vanishes, changes shape or floats. A count stays
fixed. Magic is shown by light and a physical reveal, not by morphing. One physical event per beat.

## Continuity between clips (machine-checked)
Each clip starts where the previous one ended: same people, same objects in the same hands, same count and colour.
A cut into another story time (past ↔ present) is carried by a bridge seen in both clips — the outgoing clip ends on
it, the incoming clip opens on it (the phone young Daniel lifts is the phone old Daniel lifts; the ring we push in
on is the ring young Daniel holds). Shots carry `period`, `bridge` and `props` (for planning; a prompt names only what its clip shows).

## Machine-checked format of a video prompt (a lint rejects the answer if any line is broken)
Write the prompt in the film's language, brief.language: ENGLISH for "en" (English labels: References, Characters &
wardrobe, Setting, Shot, Action, Camera movement, Lighting & color, Physics, Audio, Duration — the English twins of the
labels below, with "Keep them exactly as in the reference images", "One continuous take, …", "10 seconds, …, one
continuous shot, no cuts." and the voice said "in English"), VIETNAMESE for "vi" as below. Names stay exactly as in the cast. Every block starts on its OWN LINE with its exact
label followed by a colon, in this order:
`Ảnh tham chiếu:` the cast names attached to this clip, comma-separated.
`Nhân vật & trang phục:` must contain "Giữ nguyên đúng như ảnh tham chiếu" whenever a character is in the clip,
  then who is in frame (by name) and what they wear.
`Bối cảnh:` the location "như ảnh tham chiếu" + light, air, details.
`Góc quay:` shot size + physical camera position + composition.
`Hành động:` the shot's actions, each starting with its time range written as `0-4s:` (digits, hyphen, lower-case s),
  exactly the shot's actions and seconds, in increasing order, inside 10s. No other number ranges in this block.
`Chuyển động camera:` starts with "Oneshot liền mạch, …"; one primary job. Two movements → "… rồi …" or "→".
  A shot with an in-shot transition MUST first hold: "Giữ khung ổn định … trong <stable_open_s> giây đầu, rồi …".
`Ánh sáng & màu sắc:` light source, palette, particles.
`Âm thanh:` ambience and diegetic sound. No speech unless the shot has a voice_line; then it MUST contain that line
  verbatim in double quotes, who says it, the fixed brief.voice_style, and when (start ≥1s, end ≤7s), e.g.
  `Âm thanh: Lồng tiếng (voice-over, <voice_style>) nói rõ ràng bằng tiếng Việt từ giây 1.5 đến 6: "<voice_line>". Nền: …`
  or for on-camera dialogue `Âm thanh: Thu Hà nhìn vào camera, khẩu hình khớp lời, nói (<voice_style>) từ giây 2 đến 6: "<voice_line>". Nền: …`.
  Only that one line is spoken; no other words, no subtitles or on-screen text; keep background music very low under a voice.
`Thời lượng:` exactly `10 giây, <nhịp>, không cắt cảnh.`
Required: Bối cảnh, Góc quay, Hành động, Chuyển động camera, Thời lượng (and Nhân vật & trang phục when people appear).
Never begin any other line with one of these labels followed by a colon.
Names: write a character's cast name only in the shots whose cast lists that character; describe anyone else generically.
Keep each prompt under 1000 characters (≈150 words; the FMV prompts that worked were ~570). Just enough: one
short sentence per line, each object named once, no camera equipment, every used object in frame from 0s.
