"""FK-LOCAL: canvas layout API."""
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent.db import canvas_crud

router = APIRouter(prefix="/projects/{pid}/canvas", tags=["canvas"])
_KEY = re.compile(r"^(character|scene|video|final|script|idea|note|review):[A-Za-z0-9-]{1,64}$")


class NodeIn(BaseModel):
    x: float
    y: float
    w: float | None = None
    h: float | None = None
    data: dict | None = None


class BulkItem(NodeIn):
    node_key: str


class BulkIn(BaseModel):
    nodes: list[BulkItem]


def _check(key: str) -> None:
    if not _KEY.match(key):
        raise HTTPException(422, f"invalid node_key: {key!r}")


@router.get("")
async def get_canvas(pid: str):
    return {"nodes": await canvas_crud.list_nodes(pid)}


@router.put("/nodes/{node_key}")
async def put_node(pid: str, node_key: str, body: NodeIn):
    _check(node_key)
    return await canvas_crud.upsert_node(pid, node_key, body.x, body.y, body.w, body.h, body.data)


@router.put("/nodes")
async def put_nodes(pid: str, body: BulkIn):
    for n in body.nodes:
        _check(n.node_key)
    out = [await canvas_crud.upsert_node(pid, n.node_key, n.x, n.y, n.w, n.h, n.data)
           for n in body.nodes]
    return {"nodes": out}


@router.delete("/nodes/{node_key}")
async def delete_node(pid: str, node_key: str):
    _check(node_key)
    await canvas_crud.delete_node(pid, node_key)
    return {"ok": True}
