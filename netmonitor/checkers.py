"""П2: Проверка доступности хоста.

Seam: is_host_available(url, connect_timeout, read_timeout) -> bool
HTTP GET. True если получили любой HTTP-ответ (TCP установлен + сервер ответил).
False на сетевой ошибке / таймауте / 5xx.
"""
from __future__ import annotations

import psutil
import requests
import winreg


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


def _is_system_proxy_enabled() -> bool:
    """True если в реестре Windows включён системный прокси
    (HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings: ProxyEnable=1).

    Многие VPN (Warp, расширения, прокси-клиенты) не создают сетевой адаптер,
    а просто включают системный прокси — это надёжный признак такого VPN.
    """
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
    except OSError:
        return False
    try:
        value, _ = winreg.QueryValueEx(key, "ProxyEnable")
        return bool(value)
    except (FileNotFoundError, OSError):
        return False
    finally:
        try:
            winreg.CloseKey(key)
        except OSError:
            pass


def is_vpn_active(vpn_cfg) -> bool:
    """VPN активен если выполняется хотя бы одно:
      1) найден сетевой интерфейс под vpn-паттернами (TAP/TUN/Wintun/...), ИЛИ
      2) включён системный прокси Windows (HKCU ProxyEnable=1).

    IP-сравнение убрано: провайдерский IP динамический, ненадёжно.
    Признак 2 покрывает VPN-клиенты, которые не создают адаптер (Warp, прокси).
    """
    # (1) проверка интерфейсов
    try:
        addrs = psutil.net_if_addrs()
    except Exception:
        addrs = {}
    for iface_name in addrs:
        if _interface_is_vpn(iface_name, vpn_cfg.interface_patterns, vpn_cfg.exclude_interface_patterns):
            return True

    # (2) системный прокси
    if _is_system_proxy_enabled():
        return True

    return False
