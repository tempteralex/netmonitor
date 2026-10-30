"""Тесты для П6: notifier.Notifier

Seam: Notifier(notifications_cfg).notify(old_state, new_state)
Действия при смене состояния (порядок):
  1. toast (PowerShell)   — вынесен в _show_toast(text), патчим
  2. лог в файл           — реальная запись
  3. задержка notify_delay_sec (3000мс)
  4. звук (winsound)      — ОДИН сигнал (Alarm10.wav) на любое изменение статуса,
                            вынесен в _play_sound()

Порядок: toast → лог → задержка → звук.
Не лезем внутрь: только через публичный notify() и файл лога.
"""
from pathlib import Path

import pytest

from netmonitor.monitor import State
from netmonitor.notifier import Notifier
from netmonitor.config import NotificationsCfg


def _cfg(log_path: str, sound=True, toast=True, delay_sec=3):
    return NotificationsCfg(sound=sound, toast=toast, log_file=log_path,
                            notify_delay_sec=delay_sec)


# --- лог: записывается строка при смене состояния ---------------------------

def test_log_writes_transition_line(tmp_path):
    log_path = tmp_path / "monitor.log"
    n = Notifier(_cfg(str(log_path), delay_sec=0))
    n._show_toast = lambda text: None
    n._play_sound = lambda: None

    n.notify(old_state=State.UNRESTRICTED, new_state=State.NO_INTERNET)

    content = log_path.read_text(encoding="utf-8")
    assert "UNRESTRICTED" in content
    assert "NO_INTERNET" in content
    assert "->" in content or "→" in content


def test_log_appends_multiple_transitions(tmp_path):
    log_path = tmp_path / "monitor.log"
    n = Notifier(_cfg(str(log_path), delay_sec=0))
    n._show_toast = lambda text: None
    n._play_sound = lambda: None

    n.notify(None, State.UNRESTRICTED)
    n.notify(State.UNRESTRICTED, State.NO_INTERNET)
    n.notify(State.NO_INTERNET, State.UNRESTRICTED)

    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 3


# --- звук: ОДИН сигнал на любое изменение (без kind) ------------------------

def test_sound_played_on_transition_to_no_internet(tmp_path):
    n = Notifier(_cfg(str(tmp_path / "monitor.log"), delay_sec=0))
    calls = []
    n._show_toast = lambda text: None
    n._play_sound = lambda: calls.append(True)

    n.notify(None, State.NO_INTERNET)
    assert len(calls) == 1          # один сигнал


def test_sound_played_on_recovery(tmp_path):
    n = Notifier(_cfg(str(tmp_path / "monitor.log"), delay_sec=0))
    calls = []
    n._show_toast = lambda text: None
    n._play_sound = lambda: calls.append(True)

    n.notify(State.NO_INTERNET, State.UNRESTRICTED)
    assert len(calls) == 1          # тот же один сигнал


def test_sound_played_on_whitelist_transition(tmp_path):
    n = Notifier(_cfg(str(tmp_path / "monitor.log"), delay_sec=0))
    calls = []
    n._show_toast = lambda text: None
    n._play_sound = lambda: calls.append(True)

    n.notify(State.UNRESTRICTED, State.WHITELIST)
    assert len(calls) == 1


# --- toast: показывается с текстом нового состояния -------------------------

def test_toast_shown_with_state_label(tmp_path):
    n = Notifier(_cfg(str(tmp_path / "monitor.log"), delay_sec=0))
    shown = []
    n._show_toast = lambda text: shown.append(text)
    n._play_sound = lambda: None

    n.notify(None, State.NO_INTERNET)
    assert len(shown) == 1
    assert any(s in shown[0] for s in ("Интернета нет", "NO_INTERNET"))


# --- флаги выключения: звук/toast можно отключить --------------------------

def test_sound_disabled_no_call(tmp_path):
    cfg = _cfg(str(tmp_path / "m.log"), sound=False, delay_sec=0)
    n = Notifier(cfg)
    calls = []
    n._show_toast = lambda text: None
    n._play_sound = lambda: calls.append(True)

    n.notify(None, State.NO_INTERNET)
    assert calls == []


def test_toast_disabled_no_call(tmp_path):
    cfg = _cfg(str(tmp_path / "m.log"), toast=False, delay_sec=0)
    n = Notifier(cfg)
    shown = []
    n._show_toast = lambda text: shown.append(text)
    n._play_sound = lambda: None

    n.notify(None, State.NO_INTERNET)
    assert shown == []


def test_log_still_written_when_sound_and_toast_disabled(tmp_path):
    cfg = _cfg(str(tmp_path / "m.log"), sound=False, toast=False, delay_sec=0)
    n = Notifier(cfg)
    n._show_toast = lambda text: None
    n._play_sound = lambda: None

    n.notify(None, State.NO_INTERNET)
    lines = [l for l in Path(str(tmp_path / "m.log")).read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1


# --- порядок: toast → лог → задержка → звук --------------------------------

def test_notify_order_toast_then_delay_then_sound(tmp_path, monkeypatch):
    """Порядок: toast → лог → задержка → звук."""
    n = Notifier(_cfg(str(tmp_path / "monitor.log"), delay_sec=3))
    order = []
    n._show_toast = lambda text: order.append("toast")
    n._play_sound = lambda: order.append("sound")
    monkeypatch.setattr("netmonitor.notifier.time.sleep", lambda s: order.append("sleep"))

    n.notify(None, State.NO_INTERNET)
    assert order == ["toast", "sleep", "sound"]


def test_notify_sleeps_between_toast_and_sound(tmp_path, monkeypatch):
    n = Notifier(_cfg(str(tmp_path / "monitor.log"), delay_sec=3))
    n._show_toast = lambda text: None
    n._play_sound = lambda: None
    slept = []
    monkeypatch.setattr("netmonitor.notifier.time.sleep", lambda s: slept.append(s))

    n.notify(None, State.NO_INTERNET)
    assert slept == [3]             # пауза 3с между toast и звуком


def test_notify_no_sleep_when_delay_zero(tmp_path, monkeypatch):
    n = Notifier(_cfg(str(tmp_path / "monitor.log"), delay_sec=0))
    n._show_toast = lambda text: None
    n._play_sound = lambda: None
    slept = []
    monkeypatch.setattr("netmonitor.notifier.time.sleep", lambda s: slept.append(s))

    n.notify(None, State.NO_INTERNET)
    assert slept == []


# --- старое состояние None (старт) → тоже нотифицируем ----------------------

def test_first_confirmation_notifies(tmp_path):
    n = Notifier(_cfg(str(tmp_path / "monitor.log"), delay_sec=0))
    calls = []
    n._show_toast = lambda text: None
    n._play_sound = lambda: calls.append(True)

    n.notify(None, State.UNRESTRICTED)
    assert len(calls) == 1
