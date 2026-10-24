# Порт на Linux: аудит Windows-зависимостей (L-01)

Составлено **2026-10-24** по коду ветки `feature/ux-10-license-orgs` (версия 3.8.2).
Задачи этапа: `docs/REESTR_ROADMAP.md`, Ф7 (L-02…L-09). Здесь только факты из кода и решения;
нормы ПП № 1236 см. `docs/REESTR_1236_HANDOFF.md`.

Метод: поиск по `*.py` (без `tests/`, `.venv/`, `build/`, `dist/`, `web/`) на `win32*`, `winreg`,
`ctypes.windll`, `DPAPI`, `APPDATA`/`USERPROFILE`, `explorer`, `os.name`/`sys.platform`, шрифты,
`sspi`, плюс `NormaOT_Reestr.spec`, `requirements.txt`, `tests/`. **На Linux код не запускался**
(WSL на машине разработчика не установлен), выводы о поведении сделаны по чтению кода.

## 1. Главный вывод

Сейчас программа на Linux **не запустится дальше создания мастер-ключа**:
`utils/crypto.py:_write_key_file()` всегда вызывает `_dpapi_encrypt()`, без `win32crypt` это
`CryptoUnavailableError`, обходного пути нет. Всё остальное (пути, прокси, реестр, ACL, UI)
деградирует мягко: ошибки `ImportError` уже перехватываются. Значит, порядок работ:
**L-02 (ключ) → L-03 (пути) → остальное**.

Платформенно-независимы и правок не требуют: БД (SQLite), импорт/экспорт xlsx/XML/DOCX
(openpyxl, lxml, defusedxml, python-docx), API-клиент на `requests`/`urllib`, лицензии (Ed25519),
аудит (HMAC), бэкап (`pyzipper`), организации (кроме путей).

## 2. Таблица «модуль → Windows-специфика → решение → оценка»

Оценка: **S** ≤ 0,5 дня, **M** 1–2 дня, **L** 3–5 дней (работа исполнителя, без тестов на ОС).

| Модуль | Что Windows-специфично | Решение для Linux | Задача | Оценка |
|---|---|---|---|---|
| `utils/crypto.py` | Мастер-ключ шифруется DPAPI (`win32crypt.CryptProtectData`, `_DPAPI_ENTROPY`); `_write_key_file` без DPAPI падает; production mode требует `win32crypt` (`check_environment`, создание ключа); статусы «DPAPI» в `get_key_protection_status`-подобных строках (стр. ~829–846) | Абстракция `KeyStore`: `DpapiKeyStore` (Windows, байт-в-байт как сейчас, `_DPAPI_ENTROPY` и формат не трогать), `SecretServiceKeyStore` (`keyring`/`secretstorage`, D-Bus), `PassphraseFileKeyStore` (уже есть PBKDF2 600K; файл 0600). Production mode на Linux: Secret Service или парольная фраза обязательны, plaintext запрещён. Ключи между ОС не переносятся | L-02 | L |
| `utils/crypto.py:_restrict_file_access` | DACL через `win32security` (только текущий пользователь); в prod при `ImportError` — `CryptoError` | POSIX: `os.chmod(path, 0o600)` (каталог 0700), проверять `st_mode` и владельца; в prod ошибка chmod → `CryptoError` | L-02 | S |
| `utils/app_paths.py` | База — `%APPDATA%`, fallback `~/AppData/Roaming`; миграция `Excel_to_XML` → `NormaOT` | `$XDG_DATA_HOME/NormaOT` (по умолчанию `~/.local/share/NormaOT`), логи `…/NormaOT/log`; миграцию на Linux не делать (статус `none`); каталог создавать с 0700 | L-03 | S |
| `utils/secure_temp.py` | ACL через `win32security` на каталог и файлы | Уже есть fallback `os.chmod(0o700)` для каталога; добавить 0600 на файлы (`mkstemp` и так 0600). Базу брать `$XDG_RUNTIME_DIR` (tmpfs, 0700), иначе `tempfile.gettempdir()` | L-03 | S |
| `utils/nag_state.py` | Маркер заставки дублируется в `HKCU\Software\NormaOT` (`winreg`) | Без `winreg` уже работает только файл `support_state.json`. Второе место — `$XDG_CONFIG_HOME/NormaOT/support_state` (иначе удаление папки данных сбрасывает дневной показ) | L-03 | S |
| `utils/proxy_manager.py` | `detect_windows_proxy()` читает реестр IE; `negotiate_available` по `import sspi` | Linux: `urllib.request.getproxies()` (переменные `https_proxy`/`http_proxy`/`no_proxy`); опционально `gsettings org.gnome.system.proxy` / KDE — не в v1. Negotiate: `False`, ручной логин/пароль прокси | L-04 | M |
| `network/client.py` | Та же детекция прокси и `win32security` для Negotiate; подпись «Negotiate/Kerberos (Squid)» | Использовать общую функцию детекции из `proxy_manager`; Negotiate на Linux — позже через `requests-gssapi` (нужен `kinit`), в v1 нет | L-04 | S |
| `api/backends/wininet_backend.py` | WinHTTP COM (`win32com.client`) | Уже `is_available()` = `False` вне `nt`. Не импортировать `win32com` на Linux, оставить модуль только для Windows | L-04 | S |
| `api/backends/urllib_backend.py` | Проверка `sspi` (только лог) | Убрать проверку на Linux или оставить (безвредно) | L-04 | S |
| `api/mintrud_api.py` | `DEFAULT_BACKEND_ORDER = ["wininet", "urllib", "requests"]`; «корпоративная сеть → wininet»; `use_negotiate and os.name == 'nt'` | Порядок по ОС: Linux `["requests", "urllib"]`. **TLS:** на Windows WinHTTP берёт системное хранилище (там может быть «Russian Trusted Root CA» или корпоративный CA для SSL-инспекции), `requests` берёт `certifi`, где их нет. Решение: пакет `truststore` (системное хранилище OpenSSL) или явный CA-файл в настройках; `verify=True` не отключать. Какой CA у `edu.rosmintrud.ru` — `[УТОЧНИТЬ]` (с ПК разработчика сайт недоступен) | L-04 | M |
| `tabs/data_transfer_tab.py` | Флажок «Использовать Windows-авторизацию (Negotiate/Kerberos)» | Скрыть на Linux (или подписать «Kerberos», когда появится gssapi) | L-04 | S |
| `main.py` | `ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID` (в `try`, на Linux молча пропускается); иконка `resources/ico.ico`; тексты про `%APPDATA%` в сообщениях о миграции (стр. 604–613); предупреждение «DPAPI unavailable» (стр. 696) | Явная проверка `sys.platform == "win32"`; на Linux `app.setDesktopFileName("normaot-reestr")` + PNG-иконка; тексты брать из `get_app_data_dir()`, а не литерала; предупреждение — по типу `KeyStore` | L-05 | S |
| `utils/tahoe_style.py` | `apply_mica()` — DWM (`ctypes.windll.dwmapi`) | Уже `return False` вне `win32`. Проверить вид стилей под Fusion на Linux: шрифт явно не задан, берётся системный (Astra: PT Astra Sans) | L-05 | S |
| `tabs/data_entry_tab.py:1070` | `subprocess.Popen('explorer /select,"…"')` | `QDesktopServices.openUrl(QUrl.fromLocalFile(папка))`; выделение файла есть только на Windows — оставить `explorer` под проверкой ОС | L-05 | S |
| `utils/log_viewer_dialog.py:350` | `subprocess.Popen(['explorer', dir])` | `QDesktopServices.openUrl(QUrl.fromLocalFile(dir))` на всех ОС | L-05 | S |
| `utils/log_viewer_dialog.py:143`, `utils/error_utils.py:83` | Шрифт `Consolas` | `QFontDatabase.systemFont(QFontDatabase.FixedFont)` | L-05 | S |
| `utils/about_dialog.py` | Рабочий стол из `USERPROFILE`, `TEMP` (стр. 240); отчёт об ошибке через Outlook COM (стр. 307) | `QStandardPaths.DesktopLocation` (на русской локали это `~/Рабочий стол`); Outlook — только Windows, на Linux сразу `mailto:` (fallback уже есть) | L-05 | S |
| `utils/help_dialog.py`, `utils/license.py`, `utils/org_profiles.py`, `utils/ui_helpers.py` | Только тексты/докстринги с `%APPDATA%` и «Windows DPAPI» | Справка: путь из `get_app_data_dir()`, описание защиты ключа — по ОС. В докстрингах писать «папка данных» | L-05 | S |
| `exporters/protocol_exporter.py` | Шрифт DOCX `Times New Roman` | Не код, а данные документа: на Linux LibreOffice подставит метрически совместимый (Liberation Serif / PT Astra Serif). Проверить вёрстку протокола на ОС | L-07 | S |
| `NormaOT_Reestr.spec` | `PyInstaller.utils.win32.versioninfo`, `.ico`, `hiddenimports` pywin32 | Отдельный `NormaOT_Reestr_linux.spec` (или ветвление по `sys.platform`): без versioninfo, без pywin32, PNG-иконка | L-06 | M |
| `requirements.txt` | `pywin32>=306` безусловно (на Linux `pip install` упадёт); `pyinstaller` и `xlrd` в runtime-зависимостях | `pywin32>=306; sys_platform == "win32"`; Linux: `keyring`/`secretstorage`, `truststore`; dev-зависимости вынести (совпадает с долгом #5) | L-02/L-06 | S |
| `Launcher.cs` | C#-лаунчер под `csc.exe` (устаревший, сборка идёт через PyInstaller) | На Linux не нужен; кандидат на удаление (долг #7–#12) | — | — |
| `tools/sign_build.ps1` | Authenticode | Linux: SHA-256 + подпись GPG (`.asc`) архива/пакетов | L-06 | S |
| `tools/site_gen/gen_docs.py`, `gen_pages.py` | Тексты «только Windows 10/11», `%APPDATA%`, `Get-AuthenticodeSignature`, pywin32 в списке лицензий | Разделы по ОС после L-06 | L-09 | M |

### Тесты

| Файл | Зависимость | Решение |
|---|---|---|
| `tests/conftest.py` | Изоляция через `APPDATA` | Дополнительно `XDG_DATA_HOME`, `XDG_CONFIG_HOME`, `XDG_RUNTIME_DIR` во временный каталог (иначе тесты на Linux тронут реальный `~/.local/share/NormaOT` — нарушение правила) |
| `tests/test_key_metadata_integrity.py` | Холодная загрузка через DPAPI | Параметризовать по `KeyStore`; DPAPI-ветка — `skipif(sys.platform != "win32")` |
| `tests/test_app_paths.py` | Семантика миграции `%APPDATA%` | Windows-кейсы под `skipif`, добавить XDG-кейсы |
| `tests/test_wininet_tls.py` | WinHTTP | Уже `skipif(not WININET_AVAILABLE)` для живого COM; проверить, что модуль импортируется на Linux |
| остальные | — | Прогнать полный набор на Linux в CI (GitHub Actions `ubuntu-latest`, `QT_QPA_PLATFORM=offscreen`) до тестов на Astra/РЕД ОС |

## 3. Целевые ОС и сборка (`[УТОЧНИТЬ]` до L-06)

- Выбор двух ОС — задача владельца **O-03** (кандидаты: Astra Linux SE, РЕД ОС, Альт).
- PySide6 ≥ 6.6 поставляется в колёсах `manylinux_2_28` (нужен glibc ≥ 2.28). Версии glibc на
  выбранных релизах ОС — `[УТОЧНИТЬ]` (сверить на образах: `ldd --version`). Сборку делать на самой
  старой поддерживаемой ОС.
- Python 3.12 не системный на этих ОС: поставлять собранным PyInstaller (onedir), не через пакет
  `python3` ОС.
- Qt на Linux: нужны системные `libxcb-cursor0` и др. xcb-библиотеки для плагина `xcb`; список
  зависимостей пакета `.deb`/`.rpm` составить в L-06.
- Secret Service: в Astra (Fly) и РЕД ОС может не быть запущенного `gnome-keyring`/KWallet —
  `[УТОЧНИТЬ]` на образах. Поэтому `PassphraseFileKeyStore` обязателен как основной fallback.

## 4. Побочная находка (не Linux, исправить отдельно)

`utils/crypto.py:_zero_memory()` делает `ctypes.memset(id(data) + 16, 0, len(data))` для
`bytearray`. У `bytearray` данные лежат в отдельном буфере (проверено: смещение буфера от `id()`
≈ 0xB7B0, а не 16), объект занимает 56 байт. Поэтому:

- ключ **не обнуляется** — затираются поля заголовка (`ob_size`, `ob_alloc`, указатель
  `ob_bytes`…), буфер с ключом утекает;
- при `len > 40` запись выходит за пределы объекта — **порча кучи**. Так бывает при
  `_zero_memory(old_encoded)` в `rotate_master_key` (base64 ключа = 44 байта).

Исправление: `buf = (ctypes.c_char * len(data)).from_buffer(data); ctypes.memset(buf, 0, len(data))`.
`_zero_memory_bytes()` копирует `bytes` в новый `bytearray`, исходный `bytes` этим не очистить
(ограничение CPython; оставить как best effort и честно описать в docs/SECURITY.md).

## 5. Предлагаемый порядок PR (ветка `feature/linux-port`)

Актуальный план и статусы: `docs/LINUX_ROADMAP.md` (там же L-00 = п. 1 ниже).

1. Исправление `_zero_memory` (отдельный маленький PR в основную ветку).
2. L-03 пути + `conftest` (XDG-изоляция) + CI на `ubuntu-latest` — тесты начинают гоняться на Linux.
3. L-02 `KeyStore` — самый рискованный, с тестами обеих веток; Windows-ветка байт-в-байт.
4. L-04 сеть (порядок бэкендов, прокси из окружения, `truststore`).
5. L-05 UI-мелочи (explorer, шрифты, тексты).
6. L-06 сборка и пакеты, затем L-07 тесты на ОС владельца.

## Выполнено в L-03 (2026-10-24)

- `utils/platform_info.py`: `IS_WINDOWS`, `IS_LINUX`; тесты патчат флаги.
- `app_paths`: на Linux база `$XDG_DATA_HOME` (относительное значение игнорируется, по спецификации XDG), каталог 0700 с явным `chmod`; миграции нет (статус `none`). Windows-ветка не менялась.
- `secure_temp`: на Linux база `$XDG_RUNTIME_DIR`, только если это каталог текущего пользователя без доступа группе/остальным, иначе `gettempdir()`; каталог 0700, файлы 0600; `win32security` на Linux не импортируется.
- `nag_state`: три копии маркера (реестр / `$XDG_CONFIG_HOME/NormaOT/support_state` / файл в каталоге данных), побеждает самая поздняя дата.
- `tests/conftest.py` перенаправляет `XDG_DATA_HOME`, `XDG_CONFIG_HOME`, `XDG_RUNTIME_DIR` и чистит XDG-маркер перед каждым тестом.
- Не проверено на реальном Linux (WSL не установлен, O-09): 4 POSIX-теста в `tests/test_platform_linux.py` на Windows пропускаются (`skipif`).
- `tests/test_app_paths.py` целиком помечен `skipif(not IS_WINDOWS)`.

