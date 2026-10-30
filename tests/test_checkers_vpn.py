"""Тесты для П3: checkers.is_vpn_active(vpn_cfg) -> bool + _interface_is_vpn

Seam 1 (чистая логика, без моков): _interface_is_vpn(name, patterns, excludes) -> bool
  - имя попадает под один из patterns (case-insensitive substring) И не под excludes → True

Seam 2 (внешняя граница): is_vpn_active(vpn_cfg) -> bool
  - True если найден VPN-интерфейс через psutil.net_if_addrs()
  - IP-сравнение УБРАНО (провайдерский IP динамический — ненадёжно).
    Опираемся ТОЛЬКО на наличие VPN-адаптера (TAP/TUN/Wintun/...).
  - патчим psutil.net_if_addrs — не лезем в реальную сеть
"""
import pytest

from netmonitor.checkers import is_vpn_active, _interface_is_vpn, _is_system_proxy_enabled
from netmonitor.config import VpnCfg


def _vpn_cfg():
    return VpnCfg(
        interface_patterns=["TAP", "TUN", "Wintun", "wg", "OpenVPN", "vpn"],
        exclude_interface_patterns=["Hyper-V", "VirtualBox", "Loopback"],
    )


# === Seam 1: чистая логика сопоставления имени интерфейса ==================

@pytest.mark.parametrize("name", ["TAP-Windows Adapter", "wintun-userspace", "OpenVPN", "VPN-conn", "wg0"])
def test_interface_matches_vpn_patterns(name):
    assert _interface_is_vpn(name, ["TAP", "TUN", "Wintun", "wg", "OpenVPN", "vpn"],
                              ["Hyper-V", "VirtualBox", "Loopback"]) is True


@pytest.mark.parametrize("name", ["Ethernet", "Wi-Fi", "Loopback Pseudo-Interface", "Local Area Connection"])
def test_interface_does_not_match(name):
    assert _interface_is_vpn(name, ["TAP", "TUN", "Wintun", "wg", "OpenVPN", "vpn"],
                              ["Hyper-V", "VirtualBox", "Loopback"]) is False


def test_interface_excluded_even_if_matches_pattern():
    # попадает под "vpn" в имени, но исключён Hyper-V
    assert _interface_is_vpn("Hyper-V VPN Bridge", ["vpn"], ["Hyper-V"]) is False


def test_interface_case_insensitive():
    assert _interface_is_vpn("openvpn-adapter", ["OpenVPN"], []) is True
    assert _interface_is_vpn("WINTUN", ["wintun"], []) is True


def test_interface_empty_patterns_never_matches():
    assert _interface_is_vpn("TAP-Adapter", [], []) is False


# === Seam 2: is_vpn_active — только по интерфейсам =========================

def test_vpn_active_when_vpn_interface_present(monkeypatch):
    fake_addrs = {
        "Ethernet": [],
        "OpenVPN TAP": [],
    }
    monkeypatch.setattr("netmonitor.checkers.psutil.net_if_addrs", lambda: fake_addrs)

    assert is_vpn_active(_vpn_cfg()) is True


def test_vpn_inactive_when_no_vpn_interface(monkeypatch):
    fake_addrs = {"Ethernet": [], "Wi-Fi": []}
    monkeypatch.setattr("netmonitor.checkers.psutil.net_if_addrs", lambda: fake_addrs)

    assert is_vpn_active(_vpn_cfg()) is False


def test_vpn_inactive_with_only_excluded_virtual_adapters(monkeypatch):
    # Hyper-V / VirtualBox адаптеры не считаются VPN
    fake_addrs = {"Hyper-V Virtual Ethernet": [], "VirtualBox Host-Only": []}
    monkeypatch.setattr("netmonitor.checkers.psutil.net_if_addrs", lambda: fake_addrs)

    assert is_vpn_active(_vpn_cfg()) is False


def test_vpn_active_with_multiple_adapters_one_vpn(monkeypatch):
    fake_addrs = {
        "Ethernet": [],
        "Wi-Fi": [],
        "Loopback Pseudo-Interface 1": [],
        "wintun0": [],
    }
    monkeypatch.setattr("netmonitor.checkers.psutil.net_if_addrs", lambda: fake_addrs)

    assert is_vpn_active(_vpn_cfg()) is True


def test_vpn_active_returns_false_when_psutil_fails(monkeypatch):
    # psutil может бросить исключение в некоторых окружениях — не должны упасть
    def boom():
        raise RuntimeError("psutil unavailable")
    monkeypatch.setattr("netmonitor.checkers.psutil.net_if_addrs", boom)

    assert is_vpn_active(_vpn_cfg()) is False


# === Признак 2: системный прокси Windows (HKCU\...\Internet Settings) ========
# VPN может не создавать сетевой адаптер, а просто включать системный прокси.
# ProxyEnable=1 в реестре → VPN активен.

class _FakeKey:
    def __init__(self, values: dict):
        self._values = values
    def QueryValueEx(self, name):
        return self._values[name]


def test_is_system_proxy_enabled_true(monkeypatch):
    # ProxyEnable=1 → прокси включён
    monkeypatch.setattr("netmonitor.checkers.winreg.HKEY_CURRENT_USER", 0)
    monkeypatch.setattr("netmonitor.checkers.winreg.OpenKey", lambda root, path: _FakeKey({"ProxyEnable": (1, 4)}))
    monkeypatch.setattr("netmonitor.checkers.winreg.QueryValueEx", lambda key, name: key.QueryValueEx(name))
    monkeypatch.setattr("netmonitor.checkers.winreg.CloseKey", lambda key: None)
    assert _is_system_proxy_enabled() is True


def test_is_system_proxy_disabled_false(monkeypatch):
    # ProxyEnable=0 → прокси выключен
    monkeypatch.setattr("netmonitor.checkers.winreg.HKEY_CURRENT_USER", 0)
    monkeypatch.setattr("netmonitor.checkers.winreg.OpenKey", lambda root, path: _FakeKey({"ProxyEnable": (0, 4)}))
    monkeypatch.setattr("netmonitor.checkers.winreg.QueryValueEx", lambda key, name: key.QueryValueEx(name))
    monkeypatch.setattr("netmonitor.checkers.winreg.CloseKey", lambda key: None)
    assert _is_system_proxy_enabled() is False


def test_is_system_proxy_registry_missing_returns_false(monkeypatch):
    # ключа ProxyEnable нет в реестре → не прокси
    class _KeyNoValue:
        def QueryValueEx(self, name):
            raise FileNotFoundError(name)
    monkeypatch.setattr("netmonitor.checkers.winreg.HKEY_CURRENT_USER", 0)
    monkeypatch.setattr("netmonitor.checkers.winreg.OpenKey", lambda root, path: _KeyNoValue())
    monkeypatch.setattr("netmonitor.checkers.winreg.QueryValueEx", lambda key, name: key.QueryValueEx(name))
    monkeypatch.setattr("netmonitor.checkers.winreg.CloseKey", lambda key: None)
    assert _is_system_proxy_enabled() is False


def test_is_system_proxy_openkey_fails_returns_false(monkeypatch):
    # раздел вообще не открывается (нет прав/не существует) → не прокси
    def boom(root, path):
        raise OSError("access denied")
    monkeypatch.setattr("netmonitor.checkers.winreg.HKEY_CURRENT_USER", 0)
    monkeypatch.setattr("netmonitor.checkers.winreg.OpenKey", boom)
    monkeypatch.setattr("netmonitor.checkers.winreg.QueryValueEx", lambda key, name: key.QueryValueEx(name))
    monkeypatch.setattr("netmonitor.checkers.winreg.CloseKey", lambda key: None)
    assert _is_system_proxy_enabled() is False


# === интеграция: is_vpn_active учитывает прокси =============================

def test_vpn_active_when_no_vpn_adapter_but_proxy_enabled(monkeypatch):
    # VPN-адаптера нет, но системный прокси включён → VPN активен
    monkeypatch.setattr("netmonitor.checkers.psutil.net_if_addrs", lambda: {"Ethernet": []})
    monkeypatch.setattr("netmonitor.checkers._is_system_proxy_enabled", lambda: True)
    assert is_vpn_active(_vpn_cfg()) is True


def test_vpn_inactive_when_no_adapter_and_no_proxy(monkeypatch):
    monkeypatch.setattr("netmonitor.checkers.psutil.net_if_addrs", lambda: {"Ethernet": []})
    monkeypatch.setattr("netmonitor.checkers._is_system_proxy_enabled", lambda: False)
    assert is_vpn_active(_vpn_cfg()) is False
