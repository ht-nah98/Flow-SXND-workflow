"""Build agent/director/knowledge/commands.json from the Prompt Bible text export.

Usage: python3 scripts/build_director_commands.py
"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "agent/director/knowledge"
GROUPS = {"A": "framing", "B": "angle", "C": "perspective", "D": "movement", "E": "optics",
          "F": "rig", "G": "time", "H": "transition", "I": "ai_transition", "J": "ai_effect", "K": "preset"}
HEAD = re.compile(r"^# ([A-K])\. ")
CMD = re.compile(r"^(\d{1,3})/([a-z0-9-]+)(?:\(alias: (.+)\))?$")


def build(lines: list[str]) -> list[dict]:
    out, group, i = [], None, 0
    while i < len(lines):
        line = lines[i].strip()
        h = HEAD.match(line)
        if h:
            group = GROUPS[h.group(1)]
        m = CMD.match(line)
        if m and group:
            num, cid, alias = m.groups()
            typ, affects, vi, en, pairing = (lines[i + k].strip() for k in range(1, 6))
            avoid_txt = pairing.split("TRÁNH:", 1)[1] if "TRÁNH:" in pairing else ""
            good_txt = pairing.split("TRÁNH:", 1)[0].replace("GHÉP:", "")
            out.append({"num": int(num), "id": cid, "aliases": re.findall(r"/([a-z0-9-]+)", alias or ""),
                        "type": typ.lower(), "group": group, "affects": affects,
                        "explain_vi": vi, "expansion_en": en,
                        "pairs_with": re.findall(r"/([a-z0-9*-]+)", good_txt),
                        "avoid": re.findall(r"/([a-z0-9*-]+)", avoid_txt)})
            i += 6
            continue
        i += 1
    return sorted(out, key=lambda c: c["num"])


def _expand(refs: list[str], ids: set[str], self_id: str) -> list[str]:
    """`/rack-focus-*` → every matching id; drop prose fragments like `dolly` and the entry's own id."""
    out = []
    for r in refs:
        if r.endswith("*"):
            out += sorted(i for i in ids if i.startswith(r[:-1]))
        elif r in ids:
            out.append(r)
    return sorted(set(out) - {self_id})


def main():
    cmds = build((ROOT / "source/prompt-bible.txt").read_text(encoding="utf-8").splitlines())
    # An alias shared by several entries is ambiguous: drop it rather than let one entry shadow another.
    counts = Counter(a for c in cmds for a in c["aliases"])
    for c in cmds:
        c["aliases"] = [a for a in c["aliases"] if counts[a] == 1]
    names = [c["id"] for c in cmds] + [a for c in cmds for a in c["aliases"]]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        raise SystemExit(f"command ids/aliases collide: {dupes}")
    ids = set(names)
    for c in cmds:
        c["avoid"] = _expand(c["avoid"], ids, c["id"])
        c["pairs_with"] = _expand(c["pairs_with"], ids, c["id"])
    (ROOT / "commands.json").write_text(json.dumps(cmds, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(cmds), "commands")


if __name__ == "__main__":
    main()
