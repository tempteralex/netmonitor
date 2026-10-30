"""П9: CLI — точка входа monitor.py.

Seam: monitor_main(argv=None) -> int  — тестируемая функция.
Команды:
  --config <path>           путь к конфигу
  --check-once              разовая проверка → напечатать состояние, выйти
  --install-startup         установить автозапуск
  --uninstall-startup       удалить автозапуск
  --help / (без аргументов) usage
Exit codes: 0 = успех, 2 = ошибка/usage.
"""
from __future__ import annotations

import sys
from pathlib import Path

from netmonitor import monitor as monitor_mod
from netmonitor.config import load
from netmonitor.startup import default_startup_dir, install_startup, uninstall_startup
from netmonitor.state_tracker import StateTracker
from netmonitor.notifier import Notifier


USAGE = """\
netmonitor — мониторинг наличия интернета.

Использование:
  python monitor.py --config <path>                  запустить мониторинг
  python monitor.py --check-once --config <path>     разовая проверка, печать состояния
  python monitor.py --install-startup --config <path>  установить автозапуск
  python monitor.py --uninstall-startup               удалить автозапуск
  python monitor.py --help                            эта справка
"""


def _monitor_script_path() -> str:
    """Путь к исполняемому скрипту monitor (для лаунчера автозапуска)."""
    # cli.py сам не запускает цикл; целевой скрипт — monitor.py рядом с пакетом
    here = Path(__file__).resolve().parent
    target = here / "monitor_main.py"
    if target.exists():
        return str(target)
    # fallback: __main__-стиль — используем -m netmonitor.cli
    return "-m netmonitor.cli"


def _parse(argv: list[str]) -> dict:
    """Простой парсер флагов. Возвращает dict или поднимает ValueError."""
    opts = {
        "config": None,
        "check_once": False,
        "install_startup": False,
        "uninstall_startup": False,
        "help": False,
    }
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            opts["help"] = True
        elif a == "--config":
            if i + 1 >= len(argv):
                raise ValueError("--config требует значение")
            opts["config"] = argv[i + 1]
            i += 1
        elif a == "--check-once":
            opts["check_once"] = True
        elif a == "--install-startup":
            opts["install_startup"] = True
        elif a == "--uninstall-startup":
            opts["uninstall_startup"] = True
        else:
            raise ValueError(f"неизвестный аргумент: {a}")
        i += 1
    return opts


def monitor_main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2

    try:
        opts = _parse(argv)
    except ValueError as e:
        print(f"Ошибка: {e}\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    if opts["help"]:
        print(USAGE)
        return 2  # help — это не «успех», а показ usage

    # --- uninstall-startup (config не нужен) --------------------------------
    if opts["uninstall_startup"]:
        removed = uninstall_startup(_monitor_script_path(), startup_dir=default_startup_dir())
        print("Автозапуск удалён." if removed else "Автозапуск не был установлен.")
        return 0

    # --- все остальные команды требуют --config ------------------------------
    if not opts["config"]:
        print("Ошибка: --config обязателен для этой команды.\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    try:
        cfg = load(opts["config"])
    except Exception as e:
        print(f"Ошибка загрузки конфига: {e}", file=sys.stderr)
        return 2

    # --- install-startup ----------------------------------------------------
    if opts["install_startup"]:
        launcher = install_startup(
            _monitor_script_path(), opts["config"], startup_dir=default_startup_dir()
        )
        print(f"Автозапуск установлен: {launcher}")
        return 0

    # --- check-once: разовая проверка ---------------------------------------
    if opts["check_once"]:
        state = _check_once(cfg)
        print(f"Состояние: {state.name} ({state.label()})")
        return 0

    # --- по умолчанию: запуск мониторинга (главный цикл) --------------------
    tray = None
    if not opts["no_tray"]:
        try:
            from netmonitor.tray import TrayIcon
            tray = TrayIcon()
        except Exception as e:
            print(f"Внимание: трей недоступен ({e}). Запуск без иконки.", file=sys.stderr)
    try:
        monitor_mod.main(opts["config"], tray=tray)
    except KeyboardInterrupt:
        return 0
    finally:
        if tray is not None:
            try:
                tray.stop()
            except Exception:
                pass
    return 0


def _check_once(cfg) -> "State":
    """Одна итерация без подтверждения (confirm_count=1 эквивалент) для отладки."""
    allowed_ok = monitor_mod._check_any(
        cfg.hosts.allowed, cfg.connect_timeout_sec, cfg.read_timeout_sec
    )
    blocked_ok = monitor_mod._check_any(
        cfg.hosts.blocked, cfg.connect_timeout_sec, cfg.read_timeout_sec
    )
    vpn_active = monitor_mod.is_vpn_active(cfg.vpn)
    return monitor_mod.compute_state(allowed_ok, blocked_ok, vpn_active)


if __name__ == "__main__":
    sys.exit(monitor_main())
