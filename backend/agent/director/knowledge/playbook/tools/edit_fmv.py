"""Cut the FMV remake like the sample: trimmed 3-7s segments, hard cuts, white light-leak flash for the
time jump, warm->cold grade for the night shot. Usage: python3 edit.py <clips_dir> <out.mp4>"""
import subprocess
import sys

CLIPS, OUT = sys.argv[1], sys.argv[2]
# (clip, start, duration, transition INTO this segment, grade)
EDL = [
    (10, 1.0, 4.0, None, "warm"),       # overhead: the two of them baking — establishes the kitchen
    (1, 2.5, 5.5, "cut", "warm"),       # oneshot together at the counter
    (2, 4.5, 4.5, "cut", "warm"),       # he sneaks up, flour on her cheek
    (3, 4.0, 5.0, "cut", "warm"),       # POV from the oven, she peeks in
    (8, 3.5, 6.0, "cut", "warm"),       # pretend burn, she checks, kiss on the cheek
    (4, 1.0, 4.5, "cut", "warm"),       # selfie with the finished cake
    (5, 1.5, 5.0, "flash", "warm"),     # time jump: motorbike by the sea
    (6, 4.5, 5.3, "cut", "warm"),       # stairs vlog, kiss to camera
    (11, 3.0, 4.5, "cut", "dream"),     # through the window, blurred — memory
    (7, 1.5, 4.5, "flash", "neutral"),  # cake with candles — now
    (9, 2.0, 6.5, "cut", "cold"),       # alone, rainy night
]
GRADE = {
    "warm": "colorbalance=rs=.04:gs=.01:bs=-.04,eq=saturation=1.05",
    "dream": "gblur=sigma=2,colorbalance=rs=.05:bs=-.03,eq=brightness=.03",
    "neutral": "null",
    "cold": "colorbalance=rs=-.06:gs=-.01:bs=.08,eq=saturation=.75:brightness=-.03",
}
FLASH = 0.5  # seconds of white flash on a time jump

inputs, chains = [], []
half = FLASH / 2  # white flash: the outgoing shot fades to white, the incoming one fades up from it
for i, (clip, ss, dur, kind, grade) in enumerate(EDL):
    inputs += ["-ss", str(ss), "-t", str(dur), "-i", f"{CLIPS}/clip{clip:02d}.mp4"]
    fx = []
    if kind == "flash":
        fx.append(f"fade=t=in:d={half}:color=white")
    if i + 1 < len(EDL) and EDL[i + 1][3] == "flash":
        fx.append(f"fade=t=out:st={dur - half:.3f}:d={half}:color=white")
    if i + 1 == len(EDL):
        fx.append(f"fade=t=out:st={dur - 1.0:.3f}:d=1.0")
    chains.append(f"[{i}:v]scale=1280:720,setsar=1,fps=24,format=yuv420p,{GRADE[grade]},setpts=PTS-STARTPTS"
                  f"{''.join(',' + f for f in fx)}[v{i}];"
                  f"[{i}:a]aresample=48000,asetpts=PTS-STARTPTS,afade=t=in:d=0.08,"
                  f"afade=t=out:st={dur - (1.5 if i + 1 == len(EDL) else 0.12):.3f}"
                  f":d={1.5 if i + 1 == len(EDL) else 0.12}[a{i}]")
total = sum(d for _, _, d, _, _ in EDL)
chains.append("".join(f"[v{i}][a{i}]" for i in range(len(EDL))) + f"concat=n={len(EDL)}:v=1:a=1[vout][aout]")

cmd = ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(chains),
       "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "high", "-crf", "18", "-preset", "medium", "-movflags", "+faststart",
       "-c:a", "aac", "-b:a", "192k", OUT]
subprocess.run(cmd, check=True)
print(f"{OUT} {total:.1f}s")
