"""Run BRIEF→EDIT_REVIEW with the real claude CLI on a throwaway DB. No Flow calls.

Usage: ./venv/bin/python scripts/director_dry_run.py "tình yêu tuổi trẻ của 2 bạn trẻ" 120
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main(text: str, target: int):
    from agent.db import schema
    schema.DB_PATH = Path(tempfile.mkdtemp()) / "dry.db"
    schema._db_connection = None
    await schema.init_db()
    from agent.director import pipeline, store

    async def stop(run):
        raise pipeline.Gate("TEST_STOP")
    pipeline.HANDLERS["INGEST"] = stop
    run = await store.create_run({"text": text, "target_s": target, "orientation": "HORIZONTAL",
                                  "style": "realistic"}, {})
    run = await pipeline.run_until_blocked(run["id"])
    for s in await store.list_steps(run["id"]):
        print(f"{s['stage']:<12} try {s['attempt']} {s['status']:<12} {s['duration_ms'] / 1000:.0f}s "
              f"lint={len(s['lint'] or [])}")
        for i in s["lint"] or []:
            print(f"    {i['severity']:<7} {i['rule']} [{i['shot_id']}] {i['message']}")
    print("status:", run["status"], "stage:", run["stage"], run.get("error") or "")
    plan = run["plan"]
    shots = plan.get("shotlist", {}).get("shots", [])
    for sh in shots:
        print(f"#{sh['order']:>2} {sh['duration_s']:>2}s {sh['mode']} {len(sh['actions'])}a "
              f"{' '.join(sh['commands']):<40} {sh['idea']}")
    print(f"shots: {len(shots)}  total: {sum(sh['duration_s'] for sh in shots)}s  target: {target}s")
    print("warnings:", json.dumps(plan.get("warnings", []), ensure_ascii=False, indent=1))
    print("editor:", json.dumps(plan.get("editor", {}), ensure_ascii=False)[:800])
    out = Path(f"output/_director/dry-{run['id'][:8]}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    print("plan:", out)
    await schema.close_db()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], int(sys.argv[2])))
