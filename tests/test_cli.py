"""Тесты для П9: CLI — monitor_main(argv) -> int

Точка входа — тестируемая функция monitor_main(argv=None). Не sys.argv напрямую.
Флаги:
  --config <path>           путь к конфигу (обязателен для всех команд кроме --uninstall-startup)
  --check-once              разовая проверка: напечатать состояние и выйти (code 0)
  --install-startup         установить автозапуск для config (code 0)
  --uninstall-startup       удалить автозапуск (code 0)
  (без аргументов / --help) usage в stderr/stdout, код ненулевой

Возвращает exit code: 0 = успех, ненулевой = ошибка/usage.
"""
import textwrap

import pytest

from netmonitor import cli
from netmonitor.config import load
from netmonitor.monitor import State


def _make_cfg(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent("""
        interval_sec: 1
        confirm_count: 1
        hosts:
          allowed: ["https://a.example"]
          blocked: ["https://x.example"]
    """), encoding="utf-8")
    return p


# --- без аргументов → usage, ненулевой код ----------------------------------

def test_no_args_shows_usage_nonzero(tmp_path, capsys):
    code = cli.monitor_main([])
    out = capsys.readouterr().out + capsys.readouterr().err
    assert code != 0


def test_help_shows_usage(tmp_path, capsys):
    code = cli.monitor_main(["--help"])
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert code != 0
    assert "--config" in text or "usage" in text.lower()


# --- --check-once: печатает состояние, код 0 --------------------------------

def test_check_once_prints_state_and_exits_zero(tmp_path, capsys, monkeypatch):
    cfg_path = _make_cfg(tmp_path)
    # все хосты доступны, VPN выкл → UNRESTRICTED (confirm_count=1 → сразу подтверждается)
    monkeypatch.setattr("netmonitor.monitor.is_host_available", lambda url, c, r: True)
    monkeypatch.setattr("netmonitor.monitor.is_vpn_active", lambda vcfg: False)

    code = cli.monitor_main(["--check-once", "--config", str(cfg_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "UNRESTRICTED" in out or "Интернет без ограничений" in out


def test_check_once_prints_no_internet_when_all_fail(tmp_path, capsys, monkeypatch):
    cfg_path = _make_cfg(tmp_path)
    monkeypatch.setattr("netmonitor.monitor.is_host_available", lambda url, c, r: False)
    monkeypatch.setattr("netmonitor.monitor.is_vpn_active", lambda vcfg: False)

    code = cli.monitor_main(["--check-once", "--config", str(cfg_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "NO_INTERNET" in out or "Интернета нет" in out


def test_check_once_whitelist_when_blocked_unavailable(tmp_path, capsys, monkeypatch):
    cfg_path = _make_cfg(tmp_path)
    def fake(url, c, r):
        return "a.example" in url
    monkeypatch.setattr("netmonitor.monitor.is_host_available", fake)
    monkeypatch.setattr("netmonitor.monitor.is_vpn_active", lambda vcfg: False)

    code = cli.monitor_main(["--check-once", "--config", str(cfg_path)])
    out = capsys.readouterr().out
    assert code == 0
    assert "WHITELIST" in out or "белы" in out.lower()


# --- --check-once без --config → ошибка -------------------------------------

def test_check_once_without_config_is_error(tmp_path, capsys):
    code = cli.monitor_main(["--check-once"])
    assert code != 0


# --- --check-once с несуществующим конфигом → ошибка ------------------------

def test_check_once_missing_config_file_is_error(tmp_path, capsys):
    code = cli.monitor_main(["--check-once", "--config", str(tmp_path / "nope.yaml")])
    assert code != 0


# --- --install-startup создаёт лаунчер --------------------------------------

def test_install_startup_creates_launcher(tmp_path, monkeypatch, capsys):
    cfg_path = _make_cfg(tmp_path)
    # подменяем папку Startup на tmp_path, чтобы не лезть в систему
    monkeypatch.setattr("netmonitor.cli.default_startup_dir", lambda: str(tmp_path))
    # путь к target-скрипту (monitor_main) — используем реальный cli-модуль
    monkeypatch.setattr("netmonitor.cli._monitor_script_path", lambda: str(tmp_path / "monitor.py"))

    code = cli.monitor_main(["--install-startup", "--config", str(cfg_path)])
    assert code == 0
    launchers = [p for p in tmp_path.iterdir() if p.suffix == ".vbs"]
    assert len(launchers) == 1


def test_install_startup_without_config_is_error(tmp_path, capsys):
    code = cli.monitor_main(["--install-startup"])
    assert code != 0


# --- --uninstall-startup удаляет лаунчер ------------------------------------

def test_uninstall_startup_removes_launcher(tmp_path, monkeypatch, capsys):
    cfg_path = _make_cfg(tmp_path)
    monkeypatch.setattr("netmonitor.cli.default_startup_dir", lambda: str(tmp_path))
    monkeypatch.setattr("netmonitor.cli._monitor_script_path", lambda: str(tmp_path / "monitor.py"))

    # сначала установим
    cli.monitor_main(["--install-startup", "--config", str(cfg_path)])
    assert any(tmp_path.iterdir())

    code = cli.monitor_main(["--uninstall-startup"])
    assert code == 0
    assert not any(p.suffix == ".vbs" for p in tmp_path.iterdir())


def test_uninstall_startup_when_absent_returns_zero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("netmonitor.cli.default_startup_dir", lambda: str(tmp_path))
    monkeypatch.setattr("netmonitor.cli._monitor_script_path", lambda: str(tmp_path / "monitor.py"))

    code = cli.monitor_main(["--uninstall-startup"])
    assert code == 0  # отсутствие — не ошибка


# --- неизвестный флаг → ошибка ----------------------------------------------

def test_unknown_flag_is_error(tmp_path, capsys):
    code = cli.monitor_main(["--frobnicate"])
    assert code != 0
