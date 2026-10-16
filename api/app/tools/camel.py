"""Give stored documents the camelCase keys the web app reads, whichever model produced them."""

from __future__ import annotations

from typing import Any


def camel_key(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(word[:1].upper() + word[1:] for word in rest)


def camelize(value: Any) -> Any:
    if isinstance(value, dict):
        return {camel_key(k) if isinstance(k, str) else k: camelize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [camelize(v) for v in value]
    return value
