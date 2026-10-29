"""FK-LOCAL: map a successful REST mutation to an entity_changed event."""
import re

_PATH = re.compile(r"^/api/(projects|characters|videos|scenes)(?:/([^/]+))?(?:/(.*))?$")
_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
_ENTITY = {"projects": "project", "characters": "character", "videos": "video", "scenes": "scene"}


def classify_mutation(method: str, path: str) -> dict | None:
    if method not in _MUTATING:
        return None
    m = _PATH.match(path)
    if not m:
        return None
    coll, ident, rest = m.group(1), m.group(2), m.group(3)
    entity = _ENTITY[coll]
    project_id = ident if coll == "projects" else None
    if coll == "projects" and rest and rest.startswith("export"):
        return None  # downloads/zips existing media, doesn't mutate the project
    if coll == "projects" and rest and rest.startswith("canvas"):
        entity = "canvas"
    if ident is None:
        action = "created" if method == "POST" else "updated"
    elif method == "DELETE" and not rest:
        action = "deleted"
    else:
        action = "updated"
    return {"entity": entity, "id": ident, "project_id": project_id, "action": action}
