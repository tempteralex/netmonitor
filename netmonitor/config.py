"""П1: Загрузка и валидация конфигурации.

Seam: load(path) -> Config. Читает YAML, заполняет дефолты, валидирует.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class HostsCfg:
    allowed: list[str]
    blocked: list[str]


@dataclass
class VpnCfg:
    interface_patterns: list[str]
    exclude_interface_patterns: list[str]
    # IP-сравнение убрано: провайдерский IP динамический, определение только по интерфейсам


@dataclass
class NotificationsCfg:
    sound: bool
    toast: bool
    log_file: str
    notify_delay_sec: int   # пауза ПОСЛЕ уведомления (мс→сек), чтобы не спамить


@dataclass
class Config:
    interval_sec: int
    connect_timeout_sec: int
    read_timeout_sec: int
    confirm_count: int
    hosts: HostsCfg
    vpn: VpnCfg
    notifications: NotificationsCfg


# --- дефолты из SPEC раздел 5 ------------------------------------------------

_DEFAULTS: dict = {
    "interval_sec": 6,
    "connect_timeout_sec": 5,
    "read_timeout_sec": 5,
    "confirm_count": 2,
    "hosts": {
        "allowed": [
            "https://www.gosuslugi.ru",
            "https://online.sberbank.ru",
        ],
        "blocked": [
            "https://www.youtube.com",
            "https://twitter.com",
        ],
    },
    "vpn": {
        "interface_patterns": ["TAP", "TUN", "Wintun", "wg", "OpenVPN", "vpn"],
        "exclude_interface_patterns": ["Hyper-V", "VirtualBox", "Loopback"],
    },
    "notifications": {
        "sound": True,
        "toast": True,
        "log_file": "monitor.log",
        "notify_delay_sec": 3,   # 3000мс пауза после уведомления
        "sound_file": r"C:\Windows\Media\Alarm10.wav",
    },
}


def _merge(defaults: dict, override: dict) -> dict:
    """Глубокое слияние: override побеждает, дефолты заполняют пропуски."""
    out = dict(defaults)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _validate(data: dict) -> None:
    if not isinstance(data["interval_sec"], int) or data["interval_sec"] < 1:
        raise ValueError(f"interval_sec must be a positive int, got {data['interval_sec']!r}")
    if not isinstance(data["connect_timeout_sec"], int) or data["connect_timeout_sec"] < 1:
        raise ValueError(f"connect_timeout_sec must be a positive int")
    if not isinstance(data["read_timeout_sec"], int) or data["read_timeout_sec"] < 1:
        raise ValueError(f"read_timeout_sec must be a positive int")
    if not isinstance(data["confirm_count"], int) or data["confirm_count"] < 1:
        raise ValueError(f"confirm_count must be >= 1, got {data['confirm_count']!r}")
    if not data["hosts"]["allowed"]:
        raise ValueError("hosts.allowed must not be empty")
    if not data["hosts"]["blocked"]:
        raise ValueError("hosts.blocked must not be empty")
    if not isinstance(data["notifications"]["notify_delay_sec"], int) or data["notifications"]["notify_delay_sec"] < 0:
        raise ValueError("notify_delay_sec must be a non-negative int")


def load(path: str | Path) -> Config:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config file not found: {p}")

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("config root must be a mapping")

    merged = _merge(_DEFAULTS, raw)
    _validate(merged)

    return Config(
        interval_sec=merged["interval_sec"],
        connect_timeout_sec=merged["connect_timeout_sec"],
        read_timeout_sec=merged["read_timeout_sec"],
        confirm_count=merged["confirm_count"],
        hosts=HostsCfg(
            allowed=list(merged["hosts"]["allowed"]),
            blocked=list(merged["hosts"]["blocked"]),
        ),
        vpn=VpnCfg(
            interface_patterns=list(merged["vpn"]["interface_patterns"]),
            exclude_interface_patterns=list(merged["vpn"]["exclude_interface_patterns"]),
        ),
        notifications=NotificationsCfg(
            sound=merged["notifications"]["sound"],
            toast=merged["notifications"]["toast"],
            log_file=merged["notifications"]["log_file"],
            notify_delay_sec=merged["notifications"]["notify_delay_sec"],
        ),
    )
