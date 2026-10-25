from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget


@dataclass(frozen=True, slots=True)
class TextControl:
    name: str
    default: str


@dataclass(frozen=True, slots=True)
class BoolControl:
    name: str
    default: bool


@dataclass(frozen=True, slots=True)
class ChoiceControl:
    name: str
    default: str
    options: list[str]


@dataclass(frozen=True, slots=True)
class IntControl:
    name: str
    default: int
    minimum: int
    maximum: int


@dataclass(frozen=True, slots=True)
class FloatControl:
    name: str
    default: float
    minimum: float
    maximum: float


Control = TextControl | BoolControl | ChoiceControl | IntControl | FloatControl


@dataclass(frozen=True, slots=True)
class StoryDef:
    controls: list[Control]
    make_widget: Callable[[dict, dict], QWidget]


BuildFn = Callable[[], StoryDef]

_registry: dict[str, BuildFn] = {}


def story(name: str):
    """Decorator: registers a zero-arg StoryDef builder under `name`."""

    def decorator(build_fn: BuildFn) -> BuildFn:
        if name in _registry:
            raise ValueError(f"Story '{name}' is already registered")
        _registry[name] = build_fn
        return build_fn

    return decorator


def all_story_names() -> list[str]:
    return list(_registry.keys())


def get_story(name: str) -> StoryDef:
    return _registry[name]()


__all__ = [
    "BoolControl",
    "ChoiceControl",
    "Control",
    "FloatControl",
    "IntControl",
    "StoryDef",
    "TextControl",
    "all_story_names",
    "get_story",
    "story",
]
