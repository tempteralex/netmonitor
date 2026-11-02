# netmonitor

Я раздаю интернет с телефона и с ограничениями связи хотелось бы знать когда она есть, а когда нет. Программа мониторинга наличия сети интернет для Windows. Непрерывно определяет  
**одно из 3 состояний** сети и уведомляет при смене состояния (звук + toast +
иконка в трее + лог).

## Состояния сети

| Состояние | Описание | Иконка |
|-----------|----------|--------|
| `UNRESTRICTED` | Интернет без ограничений | 🟢 зелёная |
| `WHITELIST` | Ограниченный интернет (белые списки) | 🟡 жёлтая |
| `NO_INTERNET` | Интернета нет | 🔴 красная |

## Как это работает

1. Периодически (настраиваемый интервал, по умолчанию 6 сек) проверяет по HTTP:
   - **маркер полного интернета** `connectivitycheck.gstatic.com` (заблокирован при белых списках,
     доступен прямо или пробросом через VPN);
   - **хосты белого списка** `gosuslugi.ru`, `vk.ru` (доступны всегда, когда интернет есть).
2. По таблице состояний вычисляет текущее:
   - `connectivitycheck` доступен → **интернет без ограничений** (прямой доступ или VPN-проброс);
   - `connectivitycheck` недоступен, но белые хосты доступны → **ограниченный интернет (белые списки)**;
   - ничего не доступно → **интернета нет**.
3. Состояние считается подтверждённым после N (по умолчанию 3) одинаковых
   наблюдений подряд — одиночные провалы не переключают состояние.
4. При подтверждённой смене состояния:
   - показывает toast-уведомление (PowerShell),
   - записывает переход в лог-файл,
   - ждёт `notify_delay_sec` (3 сек),
   - проигрывает звук `C:\Windows\Media\Alarm10.wav`,
   - обновляет иконку в трее.

## Установка с GitHub

### 1. Клонирование репозитория

```bash
git clone https://github.com/tempteralex/netmonitor.git
cd netmonitor
```

Или через SSH:
```bash
git clone git@github.com:tempteralex/netmonitor.git
cd netmonitor
```

### 2. Установка зависимостей

Рекомендуется использовать виртуальное окружение:

```bash
python -m venv venv
venv/Scripts/activate          # Windows (git-bash / PowerShell)
# или:  venv\Scripts\activate.bat   (cmd)
# или:  venv\Scripts\Activate.ps1   (PowerShell)

pip install -r requirements.txt
```

Требуется Python 3.10+ на Windows (используется `winsound`, `winreg`, `pystray`).

### 3. Конфигурация

Файл [`config.yaml`](config.yaml) уже идёт с примером. Отредактируйте под себя:
- `hosts.allowed` — хосты, доступные всегда (белый список при ограничениях)
- `hosts.blocked` — хост, который **доступен только при полном интернете**
  (должен блокироваться при ограничениях — например google.com)
- `interval_sec`, `confirm_count` — интервал опроса и число подтверждений
- `interval_sec`, `confirm_count` — интервал опроса и число подтверждений

### 4. Первый запуск

```bash
python -m netmonitor.cli --config config.yaml
```

При **первом старте** программа автоматически добавит себя в автозагрузку
Windows (если её там ещё нет). После перезагрузки ПК мониторинг запустится
сам. Подробное сообщение печатается в консоль при добавлении.

Чтобы отключить авто-добавление в автозагрузку:
```bash
python -m netmonitor.cli --config config.yaml --no-autostart
```

## Установка (кратко)

```bash
git clone https://github.com/tempteralex/netmonitor.git
cd netmonitor
python -m venv venv && venv/Scripts/activate
pip install -r requirements.txt
python -m netmonitor.cli --config config.yaml
```

## Использование

```bash
# разовая проверка (отладка)
python -m netmonitor.cli --check-once --config config.yaml

# запустить мониторинг с иконкой в трее
python -m netmonitor.cli --config config.yaml

# без иконки в трее
python -m netmonitor.cli --config config.yaml --no-tray

# вручную добавить/удалить автозагрузку
python -m netmonitor.cli --install-startup --config config.yaml
python -m netmonitor.cli --uninstall-startup
```

### Меню иконки в трее

Правый клик по иконке:
- **Перезагрузка** — перезапуск процесса мониторинга (полный рестарт)
- **Выход** — завершить программу

## Деинсталляция

### Убрать из автозагрузки

```bash
python -m netmonitor.cli --uninstall-startup
```

Удаляет `.vbs`-лаунчер из папки Startup. После этого мониторинг не будет
запускаться при старте Windows.

### Полное удаление программы

1. Уберите из автозагрузки (см. выше):
   ```bash
   python -m netmonitor.cli --uninstall-startup
   ```
2. Остановите мониторинг (клик «Выход» в трее, или Ctrl+C в консоли)
3. Удалите папку с программой:
   ```bash
   rm -rf D:/work/job
   ```
4. (опционально) Удалите зависимости:
   ```bash
   pip uninstall psutil requests pyyaml pystray Pillow
   ```
5. (опционально) Удалите лог `monitor.log`, если создавался в папке программы

## Конфигурация

См. [`config.yaml`](config.yaml) — все параметры настраиваются: интервал,
таймауты, список хостов, флаги уведомлений, задержка.

## Структура проекта

```
netmonitor/
  config.py        # загрузка/валидация YAML-конфига
  checkers.py      # проверка хостов по HTTP
  monitor.py       # определение состояния + главный цикл
  state_tracker.py # подтверждение смены состояния
  notifier.py      # toast + звук + лог
  tray.py          # иконка в трее (pystray)
  startup.py       # автозапуск (.vbs лаунчер)
  cli.py           # точка входа с флагами
```