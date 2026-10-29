"""Credit guard (spec §5): nothing reaches Flow without a reservation."""
import math

from agent import config
from agent.db import crud
from agent.director import store
from agent.director.schemas import ShotList


class BudgetExceeded(Exception):
    def __init__(self, kind: str):
        super().__init__(f"budget exhausted for {kind}")
        self.kind = kind


def estimate(shotlist: ShotList) -> dict:
    """Video budget asked at the ASSETS gate: one r2v clip per shot plus a quarter for regens."""
    n = len(shotlist.shots)
    regens = math.ceil(0.25 * n)
    return {"videos": n, "regens": regens, "credits_est": (n + regens) * config.DIRECTOR_CREDIT_TABLE["video"]}


def estimate_refs(n: int) -> dict:
    return {"refs": n, "credits_est": n * config.DIRECTOR_CREDIT_TABLE["image"]}


async def guarded_request(run_id: str, kind: str, **kw) -> dict:
    if not await store.reserve(run_id, kind):
        raise BudgetExceeded(kind)
    return await crud.create_request(**kw)
