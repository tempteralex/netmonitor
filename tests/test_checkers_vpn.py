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

from netmonitor.checkers import is_vpn_active, _interface_is_vpn
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
