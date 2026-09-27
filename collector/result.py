"""采集层统一返回封装（ADR-003）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class CollectResult(Generic[T]):
    success: bool
    records: list[T] = field(default_factory=list)
    error_message: str | None = None
