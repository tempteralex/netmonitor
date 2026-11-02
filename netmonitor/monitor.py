"""П4: Определение состояния интернета за одну итерацию.

Seam: compute_state(allowed_ok, blocked_ok, vpn_active) -> State — чистая функция.
Таблица состояний — в SPEC.md раздел 3.3. П7 (главный цикл) и П9 (CLI) добавляются
позже отдельными слайсами; здесь пока только логика состояния.
"""
from __future__ import annotations

import logging
import time
from enum import Enum

from netmonitor.checkers import is_host_available, is_vpn_active
from netmonitor.config import Config, load


class State(Enum):
    UNRESTRICTED = 1   # интернет без ограничений
    WITH_VPN = 2       # интернет без ограничений + VPN
    WHITELIST = 3      # ограниченный (белые списки)
    NO_INTERNET = 4    # интернета нет

    def label(self) -> str:
        return _LABELS[self]


_LABELS = {
    State.UNRESTRICTED: "Интернет без ограничений",
    State.WITH_VPN: "Интернет без ограничений (VPN)",
    State.WHITELIST: "Ограниченный интернет (белые списки)",
    State.NO_INTERNET: "Интернета нет",
}


def compute_state(allowed_ok: bool, blocked_ok: bool, vpn_active: bool) -> State:
    """Чистая функция по таблице из SPEC 3.3.

   allowed_ok  — хотя бы один разрешённый хост доступен
    blocked_ok  — хотя бы один запрещённый хост доступен
    vpn_active  — обнаружен VPN
    """
    if not allowed_ok:
        # нет ожидаемого белого хоста → нет сети (включая вырожденный blocked-only)
        return State.NO_INTERNET
    if not blocked_ok:
        # allowed есть, blocked нет → белый список (VPN не меняет)
        return State.WHITELIST
    # allowed и blocked оба доступны
    return State.WITH_VPN if vpn_active else State.UNRESTRICTED


# === П7: одна итерация и главный цикл ======================================

def _check_any(urls, connect_timeout, read_timeout) -> bool:
    """Хотя бы один URL доступен. Проверка параллельная (ThreadPoolExecutor),
    с общим таймаутом — зависший хост не блокирует результат от быстрого.

    Это важно при VPN/прокси, где часть хостов может висеть на таймауте:
    последовательная проверка делала бы суммарный таймаут, параллельная — максимум
    по одному.
    """
    urls = list(urls)
    if not urls:
        return False
    overall = connect_timeout + read_timeout + 1
    from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
    ex = ThreadPoolExecutor(max_workers=min(len(urls), 8))
    pending = set()
    try:
        pending = {ex.submit(is_host_available, u, connect_timeout, read_timeout) for u in urls}
        while pending:
            done, pending = wait(pending, timeout=overall, return_when=FIRST_COMPLETED)
            if not done:
                # ничего не завершилось за overall — все зависли, выходим
                break
            for fut in done:
                if fut.result():
                    return True
        return False
    finally:
        for f in pending:
            f.cancel()
        ex.shutdown(wait=False, cancel_futures=True)


def _run_iteration(cfg: Config, tracker, notifier, tray=None) -> State | None:
    """Одна итерация мониторинга. Возвращает подтверждённое состояние, если оно
    сменилось в этой итерации; иначе None. Может бросать исключения — их ловит main."""
    allowed_ok = _check_any(cfg.hosts.allowed, cfg.connect_timeout_sec, cfg.read_timeout_sec)
    blocked_ok = _check_any(cfg.hosts.blocked, cfg.connect_timeout_sec, cfg.read_timeout_sec)
    vpn_active = is_vpn_active(cfg.vpn)

    observed = compute_state(allowed_ok, blocked_ok, vpn_active)
    old = tracker.current                      # ДО observe — настоящее старое состояние
    confirmed = tracker.observe(observed)
    if confirmed is not None and confirmed != old:
        # Порядок при смене состояния: сначала смена значка в трее,
        # затем уведомление (toast → задержка → звук).
        if tray is not None:
            tray.update(confirmed)             # обновить иконку в трее
        notifier.notify(old, confirmed)        # toast → задержка → звук
    return confirmed


def main(config_path: str, tray=None) -> None:
    """Главный цикл мониторинга. Останавливается по KeyboardInterrupt (Ctrl-C).
    Ошибка одной итерации НЕ валит весь процесс — логируется и цикл продолжается.
    tray: опциональный TrayIcon для обновления иконки в трее при смене состояния.
    """
    cfg = load(config_path)
    from netmonitor.state_tracker import StateTracker
    from netmonitor.notifier import Notifier

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    log = logging.getLogger("netmonitor")

    tracker = StateTracker(confirm_count=cfg.confirm_count)
    notifier = Notifier(cfg.notifications)

    # запускаем трей в фоновом потоке, если передан
    if tray is not None:
        try:
            tray.start_detached()
        except Exception as e:
            log.warning("tray start failed: %r", e)

    log.info("NetMonitor started. interval=%ss confirm=%s", cfg.interval_sec, cfg.confirm_count)

    while True:
        try:
            _run_iteration(cfg, tracker, notifier, tray=tray)
        except KeyboardInterrupt:
            log.info("NetMonitor stopped")
            return
        except Exception as e:
            # ошибка одной итерации — не роняем процесс
            log.warning("iteration error: %r", e)
        try:
            time.sleep(cfg.interval_sec)
        except KeyboardInterrupt:
            log.info("NetMonitor stopped")
            return
    # при выходе — остановить трей
    if tray is not None:
        try:
            tray.stop()
        except Exception:
            pass
