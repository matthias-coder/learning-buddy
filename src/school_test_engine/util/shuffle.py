from __future__ import annotations

import random
from typing import TypeVar

T = TypeVar("T")


def new_seed() -> int:
    return random.SystemRandom().randint(0, 2**31 - 1)


def shuffled(items: list[T], seed: int, salt: str = "") -> list[T]:
    rng = random.Random(f"{seed}:{salt}")
    out = list(items)
    rng.shuffle(out)
    return out
