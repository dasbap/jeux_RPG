"""Transport and persistence interfaces; validation remains server-side."""

from typing import Any, Literal, NotRequired, TypedDict


class RuntimeMessage(TypedDict):
    path: str
    method: Literal["GET", "POST"]
    host: str
    peer: str
    headers: NotRequired[dict[str, str]]
    body: NotRequired[dict[str, Any] | None]
    scheme: NotRequired[str]


class RuntimeResponse(TypedDict):
    status: int
    headers: dict[str, str]
    body: Any


PendingBatch = dict[tuple[str, tuple[Any, ...]], dict[str, Any] | None]
