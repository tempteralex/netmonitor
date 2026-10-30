"""Тесты для tray.py: значки в трее для каждого статуса

Seam 1 (чистая логика, без GUI): make_icon(state) -> PIL.Image
  - возвращает изображение для каждого из 4 состояний
  - цвета: UNRESTRICTED=зелёный, WITH_VPN=синий, WHITELIST=жёлтый, NO_INTERNET=красный

Seam 2: TrayIcon класс
  - update(state) меняет иконку и tooltip
  - start()/stop() запуск/остановка (в тестах — без реального pystray.Icon,
    через инъекцию фабрики иконок)

Внешние границы: PIL.Image (реально генерится), pystray.Icon — инъекция.
"""
import pytest
from PIL import Image

from netmonitor.monitor import State
from netmonitor.tray import make_icon, TrayIcon, STATE_COLORS


# === Seam 1: make_icon =====================================================

@pytest.mark.parametrize("state", list(State))
def test_make_icon_returns_image_for_every_state(state):
    img = make_icon(state)
    assert isinstance(img, Image.Image)
    assert img.size[0] > 0 and img.size[1] > 0


def test_make_icon_different_colors_for_different_states():
    # иконки для разных состояний должны отличаться (разные цвета)
    img1 = make_icon(State.UNRESTRICTED)
    img4 = make_icon(State.NO_INTERNET)
    # сравниваем как RGB-данные
    assert list(img1.convert("RGB").getdata()) != list(img4.convert("RGB").getdata())


def test_state_colors_mapping():
    # каждый статус имеет свой цвет
    assert STATE_COLORS[State.UNRESTRICTED] != STATE_COLORS[State.NO_INTERNET]
    assert STATE_COLORS[State.WITH_VPN] != STATE_COLORS[State.WHITELIST]
    assert len(set(STATE_COLORS.values())) == 4  # все 4 цвета уникальны


def test_make_icon_uses_state_color():
    # цвет круга в точке вне буквы ≈ STATE_COLORS[state]
    img = make_icon(State.NO_INTERNET).convert("RGB")
    expected = STATE_COLORS[State.NO_INTERNET]
    # берём пиксель слева от центра (там чистый цвет круга, без буквы)
    cx, cy = img.size[0] // 2, img.size[1] // 2
    px = img.getpixel((cx - 12, cy))
    assert px == expected


# === Seam 2: TrayIcon ======================================================

class _FakePystrayIcon:
    """Заглушка pystray.Icon: запоминает установленную иконку/tooltip, не запускает GUI."""
    def __init__(self):
        self.icon = None
        self.title = None
        self.visible = False
        self.stopped = False

    def run(self):
        self.visible = True

    def stop(self):
        self.stopped = True
        self.visible = False

    def update_menu(self):
        pass


def test_trayicon_update_sets_icon_and_title(tmp_path):
    fake = _FakePystrayIcon()
    tray = TrayIcon(icon_factory=lambda s: fake)   # инъекция

    tray.update(State.NO_INTERNET)

    assert fake.icon is not None
    assert "Интернета нет" in fake.title or "NO_INTERNET" in fake.title


def test_trayicon_update_changes_icon_on_state_change(tmp_path):
    fake = _FakePystrayIcon()
    tray = TrayIcon(icon_factory=lambda s: fake)

    tray.update(State.UNRESTRICTED)
    first_icon = fake.icon
    tray.update(State.NO_INTERNET)
    assert fake.icon is not first_icon


def test_trayicon_update_same_state_does_not_change_icon(tmp_path):
    fake = _FakePystrayIcon()
    tray = TrayIcon(icon_factory=lambda s: fake)

    tray.update(State.UNRESTRICTED)
    first_icon = fake.icon
    tray.update(State.UNRESTRICTED)   # то же состояние
    assert fake.icon is first_icon


def test_trayicon_start_runs_icon(tmp_path):
    fake = _FakePystrayIcon()
    tray = TrayIcon(icon_factory=lambda s: fake)
    tray.start()
    assert fake.visible is True


def test_trayicon_stop_stops_icon(tmp_path):
    fake = _FakePystrayIcon()
    tray = TrayIcon(icon_factory=lambda s: fake)
    tray.start()
    tray.stop()
    assert fake.stopped is True
