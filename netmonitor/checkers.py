"""П2: Проверка доступности хоста.

Seam: is_host_available(url, connect_timeout, read_timeout) -> bool
HTTP GET. True если получили любой HTTP-ответ (TCP установлен + сервер ответил).
False на сетевой ошибке / таймауте / 5xx.
"""
from __future__ import annotations

import requests


def is_host_available(url: str, connect_timeout: int, read_timeout: int) -> bool:
    try:
        resp = requests.get(url, timeout=(connect_timeout, read_timeout), allow_redirects=True)
    except (requests.RequestException, OSError):
        return False
    # 2xx/3xx/4xx → сервер ответил, соединение установлено → считаем доступным.
    # 5xx → сервер жив, но сам себя считает сломанным → недоступен.
    return resp.status_code < 500
