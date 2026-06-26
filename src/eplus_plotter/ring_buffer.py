"""A fixed-capacity (x, y) ring buffer that bounds a series' memory.

Once full, the oldest point is overwritten, so a long run keeps a rolling window rather than
growing without bound. `xy()` returns the points in order — a cheap view while the buffer hasn't
wrapped (the common case for an annual run that fits), a concatenated copy after it wraps.
"""

from __future__ import annotations

import numpy as np


class RingBuffer:
    def __init__(self, capacity: int) -> None:
        self._cap = capacity
        self._x = np.empty(capacity, dtype=float)
        self._y = np.empty(capacity, dtype=float)
        self._n = 0  # total points appended (may exceed capacity)

    def append(self, x: float, y: float) -> None:
        i = self._n % self._cap
        self._x[i] = x
        self._y[i] = y
        self._n += 1

    def __len__(self) -> int:
        return min(self._n, self._cap)

    def xy(self) -> tuple[np.ndarray, np.ndarray]:
        if self._n <= self._cap:
            return self._x[: self._n], self._y[: self._n]
        start = self._n % self._cap  # oldest point after wrapping
        return (
            np.concatenate([self._x[start:], self._x[:start]]),
            np.concatenate([self._y[start:], self._y[:start]]),
        )
