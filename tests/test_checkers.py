"""Тесты для П2: checkers.is_host_available(url, connect_timeout, read_timeout) -> bool

Seam: функция делает HTTP GET и возвращает True если получили любой HTTP-ответ
(2xx/3xx/4xx — главное что TCP установлен и сервер ответил), False на сетевой
ошибке/таймауте/5xx.

Стратегия без патча сети:
  - доступный хост → поднимаем локальный http-сервер на 127.0.0.1, проверяем True
  - недоступный хост → несуществующий домен (.invalid), ожидаем False
  - таймаут → сервер который не отвечает, короткий timeout, ожидаем False
"""
import http.server
import socketserver
import threading
import time

import pytest

from netmonitor.checkers import is_host_available


# --- локальный HTTP-сервер для теста "доступен" -----------------------------

class _SilentHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args, **kwargs):
        pass  # тишина в консоли


@pytest.fixture
def live_http_url():
    with socketserver.TCPServer(("127.0.0.1", 0), _SilentHandler) as httpd:
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{port}/"
        httpd.shutdown()
        thread.join(timeout=2)


# --- доступный хост → True --------------------------------------------------

def test_available_host_returns_true(live_http_url):
    assert is_host_available(live_http_url, connect_timeout=3, read_timeout=3) is True


# --- несуществующий домен → False -------------------------------------------

def test_nonexistent_host_returns_false():
    # .invalid гарантированно не резолвится (RFC 2606)
    assert is_host_available(
        "http://definitely-not-real.invalid/", connect_timeout=3, read_timeout=3
    ) is False


# --- таймаут: сервер принимает соединение, но не отвечает → False -----------
# Используем TCP-сервер который accept'ает но ничего не шлёт.

def test_slow_server_returns_false():
    class _NoResponse(socketserver.BaseRequestHandler):
        def handle(self):
            time.sleep(10)  # держим соединение, не отвечаем

    with socketserver.TCPServer(("127.0.0.1", 0), _NoResponse) as srv:
        port = srv.server_address[1]
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{port}/"
        # read_timeout 1с — сервер спит 10с, должны получить False
        assert is_host_available(url, connect_timeout=3, read_timeout=1) is False
        srv.shutdown()
        thread.join(timeout=2)
