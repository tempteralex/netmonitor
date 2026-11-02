"""Значки в трее для каждого статуса сети.

Seam 1 (чистая логика): make_icon(state) -> PIL.Image — рисует иконку цвета статуса.
Seam 2: TrayIcon — обёртка над pystray.Icon. update(state) меняет иконку+tooltip.
  Через icon_factory инъекция pystray.Icon для тестов (без реального GUI).
"""
from __future__ import annotations

import threading
from typing import Callable

from PIL import Image, ImageDraw

from netmonitor.monitor import State


# цвета для каждого состояния (RGB)
STATE_COLORS: dict[State, tuple[int, int, int]] = {
    State.UNRESTRICTED: (34, 197, 94),    # зелёный — интернет без ограничений
    State.WHITELIST: (234, 179, 8),       # жёлтый — ограниченный (белые списки)
    State.NO_INTERNET: (239, 68, 68),     # красный — интернета нет
}

_ICON_SIZE = 64


def make_icon(state: State) -> Image.Image:
    """Сгенерировать иконку (PIL.Image) цвета статуса: круг с обводкой."""
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = STATE_COLORS[state]
    # внешний круг (заливка цветом статуса)
    margin = 4
    draw.ellipse(
        [margin, margin, _ICON_SIZE - margin, _ICON_SIZE - margin],
        fill=color + (255,),
        outline=(255, 255, 255, 200),
        width=2,
    )
    # буква-индикатор в центре
    letter = _state_letter(state)
    try:
        # используем дефолтный шрифт PIL
        from PIL import ImageFont
        font = ImageFont.load_default()
    except Exception:
        font = None
    # центрируем текст
    text_color = (255, 255, 255, 255)
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (_ICON_SIZE - tw) // 2 - bbox[0]
    ty = (_ICON_SIZE - th) // 2 - bbox[1]
    draw.text((tx, ty), letter, fill=text_color, font=font)
    return img


def _state_letter(state: State) -> str:
    return {
        State.UNRESTRICTED: "I",    # Internet
        State.WHITELIST: "W",       # Whitelist
        State.NO_INTERNET: "X",     # no internet
    }[state]


class TrayIcon:
    """Обёртка над pystray.Icon с обновлением иконки по состоянию сети.

    icon_factory(state) -> pystray.Icon-подобный объект. По умолчанию создаёт
    реальный pystray.Icon; в тестах подменяется через конструктор.
    """

    def __init__(self, icon_factory: Callable[[State], object] | None = None,
                 on_restart: Callable[[], None] | None = None):
        self._icon_factory = icon_factory or self._default_icon_factory
        self._on_restart = on_restart
        self._icon = None
        self._current_state: State | None = None
        self._thread: threading.Thread | None = None
        self._menu_items: list[tuple[str, Callable]] = []   # для get_menu_callback

    def _build_menu_items(self) -> list[tuple[str, Callable]]:
        """Список (label, callback) пунктов меню трея.

        Заполняется всегда (включая custom icon_factory), чтобы get_menu_callback
        работал независимо от того, кто создал Icon.
        """
        items: list[tuple[str, Callable]] = []
        if self._on_restart is not None:
            def on_restart(icon, item):
                self._on_restart()
            items.append(("Перезагрузка", on_restart))

        def on_quit(icon, item):
            if self._icon is not None:
                self._icon.stop()
        items.append(("Выход", on_quit))
        self._menu_items = items
        return items

    def _default_icon_factory(self, initial: State):
        from pystray import Icon, Menu, MenuItem

        img = make_icon(initial)
        items = self._build_menu_items()
        return Icon(
            "netmonitor",
            icon=img,
            title=initial.label(),
            menu=Menu(*[MenuItem(lbl, cb) for lbl, cb in items]),
        )

    def get_menu_callback(self, label: str):
        """Вернуть колбэк пункта меню по его названию (для тестов/отладки)."""
        for lbl, cb in self._menu_items:
            if lbl == label:
                return cb
        return None

    def update(self, state: State) -> None:
        """Сменить иконку и tooltip. При первом вызове создаёт pystray.Icon."""
        if self._icon is None:
            self._build_menu_items()   # заполнить пункты меню (для get_menu_callback)
            self._icon = self._icon_factory(state)
            self._current_state = state
            # инициализируем поля иконки (для заглушек и реального pystray)
            try:
                self._icon.icon = make_icon(state)
                self._icon.title = state.label()
            except Exception:
                pass
            return

        if state == self._current_state:
            return  # без изменений — не трогаем иконку

        self._current_state = state
        new_img = make_icon(state)
        # pystray.Icon поддерживает присвоение .icon и .title
        try:
            self._icon.icon = new_img
            self._icon.title = state.label()
            self._icon.update_menu()
        except Exception:
            pass

    def start(self) -> None:
        """Запустить pystray.Icon (блокирует — вызывать до или в отдельном потоке)."""
        if self._icon is None:
            # инициализация иконкой «ожидание» (NO_INTERNET как нейтральная)
            self.update(State.NO_INTERNET)
        self._icon.run()

    def start_detached(self) -> None:
        """Запустить иконку в фоновом потоке (не блокирует вызывающий)."""
        if self._icon is None:
            self.update(State.NO_INTERNET)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Остановить иконку."""
        if self._icon is not None:
            self._icon.stop()
        if self._thread is not None:
            self._thread.join(timeout=2)
