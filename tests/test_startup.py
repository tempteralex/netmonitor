"""Тесты для П8: startup.install_startup / uninstall_startup / default_startup_dir

Seam:
  default_startup_dir() -> str
  install_startup(target_script, config_path, pythonw=None, startup_dir=None) -> Path
  uninstall_startup(target_script, startup_dir=None) -> bool

Стратегия: startup_dir параметризуется → в тестах передаём tmp_path, не трогаем
реальную папку Startup системы. Проверяем, что файл создаётся с правильным
содержимым (запуск pythonw monitor.py --config ...), и что uninstall его удаляет.
"""
from pathlib import Path

import pytest

from netmonitor import startup


# --- default_startup_dir указывает на папку Startup -------------------------

def test_default_startup_dir_contains_startup():
    d = startup.default_startup_dir()
    assert "Startup" in d
    # путь должен существовать в системе (APPDATA\...\Startup)
    assert Path(d).exists()


# --- install создаёт файл в указанной папке ---------------------------------

def test_install_creates_launcher_file(tmp_path):
    target = str(tmp_path.parent / "monitor.py")  # любой путь
    cfg = str(tmp_path / "config.yaml")
    out = startup.install_startup(target, cfg, startup_dir=str(tmp_path))

    assert isinstance(out, Path)
    assert out.exists()
    assert out.parent == tmp_path


# --- содержимое лаунчера: pythonw + monitor.py + --config -------------------

def test_launcher_content_invokes_pythonw_with_config(tmp_path):
    target = "D:/work/job/netmonitor/monitor_main.py"
    cfg = "D:/work/job/config.yaml"
    out = startup.install_startup(target, cfg, startup_dir=str(tmp_path))

    content = out.read_text(encoding="utf-8")
    # должен запускать pythonw (без окна консоли)
    assert "pythonw" in content.lower() or "python" in content.lower()
    # путь к скрипту и конфигу присутствуют
    assert target in content or Path(target).name in content
    assert cfg in content
    assert "--config" in content


# --- имя файла лаунчера детерминировано по имени скрипта --------------------

def test_launcher_filename_based_on_target(tmp_path):
    target = "D:/work/job/run_monitor.py"
    out = startup.install_startup(target, "cfg.yaml", startup_dir=str(tmp_path))
    # имя содержит имя целевого скрипта
    assert "run_monitor" in out.name


# --- повторный install не создаёт дубликатов (idempotent) -------------------

def test_install_is_idempotent(tmp_path):
    target = str(tmp_path.parent / "monitor.py")
    cfg = str(tmp_path / "config.yaml")
    out1 = startup.install_startup(target, cfg, startup_dir=str(tmp_path))
    out2 = startup.install_startup(target, cfg, startup_dir=str(tmp_path))
    assert out1 == out2
    # ровно один файл лаунчера
    launchers = [p for p in tmp_path.iterdir()]
    assert len(launchers) == 1


# --- uninstall удаляет созданный лаунчер ------------------------------------

def test_uninstall_removes_launcher(tmp_path):
    target = str(tmp_path.parent / "monitor.py")
    cfg = str(tmp_path / "config.yaml")
    startup.install_startup(target, cfg, startup_dir=str(tmp_path))
    assert any(tmp_path.iterdir())  # лаунчер создан

    removed = startup.uninstall_startup(target, startup_dir=str(tmp_path))
    assert removed is True
    assert not any(tmp_path.iterdir())  # папка пуста


# --- uninstall возвращает False если лаунчера не было -----------------------

def test_uninstall_returns_false_when_absent(tmp_path):
    target = str(tmp_path.parent / "monitor.py")
    removed = startup.uninstall_startup(target, startup_dir=str(tmp_path))
    assert removed is False


# --- uninstall не трогает другие файлы в папке ------------------------------

def test_uninstall_only_removes_its_own_launcher(tmp_path):
    target = str(tmp_path.parent / "monitor.py")
    cfg = str(tmp_path / "config.yaml")
    startup.install_startup(target, cfg, startup_dir=str(tmp_path))
    # создаём чужой файл
    other = tmp_path / "other_launcher.vbs"
    other.write_text("dummy", encoding="utf-8")

    startup.uninstall_startup(target, startup_dir=str(tmp_path))

    remaining = [p.name for p in tmp_path.iterdir()]
    assert "other_launcher.vbs" in remaining


# --- install_startup_if_absent: idempotent авто-добавление ------------------

def test_install_if_absent_creates_when_missing(tmp_path):
    target = str(tmp_path / "monitor.py")
    cfg = str(tmp_path / "config.yaml")
    result = startup.install_startup_if_absent(target, cfg, startup_dir=str(tmp_path))
    assert result is not None
    assert result.exists()


def test_install_if_absent_returns_none_when_exists(tmp_path):
    target = str(tmp_path / "monitor.py")
    cfg = str(tmp_path / "config.yaml")
    # первый вызов — создаёт
    first = startup.install_startup_if_absent(target, cfg, startup_dir=str(tmp_path))
    assert first is not None
    # второй вызов — уже есть, ничего не делает
    second = startup.install_startup_if_absent(target, cfg, startup_dir=str(tmp_path))
    assert second is None

    launchers = [p for p in tmp_path.iterdir() if p.suffix == ".vbs"]
    assert len(launchers) == 1   # без дубликатов
