"""П2: Проверка доступности хоста.

Seam: is_host_available(url, connect_timeout, read_timeout) -> bool
HTTP GET. True если получили любой HTTP-ответ (TCP установлен + сервер ответил).
False на сетевой ошибке / таймауте / 5xx.
"""
from __future__ import annotations

import psutil
import requests


def is_host_available(url: str, connect_timeout: int, read_timeout: int) -> bool:
    try:
        resp = requests.get(url, timeout=(connect_timeout, read_timeout), allow_redirects=True)
    except (requests.RequestException, OSError):
        return False
    # 2xx/3xx/4xx → сервер ответил, соединение установлено → считаем доступным.
    # 5xx → сервер жив, но сам себя считает сломанным → недоступен.
    return resp.status_code < 500


# === П3: обнаружение VPN ====================================================

def _interface_is_vpn(name: str, patterns: list[str], excludes: list[str]) -> bool:
    """True если имя интерфейса содержит (case-insensitive) один из patterns
    и НЕ содержит ни одного из excludes."""
    low = name.lower()
    if any(ex.lower() in low for ex in excludes):
        return False
    return any(p.lower() in low for p in patterns)


def _fetch_external_ip(service_url: str) -> str:
    """Запрос внешнего IP у публичного сервиса. Может бросать исключения.
    Сохранён для возможного отладочного использования, но is_vpn_active его не вызывает.
    """
    resp = requests.get(service_url, timeout=(5, 5))
    resp.raise_for_status()
    return resp.text.strip()


def is_vpn_active(vpn_cfg) -> bool:
    """VPN активен если найден сетевой интерфейс, попадающий под vpn-паттерны (psutil).

    IP-сравнение УБРАНО: провайдерский IP динамический, поэтому опираемся только
    на наличие VPN-адаптера (TAP/TUN/Wintun/...). Это надёжнее и не зависит от сети.
    """
    try:
        addrs = psutil.net_if_addrs()
    except Exception:
        return False
    for iface_name in addrs:
        if _interface_is_vpn(iface_name, vpn_cfg.interface_patterns, vpn_cfg.exclude_interface_patterns):
            return True
    return False
