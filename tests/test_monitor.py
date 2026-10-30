"""Тесты для П4: monitor.compute_state(allowed_ok, blocked_ok, vpn_active) -> StateEnum

Чистая функция от явных параметров — без моков, без сети.
Таблица из SPEC раздел 3.3:

  allowed | blocked | vpn | state
  --------+---------+-----+-------
  F       | F       | *   | 4 (нет сети)
  T       | F       | *   | 3 (белый список)
  T       | T       | T   | 2 (интернет + VPN)
  T       | T       | F   | 1 (интернет без ограничений)
  F       | T       | *   | 4 (нет ожидаемого белого хоста → нет сети)
"""
import pytest

from netmonitor.monitor import compute_state, State


# --- состояние 4: ничего не доступно ----------------------------------------

def test_state_4_when_nothing_available():
    assert compute_state(allowed_ok=False, blocked_ok=False, vpn_active=False) is State.NO_INTERNET
    assert compute_state(allowed_ok=False, blocked_ok=False, vpn_active=True) is State.NO_INTERNET


# --- состояние 3: белый список (allowed есть, blocked нет) ------------------

def test_state_3_whitelist_when_allowed_only():
    assert compute_state(allowed_ok=True, blocked_ok=False, vpn_active=False) is State.WHITELIST
    # VPN не меняет состояния 3
    assert compute_state(allowed_ok=True, blocked_ok=False, vpn_active=True) is State.WHITELIST


# --- состояние 2: интернет + VPN --------------------------------------------

def test_state_2_when_all_available_and_vpn():
    assert compute_state(allowed_ok=True, blocked_ok=True, vpn_active=True) is State.WITH_VPN


# --- состояние 1: интернет без ограничений ----------------------------------

def test_state_1_when_all_available_no_vpn():
    assert compute_state(allowed_ok=True, blocked_ok=True, vpn_active=False) is State.UNRESTRICTED


# --- вырожденный случай: blocked есть, allowed нет → состояние 4 ------------

def test_state_4_when_blocked_only_no_allowed():
    assert compute_state(allowed_ok=False, blocked_ok=True, vpn_active=False) is State.NO_INTERNET
    assert compute_state(allowed_ok=False, blocked_ok=True, vpn_active=True) is State.NO_INTERNET


# --- все 8 комбинаций соответствуют таблице (parametrized sanity) -----------

@pytest.mark.parametrize("allowed,blocked,vpn,expected", [
    (False, False, False, State.NO_INTERNET),
    (False, False, True,  State.NO_INTERNET),
    (True,  False, False, State.WHITELIST),
    (True,  False, True,  State.WHITELIST),
    (True,  True,  False, State.UNRESTRICTED),
    (True,  True,  True,  State.WITH_VPN),
    (False, True,  False, State.NO_INTERNET),
    (False, True,  True,  State.NO_INTERNET),
])
def test_full_truth_table(allowed, blocked, vpn, expected):
    assert compute_state(allowed_ok=allowed, blocked_ok=blocked, vpn_active=vpn) is expected
