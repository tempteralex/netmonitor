"""П5: Подтверждение смены состояния (A14).

Seam: StateTracker — чистая логика. Состояние считается подтверждённым после
confirm_count одинаковых наблюдений подряд. Разовое отклонение сбрасывает счётчик,
но подтверждённое состояние сохраняется, пока новое не наберёт N подтверждений.
"""
from __future__ import annotations

from netmonitor.monitor import State


class StateTracker:
    def __init__(self, confirm_count: int):
        if confirm_count < 1:
            raise ValueError("confirm_count must be >= 1")
        self._confirm_count = confirm_count
        self._confirmed: State | None = None   # текущее подтверждённое состояние
        self._pending: State | None = None     # что наблюдается сейчас
        self._streak: int = 0                  # сколько раз подряд наблюдается _pending

    @property
    def current(self) -> State | None:
        return self._confirmed

    def observe(self, state: State) -> State | None:
        """Зафиксировать наблюдение. Вернуть новое подтверждённое состояние, если
        оно сменилось в этой итерации; иначе None."""
        if state == self._pending:
            self._streak += 1
        else:
            self._pending = state
            self._streak = 1

        if self._streak >= self._confirm_count:
            if self._pending != self._confirmed:
                self._confirmed = self._pending
                return self._confirmed   # сменилось → вернуть новое
            # уже подтверждённое и держится — не «новое»
        return None
