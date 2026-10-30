"""Тесты для П5: state_tracker.StateTracker

Чистая логика подтверждения смены состояния (A14). Без моков.

Seam:
  StateTracker(confirm_count)
    .current        -> State | None   # подтверждённое состояние
    .observe(state) -> State | None   # новое подтверждённое, если сменилось; иначе None

Поведение:
  - пока не набрано confirm_count одинаковых наблюдений подряд → current=None
  - после N одинаковых → current становится этим состоянием; observe возвращает его
    (только в той итерации, когда оно подтвердилось)
  - разовое отклонение сбрасывает счётчик; current НЕ меняется, observe=None
  - подтверждённое состояние меняется только когда новое наблюдение стабильно N раз подряд
"""
import pytest

from netmonitor.monitor import State
from netmonitor.state_tracker import StateTracker


# --- старт: ничего не подтверждено ------------------------------------------

def test_initial_current_is_none():
    t = StateTracker(confirm_count=2)
    assert t.current is None


def test_single_observation_not_enough_to_confirm():
    t = StateTracker(confirm_count=2)
    assert t.observe(State.UNRESTRICTED) is None
    assert t.current is None


def test_confirmed_after_n_observations_returns_state():
    t = StateTracker(confirm_count=2)
    assert t.observe(State.UNRESTRICTED) is None       # 1-е
    assert t.observe(State.UNRESTRICTED) is State.UNRESTRICTED  # 2-е → подтверждено
    assert t.current is State.UNRESTRICTED


def test_third_same_observation_returns_none_already_confirmed():
    t = StateTracker(confirm_count=2)
    t.observe(State.UNRESTRICTED)
    t.observe(State.UNRESTRICTED)  # подтвердилось
    assert t.observe(State.UNRESTRICTED) is None       # уже подтверждено, не новое


# --- разовое отклонение сбрасывает счётчик ----------------------------------

def test_single_outlier_resets_counter_does_not_change_state():
    t = StateTracker(confirm_count=3)
    t.observe(State.UNRESTRICTED)
    t.observe(State.UNRESTRICTED)
    assert t.observe(State.NO_INTERNET) is None        # разовый сбой → сброс
    assert t.current is None
    # нужно снова набрать 3 одинаковых
    assert t.observe(State.UNRESTRICTED) is None
    assert t.observe(State.UNRESTRICTED) is None
    assert t.observe(State.UNRESTRICTED) is State.UNRESTRICTED


# --- смена подтверждённого состояния ----------------------------------------

def test_state_change_requires_n_observations_of_new_state():
    t = StateTracker(confirm_count=2)
    for _ in range(2):
        t.observe(State.UNRESTRICTED)
    assert t.current is State.UNRESTRICTED

    # переход UNRESTRICTED -> NO_INTERNET
    assert t.observe(State.NO_INTERNET) is None        # 1-е наблюдение нового
    assert t.current is State.UNRESTRICTED             # пока старое подтверждённое
    assert t.observe(State.NO_INTERNET) is State.NO_INTERNET  # 2-е → подтверждена смена
    assert t.current is State.NO_INTERNET


def test_brief_outlier_then_back_to_current_keeps_state():
    # одно отклонение, затем возвращение к подтверждённому — состояние не меняется
    t = StateTracker(confirm_count=2)
    t.observe(State.UNRESTRICTED)
    t.observe(State.UNRESTRICTED)
    assert t.current is State.UNRESTRICTED

    assert t.observe(State.NO_INTERNET) is None        # разовый сбой
    assert t.observe(State.UNRESTRICTED) is None       # возврат, но уже подтверждённое — не «новое»
    assert t.current is State.UNRESTRICTED


# --- confirm_count=1: подтверждение сразу -----------------------------------

def test_confirm_count_1_confirms_immediately():
    t = StateTracker(confirm_count=1)
    assert t.observe(State.WHITELIST) is State.WHITELIST
    assert t.current is State.WHITELIST
    assert t.observe(State.WHITELIST) is None  # уже подтверждено


def test_confirm_count_1_changes_immediately():
    t = StateTracker(confirm_count=1)
    t.observe(State.WHITELIST)
    assert t.observe(State.NO_INTERNET) is State.NO_INTERNET
    assert t.current is State.NO_INTERNET


# --- все 4 состояния проходят через трекер ----------------------------------

@pytest.mark.parametrize("state", list(State))
def test_all_states_can_be_confirmed(state):
    t = StateTracker(confirm_count=2)
    assert t.observe(state) is None
    assert t.observe(state) is state
    assert t.current is state
