"""Тесты для П7: monitor._run_iteration и monitor.main

Seam 1: _run_iteration(cfg, tracker, notifier) -> State | None
  одна итерация: проверяет хосты + VPN, считает состояние, гоняет через tracker,
  при подтверждённой смене вызывает notifier. Возвращает подтверждённое состояние
  (если сменилось в этой итерации) или None.

Seam 2: main(config_path) -> None
  бесконечный цикл с time.sleep(interval). Останавливается по KeyboardInterrupt.
  Ошибка одной итерации НЕ валит весь процесс — цикл продолжается.

Стратегия: патчим сетевые границы (is_host_available, is_vpn_active), time.sleep.
"""
import pytest

from netmonitor import monitor
from netmonitor.monitor import _run_iteration, main, State
from netmonitor.state_tracker import StateTracker
from netmonitor.notifier import Notifier
from netmonitor.config import load


# === Seam 1: _run_iteration =================================================

def _make_cfg(tmp_path):
    # минимальный валидный конфиг через load с дефолтами
    import textwrap
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent("""
        interval_sec: 1
        confirm_count: 2
        hosts:
          allowed: ["https://a.example"]
          blocked: ["https://x.example"]
        notifications:
          log_file: "monitor.log"
    """), encoding="utf-8")
    return load(p)


def test_iteration_no_change_when_state_not_confirmed(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    # все хосты доступны, VPN выкл → состояние UNRESTRICTED, но confirm_count=2,
    # одна итерация не подтверждает смену (current был None)
    monkeypatch.setattr(monitor, "is_host_available", lambda url, c, r: True)
    monkeypatch.setattr(monitor, "is_vpn_active", lambda vcfg: False)

    tracker = StateTracker(confirm_count=cfg.confirm_count)
    n = Notifier(cfg.notifications)
    n._play_sound = lambda: None
    n._show_toast = lambda t: None
    notified = []
    n.notify = lambda old, new: notified.append((old, new))

    result = _run_iteration(cfg, tracker, n)
    # первая итерация — streak=1, недостаточно для подтверждения → notify не звался
    assert result is None
    assert notified == []
    assert tracker.current is None


def test_iteration_confirms_after_n_and_notifies(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    monkeypatch.setattr(monitor, "is_host_available", lambda url, c, r: True)
    monkeypatch.setattr(monitor, "is_vpn_active", lambda vcfg: False)

    tracker = StateTracker(confirm_count=cfg.confirm_count)
    n = Notifier(cfg.notifications)
    n._play_sound = lambda: None
    n._show_toast = lambda t: None
    notified = []
    n.notify = lambda old, new: notified.append((old, new))

    _run_iteration(cfg, tracker, n)           # streak 1 — нет
    result = _run_iteration(cfg, tracker, n)  # streak 2 → подтверждено
    assert result is State.UNRESTRICTED
    assert notified == [(None, State.UNRESTRICTED)]
    assert tracker.current is State.UNRESTRICTED


def test_iteration_uses_blocked_availability_for_whitelist(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    # allowed доступен, blocked нет, VPN выкл → WHITELIST
    def fake_avail(url, c, r):
        return "a.example" in url
    monkeypatch.setattr(monitor, "is_host_available", fake_avail)
    monkeypatch.setattr(monitor, "is_vpn_active", lambda vcfg: False)

    tracker = StateTracker(confirm_count=1)  # чтобы подтвердилось сразу
    n = Notifier(cfg.notifications)
    n._play_sound = lambda: None
    n._show_toast = lambda t: None
    notified = []
    n.notify = lambda old, new: notified.append((old, new))

    _run_iteration(cfg, tracker, n)
    assert tracker.current is State.WHITELIST
    assert notified == [(None, State.WHITELIST)]


def test_iteration_no_internet_when_all_hosts_fail(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    monkeypatch.setattr(monitor, "is_host_available", lambda url, c, r: False)
    monkeypatch.setattr(monitor, "is_vpn_active", lambda vcfg: False)

    tracker = StateTracker(confirm_count=1)
    n = Notifier(cfg.notifications)
    n._play_sound = lambda: None
    n._show_toast = lambda t: None

    _run_iteration(cfg, tracker, n)
    assert tracker.current is State.NO_INTERNET


def test_iteration_order_tray_then_notify(tmp_path, monkeypatch):
    """Порядок при смене состояния: tray.update → notifier.notify (toast→звук)."""
    cfg = _make_cfg(tmp_path)
    monkeypatch.setattr(monitor, "is_host_available", lambda url, c, r: True)
    monkeypatch.setattr(monitor, "is_vpn_active", lambda vcfg: False)

    tracker = StateTracker(confirm_count=1)
    n = Notifier(cfg.notifications)
    n._play_sound = lambda: None
    n._show_toast = lambda t: None

    order = []
    class _TrayStub:
        def update(self, state):
            order.append("tray")
        def start_detached(self):
            pass
        def stop(self):
            pass
    tray = _TrayStub()
    # подменяем notify, чтобы зафиксировать момент вызова
    n.notify = lambda old, new: order.append("notify")

    _run_iteration(cfg, tracker, n, tray=tray)
    assert order == ["tray", "notify"]   # сначала трей, потом уведомление


def test_iteration_passes_real_old_state_on_change(tmp_path, monkeypatch):
    """При смене подтверждённого состояния notify получает настоящее old_state,
    а не None. SPEC: лог пишет old -> new."""
    cfg = _make_cfg(tmp_path)
    monkeypatch.setattr(monitor, "is_host_available", lambda url, c, r: True)
    monkeypatch.setattr(monitor, "is_vpn_active", lambda vcfg: False)

    tracker = StateTracker(confirm_count=1)
    n = Notifier(cfg.notifications)
    n._play_sound = lambda: None
    n._show_toast = lambda t: None
    notified = []
    n.notify = lambda old, new: notified.append((old, new))

    # 1-я итерация: подтверждается UNRESTRICTED, old=None
    _run_iteration(cfg, tracker, n)
    assert notified == [(None, State.UNRESTRICTED)]

    # меняем условия: всё упало → NO_INTERNET, old должно быть UNRESTRICTED
    monkeypatch.setattr(monitor, "is_host_available", lambda url, c, r: False)
    _run_iteration(cfg, tracker, n)
    assert notified[-1] == (State.UNRESTRICTED, State.NO_INTERNET)


# === Seam 2: main — цикл ====================================================

def test_main_stops_on_keyboard_interrupt(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    # sleep бросает сразу KeyboardInterrupt → цикл выходит
    monkeypatch.setattr(monitor.time, "sleep", lambda s: (_ for _ in ()).throw(KeyboardInterrupt()))
    monkeypatch.setattr(monitor, "is_host_available", lambda url, c, r: True)
    monkeypatch.setattr(monitor, "is_vpn_active", lambda vcfg: False)

    # должно выйти без ошибки
    main(str(cfg_path := (tmp_path / "config.yaml")))


def test_main_survives_iteration_error_and_continues(tmp_path, monkeypatch):
    """Ошибка в одной итерации НЕ валит весь процесс — цикл продолжается, потом KeyboardInterrupt."""
    cfg = _make_cfg(tmp_path)
    cfg_path = tmp_path / "config.yaml"

    calls = {"iter": 0}

    def fake_avail(url, c, r):
        calls["iter"] += 1
        if calls["iter"] == 1:
            raise RuntimeError("boom in first iteration")
        return True

    monkeypatch.setattr(monitor, "is_host_available", fake_avail)
    monkeypatch.setattr(monitor, "is_vpn_active", lambda vcfg: False)

    # sleep: первый раз проходит, второй — KeyboardInterrupt
    def fake_sleep(s):
        if calls["iter"] >= 2:
            raise KeyboardInterrupt()
    monkeypatch.setattr(monitor.time, "sleep", fake_sleep)

    # не должно бросить
    main(str(cfg_path))
    assert calls["iter"] >= 2  # первая упала, вторая прошла, потом вышли


def test_main_runs_until_keyboard_interrupt_multiple_iterations(tmp_path, monkeypatch):
    cfg = _make_cfg(tmp_path)
    cfg_path = tmp_path / "config.yaml"

    iterations = {"n": 0}

    monkeypatch.setattr(monitor, "is_host_available", lambda url, c, r: True)
    monkeypatch.setattr(monitor, "is_vpn_active", lambda vcfg: False)
    # Считаем итерации через обёртку _run_iteration; остановка через sleep.
    real_run = monitor._run_iteration

    def counted_run(cfg, tracker, notifier, tray=None):
        iterations["n"] += 1
        return real_run(cfg, tracker, notifier, tray=tray)

    monkeypatch.setattr(monitor, "_run_iteration", counted_run)

    def fake_sleep(s):
        if iterations["n"] >= 3:
            raise KeyboardInterrupt()
    monkeypatch.setattr(monitor.time, "sleep", fake_sleep)

    main(str(cfg_path))
    assert iterations["n"] == 3
