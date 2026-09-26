from __future__ import annotations

import re

from ws.errors import WsError

_SLUG = re.compile(r"^[A-Za-z0-9._-]+$")


def require_slug(value: str, kind: str) -> str:
    if not value or not _SLUG.match(value):
        raise WsError(f"invalid {kind} {value!r}: use letters, digits, '.', '_' or '-'")
    return value


def require_ref(ref: str) -> str:
    if not ref or ref.startswith("/") or ref.endswith("/"):
        raise WsError(f"invalid ref {ref!r}")
    parts = ref.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise WsError(f"invalid ref {ref!r}")
    return ref


def branch_for(workspace: str, checkout: str) -> str:
    return f"ws/{workspace}/{checkout}"
