"""П6: Уведомления при смене состояния.

Seam: Notifier(notifications_cfg).notify(old_state, new_state)
Действия (по флагам cfg):
  - звук:        winsound (stdlib, Windows). Вид звука зависит от характера смены:
                   NO_INTERNET      → "alarm"
                   улучшение (→ UNRESTRICTED/WITH_VPN, или из NO_INTERNET) → "ok"
                   иное ухудшение   → "warn"
  - toast:       через PowerShell BurnDownNotification (без сторонних пакетов)
  - лог-файл:    append-запись строки перехода
Внешние границы (_play_sound, _show_toast) вынесены как методы — для тестов
их подменяют через monkeypatch/присваивание.
"""
from __future__ import annotations

import datetime as _dt
import subprocess
import time
from pathlib import Path

import winsound

from netmonitor.config import NotificationsCfg
from netmonitor.monitor import State


# путь к звуковому файлу (один сигнал на любое изменение статуса)
_SOUND_FILE = r"C:\Windows\Media\Alarm10.wav"


class Notifier:
    def __init__(self, cfg: NotificationsCfg):
        self._cfg = cfg
        self._log_path = Path(cfg.log_file)
        # методы-границы — переопределяются в тестах
        self._play_sound = self._default_play_sound
        self._show_toast = self._default_show_toast

    # --- публичный seam -----------------------------------------------------

    def notify(self, old_state: State | None, new_state: State) -> None:
        # Порядок: toast → лог → задержка → звук
        if self._cfg.toast:
            self._show_toast(self._toast_text(new_state))
        self._write_log(old_state, new_state)
        # задержка МЕЖДУ уведомлением и звуком
        if self._cfg.notify_delay_sec > 0:
            time.sleep(self._cfg.notify_delay_sec)
        if self._cfg.sound:
            self._play_sound()

    # --- звук (один сигнал на любое изменение) ------------------------------

    @staticmethod
    def _toast_text(state: State) -> str:
        return f"Состояние сети: {state.label()}"

    # --- лог ----------------------------------------------------------------

    def _write_log(self, old_state: State | None, new_state: State) -> None:
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        old = old_state.name if old_state is not None else "START"
        line = f"{ts}  {old} -> {new_state.name}  ({new_state.label()})\n"
        # append, создать при необходимости
        with self._log_path.open("a", encoding="utf-8") as f:
            f.write(line)

    # --- реализации границ по умолчанию -------------------------------------

    def _default_play_sound(self, kind=None) -> None:
        # ОДИН сигнал (Alarm10.wav) на любое изменение статуса.
        # kind аргумент оставлен для обратной совместимости, но не используется.
        try:
            winsound.PlaySound(_SOUND_FILE, winsound.SND_FILENAME)
        except RuntimeError:
            # звуковой файл/устройство недоступны — fallback на системный бип
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except RuntimeError:
                pass

    @staticmethod
    def _default_show_toast(text: str) -> None:
        # PowerShell BurnDownNotification — без сторонних пакетов.
        ps = (
            "$ErrorActionPreference='SilentlyContinue';"
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$n = New-Object System.Windows.Forms.NotifyIcon;"
            "$n.Icon = [System.Drawing.SystemIcons]::Information;"
            "$n.Visible = $true;"
            f"$n.ShowBalloonTip(5000, 'NetMonitor', '{text}', "
            "[System.Windows.Forms.ToolTipIcon]::Info);"
            "Start-Sleep -Seconds 6;"
            "$n.Dispose()"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True,
                timeout=15,
            )
        except Exception:
            pass  # toast — не критичен; лог всё равно записан
