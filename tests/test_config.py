"""Тесты для П1: config.load(path) — загрузка, валидация, дефолты.

Seam: netmonitor.config.load(path) -> Config
  - загружает YAML
  - заполняет дефолты для отсутствующих полей
  - валидирует типы/значения → поднимает понятную ошибку при невалидном
Не лезем внутрь: проверяем только через публичный load() и поля возвращённого объекта.
"""
import textwrap
from pathlib import Path

import pytest

from netmonitor.config import load, Config


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# --- загрузка полного конфига: все поля доступны ----------------------------

def test_load_full_config_returns_config_with_all_fields(tmp_path):
    cfg_path = _write(tmp_path, "config.yaml", """
        interval_sec: 5
        connect_timeout_sec: 4
        read_timeout_sec: 4
        confirm_count: 3
        hosts:
          allowed:
            - https://a.example
            - https://b.example
          blocked:
            - https://x.example
        vpn:
          interface_patterns: ["TAP", "Wintun"]
          exclude_interface_patterns: ["Hyper-V"]
          external_ip_service: "https://api.ipify.org"
        notifications:
          sound: true
          toast: true
          log_file: "monitor.log"
    """)
    cfg = load(cfg_path)

    assert isinstance(cfg, Config)
    assert cfg.interval_sec == 5
    assert cfg.connect_timeout_sec == 4
    assert cfg.read_timeout_sec == 4
    assert cfg.confirm_count == 3
    assert cfg.hosts.allowed == ["https://a.example", "https://b.example"]
    assert cfg.hosts.blocked == ["https://x.example"]
    assert cfg.vpn.interface_patterns == ["TAP", "Wintun"]
    assert cfg.notifications.sound is True
    assert cfg.notifications.log_file == "monitor.log"


# --- дефолты для отсутствующих полей ----------------------------------------

def test_load_empty_yaml_uses_defaults(tmp_path):
    cfg_path = _write(tmp_path, "config.yaml", "{}\n")
    cfg = load(cfg_path)

    # дефолты из SPEC раздел 5
    assert cfg.interval_sec == 6
    assert cfg.connect_timeout_sec == 5
    assert cfg.read_timeout_sec == 5
    assert cfg.confirm_count == 2
    # дефолтные хосты не пустые
    assert len(cfg.hosts.allowed) >= 1
    assert len(cfg.hosts.blocked) >= 1
    assert cfg.notifications.sound is True
    assert cfg.notifications.toast is True


# --- валидация: отрицательный interval -------------------------------------

def test_load_negative_interval_raises(tmp_path):
    cfg_path = _write(tmp_path, "config.yaml", "interval_sec: -1\n")
    with pytest.raises(ValueError):
        load(cfg_path)


# --- валидация: confirm_count < 1 ------------------------------------------

def test_load_zero_confirm_count_raises(tmp_path):
    cfg_path = _write(tmp_path, "config.yaml", "confirm_count: 0\n")
    with pytest.raises(ValueError):
        load(cfg_path)


# --- валидация: пустой список allowed хостов --------------------------------

def test_load_empty_allowed_hosts_raises(tmp_path):
    cfg_path = _write(tmp_path, "config.yaml", """
        hosts:
          allowed: []
          blocked: ["https://x.example"]
    """)
    with pytest.raises(ValueError):
        load(cfg_path)


# --- отсутствующий файл → понятная ошибка -----------------------------------

def test_load_missing_file_raises_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError):
        load(tmp_path / "nope.yaml")
