# Changelog

## v3.9.0 "Норма" (2026-10-27)

Новый интерфейс. Функции и данные те же; формат файлов и базы не менялся.

### Changed
- Боковое меню вместо вкладок, верхнего меню и строки состояния. Блок «сегодня» (время, дата, внесено работников, просрочено, не обучено); раздел «Протоколы» отдельной группой. Горячие клавиши сохранены (`Ctrl+1…7` теперь идут в порядке бокового меню: «Сводка» пятая). Последний открытый раздел запоминается.
- Три темы вместо четырёх: «Норма» (по умолчанию), «Monokai тёмная», «Monokai светлая». Старые темы (Tahoe светлая/тёмная, Dracula, Monokai Pro) убраны: сохранённый выбор заменяется на ближайшую новую.
- Шрифты Rubik и Space Grotesk (SIL OFL 1.1) встроены в программу (`resources/fonts/`).
- Все цвета — из именованных токенов темы; роли кнопок (главная, тёмная, вторичная, прозрачная, опасная); единый вид карточек, шапок экранов и диалогов (шапка и подвал). В коде нет захардкоженных цветов — это проверяет тест.
- Значки вместо эмодзи и стандартных `SP_*`: общий набор в `utils/icons.py`; статусы — зелёная галочка, жёлтый треугольник, красный круг (без знака — «не обучен»), серые часы, серый «?».
- «Сводка по сотрудникам»: закреплены столбцы «Сотрудник», «СНИЛС», «Статус»; статус только значком (с подсказкой и доступным именем); двухуровневая шапка «№ · программа» над «Потребность / Дата / Протокол / Рег.№»; итоги с полосой долей и чипами-фильтрами; меню «Отчёты и планы», «Реестр», «Экспорт», «⋯».
- Сортировка во всех таблицах в три состояния (по возрастанию, по убыванию, исходный порядок); даты и числа сравниваются по значению, пустые ячейки внизу. В «Журнале проверки знаний» сортировка раньше не работала.
- «Журнал проверки знаний»: статус значком, строки не заливаются цветом статуса; «Получить номера из реестра», «Импорт», «Экспорт XLSX».
- «Настройка протоколов»: две страницы «Организация и комиссия» и «Программы обучения». «Быстрый протокол»: две карточки, жёлтая плашка при незаполненной комиссии.
- Окна «План» и «Текущая ситуация» переключаются сегментом «Текущий год / Следующий год / Текущая ситуация»; тёмные плашки у «О программе», «Выбор организации», «Поддержите проект», запроса парольной фразы и блокировки; «Безопасность» — карточками; общий «Справочник» программ.
- Окно «Настройки и темы» (внешний вид, подключение к реестру, безопасность, блокировка, файлы, организации) заменило меню «Файл / Организация / Настройки / Темы / Справка / Инструменты»; «О программе» — отдельная кнопка в боковом меню под «Справкой». «Настройки прокси» открываются поверх окна настроек, а не за ним.
- «Настройка протоколов»: председатель, представитель профсоюза и кнопки сохранения/загрузки комиссии — в левой колонке, члены комиссии — в правой, без прокрутки.
- «Журнал проверки знаний»: фильтры в две строки, кнопки не сжимаются меньше своего текста — на узком окне ничего не обрезается и не наезжает.
- Стрелки у выпадающих списков, полей даты и счётчиков рисуются в цвет темы (раньше в стилизованных полях их не было видно). Шрифт без хинтинга и со сглаживанием — без «рваных» контуров Rubik в Windows.
- Новый значок программы.
- Справка переписана под новые названия разделов и кнопок; добавлен раздел «Настройки и темы».
- Лицензия «Персональная»: окно «Поддержите проект» не показывается и при смене организации (раньше нужна была «Организация»); при добавлении организации правило прежнее.

### Added
- «Что нового»: клик по номеру версии в левом нижнем углу показывает изменения этой версии (раздел `CHANGELOG.md`, файл входит в сборку).
- «Сформировать XML и перейти к передаче»: сохраняет `ДДММГГГГ-ЧЧ-ММ.xml` (при совпадении «-2», «-3») в папку XML и открывает «Передачу данных» с этим файлом (проверка XSD как при ручном выборе). Папка по умолчанию — `XML` рядом с программой, а если туда нельзя писать — `Документы\Норма ОТ\XML`; своя папка выбирается в «Настройки и темы → Файлы».
- «Внесение данных»: полоса «Последняя загрузка» (дата, файл, добавлено / дублей / ошибок; хранится только имя файла); «Добавить и ещё» и подсказка об ошибке даты в ручном вводе.
- «Просмотр данных»: «запись N из M» и стрелки ←/→ в окне редактирования.
- «Выбор организации»: число сотрудников у каждой организации.
- «Передача данных»: кнопка «Копировать» у последнего SetId; счётчик символов API-ключа.

### Fixed
- «План» и «Текущая ситуация»: у не обученных в столбце «Последняя дата обучения» выводилось «None» вместо пустой ячейки.
- Окна открывались с минимальной высотой, и поля сжимались так, что текст обрезался (заметнее всего в «Редактировании данных»). Теперь окно сразу получает нужную высоту, но не больше 90% экрана; «Редактирование данных» прокручивается на низких экранах.
- Linux без связки ключей ОС: мастер-ключ уже защищён фразой, которую программа спрашивает при запуске, но «О программе» и «Безопасность» всё равно предлагали установить парольную фразу, а блокировка сеанса была недоступна. Теперь вторая фраза не предлагается, а блокировка сеанса работает и снимается той же фразой. В «О программе» предупреждение больше не показывается и при уже установленной фразе.
- Linux: пакет `.deb` сжимается xz, а не zstd (сборка на Ubuntu 24.04 по умолчанию даёт zstd, который dpkg старше 1.21.18 — Astra SE 1.7, Debian 9–11 — не открывает).
- При закрытии программы фильтр автоблокировки снимается до выгрузки Qt (иначе при выходе изредка сыпались ошибки в консоль).
- В `utils/tahoe_style.py` не был определён `logger`: любая ошибка чтения или записи файла темы привела бы к падению.

## v3.8.4 "Send history" (2026-10-25)

### Added
- История отправок на вкладке «Передача данных»: дата и время, SetId, число записей, статус набора (в реестре подписано / не подписано / удалено / неизвестно). Кнопка «История» показывает и скрывает панель; «Обновить данные» запрашивает последние 5 наборов, ПКМ — выделенные (до 20). Таблица `send_history` в базе организации, персональных данных нет.
- Предупреждение, если подписанный набор создан, но в реестр не отправлен (`SendEducatedPerson=false`).
- Справка: раздел «История отправок»; пункт «Содержание» подсвечивается при прокрутке.

### Changed
- Кнопка «Показать» у API-ключа заменена значком «глаз» (ключ виден, пока кнопка зажата).
- Окна «План на год» и «Текущая ситуация»: ширину столбцов можно менять, ширины запоминаются.

### Fixed
- Ответ `<Response><Error>` разбирается как ошибка (раньше запрос по SetId мог показать «записей нет»); в текст ошибки добавлен код обращения. Отправка без SetId в ответе считается ошибкой.

## v3.8.3 "Linux preview, GitFlic" (2026-10-24)

### Changed — репозиторий исходного кода
- Основной репозиторий — GitFlic (`gitflic.ru/project/denis-krv/norma_ot_reestr`), зеркало — GitHub (`github.com/Kerlad/norma_ot_reestr`); старый `Kerlad/Excel_to_XML` удалён. Окно «О программе» показывает оба адреса.
- История git очищена от архивов сборок, журналов и рабочих данных; дистрибутив раздаётся только с normaot.ru.

### Release
- Windows: `NormaOT-Reestr.zip` 70 230 890 байт, SHA-256 `61670ff08f085d4e64e3f3ba150a62f5b599874eaff914e8ed6e4650ea8323e9`, `NormaOT_Reestr.exe` подписан самоподписанным сертификатом издателя (с меткой времени).
- Linux (предварительная сборка, glibc ≥ 2.34): `normaot-reestr_3.8.3_amd64.deb` 64 441 042 байт, SHA-256 `49dab6009a6553598aa8c3b367e3fbe65021f44e78fa50909b3abb1e1f974d4a`; `normaot-reestr-3.8.3-alt1.x86_64.rpm` 82 412 318 байт, SHA-256 `ac8834905f753a0b35a42e43e035f613415e359284e530ff280db04c182da121`; `normaot-reestr-3.8.3-linux-x86_64.tar.gz` 82 867 986 байт, SHA-256 `d1354179fe2cb84f08d582831b113d893053bf687eedac23fc904a3e29db18e9`.
- `tools/linux/*.sh` помечены исполняемыми в git.

### Added — основа Linux-порта (L-03, поведение на Windows не меняется)
- `utils/platform_info.py`; на Linux каталог данных `$XDG_DATA_HOME/NormaOT` (0700), временные файлы в `$XDG_RUNTIME_DIR` (0700/0600), маркер заставки в `$XDG_CONFIG_HOME/NormaOT/support_state`.
- Хранилище мастер-ключа `utils/keystore.py` (L-02): Secret Service или парольная фраза на Linux, DPAPI на Windows без изменений; сбой хранилища не приводит к созданию нового ключа; бэкап ключа другой ОС не восстанавливается.
- Сеть на Linux (L-04): бэкенды `requests`/`urllib`, прокси из переменных окружения (`detect_system_proxy`), системное хранилище сертификатов (`truststore`) и необязательный `ca_file`; Negotiate только на Windows.

### Fixed — «Удалить все данные» не удаляла мастер-ключ из Secret Service (Linux)
- `crypto.forget_master_key()` вызывается при сбросе из меню, диалога безопасности и экрана разблокировки; тесты в `tests/test_keystore.py`.

### Fixed — `_zero_memory()` не обнуляла ключ и могла портить кучу (все ОС)
- `utils/crypto.py`: запись шла по `id(data) + 16`, а у `bytearray` данные лежат в отдельном буфере —
  ключ не затирался, а при `len > 40` (base64-ключ в `rotate_master_key`, 44 байта) запись выходила за объект.
  Теперь обнуление идёт через `ctypes.c_char.from_buffer()` по реальному адресу буфера.
- `_zero_memory_bytes()` остаётся best effort (неизменяемый `bytes` не очистить), это описано в докстринге.
- Тесты: `tests/test_crypto_zero_memory.py`.

### Fixed — бэкапы без `pyzipper` создавались незашифрованными (все ОС)
- `utils/crypto.py:create_master_key_backup()` и `db/database.py:create_backup()`: без `pyzipper` стандартный
  `zipfile` писал открытый архив (`setpassword` работает только на чтение). Теперь бэкап не создаётся,
  пишется аудит `SECURITY_WARNING`; ключ возвращает `(False, "…")`, БД — пустую строку.
- Убран fallback на открытую копию БД (`shutil.copy2`) при `OSError`; недописанный архив удаляется.
- Тесты: `tests/test_backup_no_plaintext.py`.

## v3.8.2 "Repeated query crash fix" (2026-10-21)

### Fixed — crash «Internal C++ object (PySide6.QtCore.QThread) already deleted»

1. **Second SNILS query / proxy test no longer crashes the app** (`tabs/data_transfer_tab.py`)
   - The worker `QThread` deletes itself (`deleteLater`) when finished, but the tab kept the Python reference; the next click called `isRunning()` on the deleted C++ object → `RuntimeError` (unhandled, app crash)
   - References are now dropped on `finished` (`_forget_thread`, only if it is still the same thread); the "already running" guard `_thread_busy()` treats a deleted thread as idle
   - Same fix for «Тест подключения» (proxy test)
2. Tests `tests/test_transfer_thread_refs.py` (3)

### Release

- Version 3.8.2; portable build `dist/NormaOT-Reestr.zip` (69 187 749 bytes, SHA-256 `ec46dbdc2353a9423442f60e1b230b3b9b559d9ab540a4faf05ef2c616712e2b`), `NormaOT_Reestr.exe` signed with the self-signed publisher certificate (timestamped)

## v3.8.1 "TLS fix for Windows 10" (2026-10-21)

### Fixed — «Ошибка поддержки безопасных каналов» when sending/querying on Windows 10

1. **WinHTTP backend now requests TLS 1.2/1.3 explicitly** (`api/backends/wininet_backend.py`)
   - The `WinHttp.WinHttpRequest.5.1` COM object may offer only SSL3/TLS 1.0 on Windows 10 (and 7/8.1); the registry server rejected the handshake with `ERROR_WINHTTP_SECURE_CHANNEL_ERROR` (12157)
   - `SecureProtocols` (option 9) is set to TLS 1.2 + TLS 1.3, falling back to TLS 1.2 where the OS lacks TLS 1.3
   - Options are set through `IDispatch` property-put: late-bound win32com cannot assign `http.Option[n]`, so the old code silently did nothing
2. **TLS-verification switch now actually works on WinHTTP** — it used the C-API number 31 instead of the COM `SslErrorIgnoreFlags` (4)
3. **Readable WinHTTP errors + automatic fallback**
   - COM errors are decoded by WinHTTP code (12157, 12175, 12045, 12038, 12002, 12029 …) into a short Russian message instead of the raw tuple
   - TLS failures are marked as such, so `MintrudClient` retries through the OpenSSL-based `urllib`/`requests` backends (previously the Russian text matched no SSL marker and the fallback never ran)
   - TLS failure dialog no longer blames only the corporate proxy; mentions outdated Windows TLS settings and the README troubleshooting section
4. Tests `tests/test_wininet_tls.py` (8)

### Docs

- README rewritten: download table with SHA-256 and signature, tabs overview, organizations, troubleshooting (TLS error, SmartScreen, data/log paths), current support/license text

### Release

- Version 3.8.1; portable build `dist/NormaOT-Reestr.zip` (69 187 110 bytes, SHA-256 `ce7be47eff4aa7950a5e429df0d1a5eba0d26e12f8f2fc5772c626463ddcce01`), `NormaOT_Reestr.exe` signed with the self-signed publisher certificate (timestamped); built from `.venv` — the duplicate `libssl-3-x64.dll`/`libcrypto-3-x64.dll` from the global env are no longer bundled (`_ssl.pyd` uses `libssl-3.dll`/`libcrypto-3.dll`)

## v3.8.0 "Registry report import, daily splash, signed build" (2026-10-20)

### UX-14 — Registry report import into the employee summary

1. **«Импорт отчёта из реестра»** on the «Сводка по сотрудникам» tab (`journal/summary_sync.py`, `tabs/employee_summary_tab.py`)
   - Loads the SetId response XLSX (same format as the journal import) into the employee directory
   - Employees matched by SNILS: digits only, checksum verified; existing employees get their programs updated (date, protocol, reg. number, result), re-importing the same file creates no duplicates (keyed by employee + program)
   - Unknown SNILS: the user sees how many and who, and confirms before they are added (default "No"); the report counts added and skipped
   - Duplicate rows for one program: the passed record wins, among those the latest exam date; a program with only failed attempts stays failed
   - Rows with no/invalid SNILS or an invalid program number are skipped and listed in the report by file row number and reason (no PD in logs or audit)
   - Wrong file type is rejected with the expected column names; 10 MB size limit; audit `IMPORT_XLSX` with counts only
2. Help (F1): section «Импорт отчёта реестра в сводку»; tests `tests/test_summary_sync.py` (31)

### UX-16 — Daily splash, waiting-screen support block

1. **Startup splash once per calendar day** (`utils/nag_state.py`, `main.py`)
   - The 10 s «Поддержите проект» splash now appears only on the first launch of a calendar day
   - The marker is stored twice — registry `HKCU\Software\NormaOT` (`LastSupportSplash`) and `support_state.json` in the data dir; reading takes the later date and repairs the other copy, so deleting one does not reset it
   - A stored date in the future (clock moved back) counts as due; marker failures never block startup; contains a date only, no PD
   - Organization add (60 s) and switch (30 s) splashes are unchanged and ignore the daily marker
2. **Support block on the employee-query waiting screen** (`tabs/employee_summary_tab.py:QueryProgressDialog`)
   - Same offer and code field, no timer, «Скрыть» closes it at any moment; the progress dialog and its «Отмена операции» stay usable
3. **«Спасибо за поддержку!» with license details** (`utils/donation_dialog.py:SupportPanel`)
   - With an active license the splash and the waiting-screen block show tier, holder and expiry date instead of the offer
   - 30 days before expiry: «осталось N дней» and a field for the new code («Продлить»)
   - Shared `SupportPanel` widget; dialog opened from About/Help closes with «Закрыть»
4. Help (F1) updated; tests `tests/test_nag_state.py` (21); `tests/conftest.py` keeps the registry marker out of the real HKCU
5. **Authenticode signing step** (`tools/sign_build.ps1`, UX-15)
   - Signs the built EXE with a certificate from the store (`NORMAOT_SIGN_THUMBPRINT`, incl. USB token) or a `.pfx` outside the repo; SHA-256, mandatory RFC 3161 timestamp, `-IncludeChain NotRoot`
   - Without a certificate: warning + exit code 2, the build stays unsigned instead of failing the release
   - Added as step 3 of AGENTS.md §EXE Build & Release (before zipping)
6. **Self-signed publisher certificate** (`tools/make_signing_cert.ps1`, `docs/CODE_SIGNING.md`, UX-15)
   - `CN=NormaOT (Кривоносов Д.А.), O=NormaOT, C=RU`, RSA 3072 / SHA-256, valid until 20.10.2036, thumbprint `981BDD1AEC938BD5BA0CAA2D84BDFB44CB6C83CB`; private key stays in the author's certificate store (DPAPI), `-Backup` exports a password-protected .pfx
   - Public part committed as `docs/signing/NormaOT_CodeSigning.cer` (SHA-256 `E9A5F298230A3385A35924568E70007A7D941C07B5CC45A33D001D43DB896271`)
   - `docs/CODE_SIGNING.md`: how corporate IT verifies the thumbprint and trusts the publisher (manual, GPO, Intune), how to revoke trust, and what the signature does NOT give (no public CA, SmartScreen still warns for ordinary users)
   - The 3.8.0 build is the first signed one (self-signed; SmartScreen still warns ordinary users)

### Release

- Version 3.8.0; portable build `dist/NormaOT-Reestr.zip` (71 825 884 bytes, SHA-256 `da76934f14d0806996cc7f9188edd22e11067d9be21d76f4387397652450cca8`), `NormaOT_Reestr.exe` Authenticode-signed with the self-signed publisher certificate (thumbprint `981BDD1AEC938BD5BA0CAA2D84BDFB44CB6C83CB`, timestamped) — see `docs/CODE_SIGNING.md`
- 559 tests pass

## v3.7.0 "License codes & multiple organizations" (2026-10-18)

1. **Support splash instead of the donation window** (`utils/donation_dialog.py`)
   - 10 s «Поддержите проект» splash at startup (not on first launch, not after an organization switch); «Продолжить» disabled during a visible countdown, Esc/close blocked; works offline
   - Removed «Больше не показывать», the 45-day cooldown and the placeholder QR code (`scripts/encode_qr.py` deleted)
2. **Offline license codes** (`utils/license.py`, `tools/license_tool.py`)
   - Tiers «Организация» (1500 ₽/year) and «Персональная» (499 ₽/year); code `NOT1.<payload>.<sig>` signed with Ed25519, app ships only the public key; payload: tier, holder, expiry, id
   - Activated code stored Fernet-encrypted in `license.json`; holder name never logged; audit `LICENSE_ACTIVATED` (tier/expiry/id only)
   - About: «Лицензия: …» status line, «Лицензия и поддержка» button
   - `tools/license_tool.py init|issue|verify` — author's tool; private key and `issued.csv` live outside the repo (`%USERPROFILE%/NormaOT_license_keys`)
   - No payment acceptance yet (owner not registered as self-employed)
3. **Multiple organizations** (`utils/org_profiles.py`, `tabs/org_dialogs.py`, `main.py`)
   - Per-organization DB, API key, org/protocol/summary settings; global: master key, logs/audit, license, theme, window/table layouts, proxy settings
   - The first organization stays in the root data dir (no migration); added ones in `orgs/<id>/`; names encrypted in `organizations.json`
   - Menu «Организация»: add / switch (relaunch with `--org=<id>`) / delete; startup selection dialog when there are 2+ organizations; window title shows the organization
   - Delete dialog: one organization or everything (factory reset), confirmed by typing «УДАЛИТЬ»
   - Without an «Организация» license: 60 s splash before adding, 30 s before switching
   - Audit `ORG_ADDED` / `ORG_SWITCHED` / `ORG_DELETED` (ids only)
4. Help (F1): sections «Несколько организаций», «Лицензия и поддержка»
5. Fixed: `main.py` used `safe_message_box` without importing it (factory reset error branch)
6. Tests: `tests/test_license.py` (21), `tests/test_org_profiles.py` (14)
7. Version 3.7.0; portable build `dist/NormaOT-Reestr.zip` (71 802 863 bytes, SHA-256 `15c850579fb0957ceb8dc30ba6181e5a1ecee9e70a92b31aaf8ff92c2eb0e266`)

## v3.6.0 "NormaOT data dir, Journal ↔ Registry, Security Fixes" (2026-10-18)

### Changes

1. **Data directory renamed to `%APPDATA%\NormaOT`** (`utils/app_paths.py`) — UX-01
   - Automatic one-time migration from legacy `%APPDATA%\Excel_to_XML` via atomic rename (keeps file ACLs, no duplicate PD copies)
   - Locked files (old version running) → legacy dir used for the session, migration retried on next start; both dirs with data → legacy untouched, user warned
   - New audit events: `DATA_DIR_MIGRATED`, `DATA_DIR_MIGRATION_FAILED`
   - `utils/crypto.py:_key_dir()` now delegates to `get_app_data_dir()` (removed duplicated path logic); DPAPI entropy intentionally unchanged
   - `get_app_log_dir()` derives from `get_app_data_dir()`

2. **Test isolation** (`tests/conftest.py`)
   - Test session uses a temporary `APPDATA`; previously crypto tests wrote `master.key` into the real user data dir
   - New `tests/test_app_paths.py` (9 tests)

3. **Compact dialogs for low resolutions** (`utils/dialog_base.py`, `about_dialog.py`, `security_dialog.py`) — UX-02, UX-03
   - `BaseDialog(scrollable=True)`: scrollable body, fixed bottom buttons, height capped at 90% of the screen and fitted to wrapped text
   - About and Security dialogs laid out in two columns

4. **Employee summary** (`tabs/employee_summary_tab.py`) — UX-04, UX-05
   - Removed "Обучение по программам В (№6-29) — 1 раз в 3 года" checkbox: type В programs always use the 3-year period; legacy `b_period_3years` in `summary_programs.json` ignored
   - Stats cards half as tall (value and caption on one line); fixed card values never being colored (objectName was overwritten)

5. **Persistent column widths** (`utils/ui_helpers.py:HeaderStatePersistence`) — UX-08
   - "Просмотр данных": columns now user-resizable (was Stretch); widths/order/visibility saved to `table_layouts.json`
   - Same persistence applied to "Журнал проверки знаний"
   - New `tests/test_ux_layout.py` (6 tests)

6. **Registry queries in one row** (`tabs/data_transfer_tab.py:_create_query_group`) — UX-06
   - "Запрос по SetId" and "Запрос по СНИЛС" merged into one "Запрос в реестр" group
   - SNILS field sized for 14 chars (`XXX-XXX-XXX XX`, maxLength 14); SetId field sized for 10 chars, length not limited
   - New helper `utils/ui_helpers.set_char_width()`

7. **Journal ↔ registry sync** (`journal/registry_sync.py`, `tabs/registry_query_dialog.py`, `tabs/exam_journal_tab.py`) — UX-07
   - New "Запросить по…" button: dialog with SetId (default) / СНИЛС radio buttons, input validation (SetId digits only; SNILS 11 digits + checksum), query runs in a background thread
   - "Импорт из Excel" now merges the SetId response file (saved from "Передача данных") into existing journal records instead of adding duplicates; SetId taken from the file name when numeric
   - Matching: SNILS + program + (protocol number or exam date); matched records get reg. number, status "получен" and SetId if empty; unmatched records are added after confirmation (default "No" for SNILS queries)
   - `ExamJournalRepo.update_registry_info()`, `JournalManager.match_registry_records()` / `apply_registry_updates()`
   - Audit: `IMPORT_XLSX` / `QUERY_SETID` / `QUERY_SNILS` with counts only (no PD)
   - Help (F1) and README updated; new `tests/test_registry_sync.py` (27 tests)
   - Fixed: SNILS query button on "Передача данных" was renamed to "Запросить" after a request

### Fixes (found while stabilizing the test suite)

8. **Audit log false "tampered" alarms** (`utils/audit.py`)
   - The written timestamp (`asctime`) could differ from the HMAC timestamp across a second boundary → `verify_audit_log()` flagged genuine entries. Now the line carries the exact HMAC timestamp (`_AuditFormatter`)
   - The handler-level `SensitiveDataFilter` could rewrite the signed hex tag (digit run taken for a phone number). Signed entries are already sanitized by `filter_sensitive_text()` before signing and are no longer re-filtered (`_AuditSensitiveFilter`); unsigned `[no-hmac]` entries still are
   - The hash chain restarted from zeros on every launch, so the first entry of each session was reported as tampered. `setup_audit_log()` now continues the chain from the last tag in `audit.log` (or `audit.log.1` after rotation); `verify_audit_log()` starts from the predecessor file and accepts the old per-launch restarts in pre-3.6.0 logs (deleted entries are still detected)
   - 6 regression tests in `tests/test_audit_verification.py`

9. **Secure temp dir race** (`utils/secure_temp.py`)
   - Directory creation moved under the lock: concurrent callers created several dirs (only the last one cleaned at exit) and `SetFileSecurity` could fail
   - Tests no longer leave empty `excel_xml_secure_*` dirs in `%TEMP%`

10. **"[INTEGRITY FAIL]" for every master key** (`utils/crypto.py`)
   - Cause: a new key's metadata was signed before the key was stored in `_MASTER_KEY`, and `_compute_metadata_hmac()` then fell back to the first 32 bytes of the *DPAPI-encrypted* `master.key`; verification later used the real key, so the tag never matched (same in the DPAPI entropy migration path)
   - Metadata HMAC is now always keyed by the raw master key (`_raw_master_key_for_hmac()`: explicit key → loaded key → DPAPI decryption); encrypted file bytes are never used as a key; no tag is written if the key is unavailable
   - Existing 3.2–3.5 metadata (ciphertext-keyed tag) is accepted once and re-signed with the raw key — only after DPAPI decryption succeeded; a changed field is still detected
   - Unreadable key → integrity reported as failed instead of silently using another key
   - New `tests/test_key_metadata_integrity.py` (9 tests); DPAPI entropy, PBKDF2 parameters and `master.key` format unchanged
11. **Stale training statuses** (`utils/training_rules.py:get_dynamic_status`)
   - "trained"/"expired" were re-derived from the exam date only in the old 1-year mode; with the 3-year period a program synced as "trained" stayed "trained" after expiry until the next registry query. Now always re-derived from the exam date (summary table, stats, employee status, snapshot report, background builder)
   - Empty stored status (`None`) is derived from the exam date and result instead of being ignored; failed exams stay "not_trained"
   - `is_program_expired()` no longer raises `TypeError` for an empty date
   - `db/schema.py`: missing `import sqlite3` (NameError in the error branch)

12. **Key metadata / passphrase hardening** (`utils/crypto.py`)
   - Metadata without an integrity tag is accepted only if it is genuine pre-3.x metadata (then signed at once); for 3.x metadata a missing tag is reported as an integrity failure (removing the tag used to bypass the check)
   - `is_passphrase_protected()` also checks `passphrase_wrapped.key`: deleting/rewriting `master.key.json` no longer switches off the passphrase prompt
   - `remove_passphrase()` raises `CryptoError` if the wrapped key file could not be deleted
   - 13 new regression tests (`tests/test_training_rules.py`, `tests/test_key_metadata_integrity.py`); one old test that encoded the stale-status bug was corrected

13. **UI and text review before release** (all tabs and dialogs, light/dark/dracula/monokai)
   - Help (F1): "Хранение данных" described a wrong location (`data/` next to the EXE) and whole-file DB encryption — now `%APPDATA%\NormaOT`, field-level Fernet, DPAPI-protected key, migration note; button and section names aligned with the UI ("Сохранить", "Конвертировать в XML", "Сбросить фильтры", "Удалить выбранное", "План на текущий год", manual entry via "Добавить работника вручную"); protocol generation via "Печать протоколов" described; truncated TOC item renamed; intro text readable (was gray)
   - Fixed broken characters shown to users: "Поведение" (help), "XSD-валидация" (message title), "Протокол" (summary export header)
   - Summary: status-colored date cells were unreadable in dark themes (light text on light background); tab icon replaced (black triangle was invisible in dark themes); "Отчёт по обученным", "Импорт из XLSX", "Экспорт в XLSX"
   - Proxy settings: controls no longer float in the middle of the window; "Проверять TLS-сертификат сервера", "Подключение" instead of "Transport"
   - Journal: "Дата экзамена" and "№ программы" headers no longer truncated; log viewer: "Проверить аудит" button fits
   - Quick protocol: clear commission status ("не заполнены — укажите их на вкладке «Настройка протоколов»"); data entry: "Данные УЦ и заказчика" (matches its fields)
   - Log: the backup message was mangled by the sensitive-data filter ("password=*** backup created") and contained the full user path — now "Encrypted backup created: <file name>"
   - About: "постановление Правительства РФ № 2464"

## v3.5.0 "UX: Toasts, Unified Buttons & Hotkeys"

### Changes

1. **Toast notifications restored & fixed** (`utils/toast.py`)
   - Fixed the white-text-on-transparent-background bug via QPainter-based rounded background (works in light & dark themes)
   - Success and empty-state confirmations now use non-blocking toasts instead of modal `QMessageBox`
   - Affected tabs: `data_entry`, `data_view`, `data_transfer`, `exam_journal`, `employee_summary`, `protocol`
   - Dialogs with file paths / detailed summaries intentionally kept modal

2. **Unified button styling** (design system)
   - Buttons use design-system selectors (`primary` / `success` / `danger` properties, objectNames) instead of hardcoded inline colors
   - Removed off-palette `#4169E1`; aligned to palette `#4A90E2`
   - `data_entry_tab._btn_style()` neutralized; About "Сообщить об ошибке" button uses `dialogDangerBtn`

3. **Keyboard shortcuts** (`main.py`)
   - `Ctrl+1..7` switch tabs; `Ctrl+T` template; `Ctrl+E` export; `Ctrl+L` lock; `Ctrl+D` theme; `F1` help

## v3.4.0 "Per-Program Reports & Table Fixes"

### Changes (2026-05-28)

1. **Table header freeze** (`tabs/employee_summary_tab.py`)
   - `setSortingEnabled(False)` — manual sort via `sectionClicked`
   - Header rows (0-1) are preserved during sort, only data rows (2+) sorted
   - Sub-header row height reduced from 30px to 15px
   - Sort state tracked via `_sort_column` and `_sort_order`

2. **Export reads visible rows only** (`_export_xlsx()`)
   - Now reads from table widget rows (row 2+) instead of `EmployeesRepo.get_all()`
   - Deleted/filtered rows are excluded from exports

3. **Toast replaced** with `safe_message_box()` for export save confirmations
   - Fixes white-text-on-transparent-background issue on Windows

4. **Per-program reports** (`_show_current_snapshot`, `_generate_plan`)
   - Current Situation: one row per employee **per program** with per-program expiry
   - Plan reports: same per-program approach with individual expiry date filtering
   - Added "Название" (program name) column to PlanDialog table (10 columns)
   - Added "Название" column to XLSX export in PlanDialog

5. **Delete all app data** (`main.py`, `utils/security_dialog.py`)
   - Menu: `Инструменты → Удалить все данные приложения`
   - Button in Security dialog ("Безопасность")
   - Requires typing "УДАЛИТЬ" confirmation
   - Deletes ALL files from `%APPDATA%\Excel_to_XML`
   - Audit event: `FACTORY_RESET`

6. **Removed dead code**: `_get_program_data_for_status()` (no longer needed)

## v3.3.0 "Corporate Proxy Support"

### Corporate Proxy & SSL Inspection (2026-05-26)

1. **Auto-detection of corporate environment** (`utils/proxy_manager.py`)
   - Detects proxies with `.rzd`, `.oao`, `.corp`, `.company` domains
   - `is_corporate_proxy()` / `detect_proxy_and_env()` — used by all backends
   - Automatically forces WinINET backend in corporate environments (best Negotiate/Kerberos)

2. **SSL fallback with user confirmation** (`api/mintrud_api.py`)
   - When ALL backends fail with Schannel 10013 / SSL handshake error → returns `ssl_error_detected=True`
   - UI offers to disable TLS verification with explicit security warning
   - Retry with `verify=False` is logged via `log_audit("TLS_WARNING", ...)`
   - No silent TLS disable — user must confirm each time

3. **WinINET backend hardened** (`api/backends/wininet_backend.py`)
   - `SECURITY_FLAG_IGNORE_ALL_CERT_ERRORS` set both before and after `Open()`
   - New `_is_schannel_error()` — detects Schannel 10013, 0x80090326
   - Broad exception catching for COM edge cases
   - Robust multipart boundary building (explicit bytes, type-safe)

4. **Diagnostics improvement** (`network/client.py`)
   - `is_schannel_10013_error()` — detects the error in Ru/En
   - `get_schannel_recommendation()` — user-friendly instructions
   - `get_network_diagnostics()` now reports: `is_corporate_env`, `schannel_10013_detected`, `ssl_inspection_detected`

5. **UI improvements** (`tabs/data_transfer_tab.py`)
   - When SSL error detected → dialog: "Обнаружена SSL-инспекция. Отключить TLS?"
   - Test connection shows "Корпоративная среда: Да/Нет" and "SSL-инспекция: Да/Нет"
   - Audit log fixes: `%s` formatting instead of f-strings in sensitive events

6. **Documentation** (`docs/DEPLOYMENT.md`)
   - New section §9 "Корпоративные прокси с SSL Inspection"
   - 3 solutions: disable TLS / install corporate CA / WinHTTP proxy
   - Transport backends comparison table
   - Audit events reference (TLS_WARNING, TLS_ERROR, BACKEND_CHANGE, PROXY_CHANGE)

## v3.2.0 "Security Hardening"

### Cryptographic Security (2026-05-24)

1. **Removed in-memory PD decrypt cache** (`utils/crypto.py`)
   - `_ENCRYPT_CACHE` (2000 entries of plaintext PDn in RAM) removed
   - Replaced with `_NON_PD_CACHE` used only when `cache_ok=True` is explicitly passed
   - `decrypt_value()` now defaults to `cache_ok=False` — always calls Fernet for PD fields
   - Tests updated: verify Fernet is called on every `decrypt_value()` call without `cache_ok`

2. **Extended metadata HMAC to 128-bit** (`utils/crypto.py`)
   - `_compute_metadata_hmac()` now returns 32 hex chars (was 16) — NIST SP 800-107 compliant
   - Added `_HMAC_TAG_LENGTH = 32` and `_HMAC_TAG_LENGTH_LEGACY = 16` constants
   - Legacy 64-bit HMAC auto-migrates to 128-bit on first integrity check

3. **Zero old key material after rotation** (`utils/crypto.py`)
   - `rotate_master_key()` now wraps old key in `bytearray` for mutability
   - `try/finally` block guarantees `_zero_memory()` / `_zero_memory_bytes()` always called
   - Old key and old encoded key zeroed regardless of success or rollback

4. **Strengthened backup password to 256-bit** (`utils/crypto.py`, `db/database.py`)
   - PBKDF2 iterations increased from 100K to 600K (matching passphrase derivation)
   - Key length increased from 16 bytes (64-bit) to 32 bytes (256-bit) → 64 hex chars
   - Salt updated to `EXCEL_XML_BACKUP_V4_SALT_2024`
   - Added NOTE about key rotation making old backups unrecoverable

5. **Blocked plaintext master key when PD data exists** (`utils/crypto.py`)
   - New `_has_any_encrypted_data()` checks `workers_data` for encrypted records
   - `_load_existing_key()` now raises `CryptoProductionModeError` if plaintext key found AND PD records exist in DB — regardless of dev/prod mode

6. **Required explicit confirmation before disabling TLS** (`api/mintrud_api.py`, `tabs/data_transfer_tab.py`)
   - Confirmation dialog now defaults to "No" and explicitly warns about PD data interception risk
   - TLS setting saved immediately after confirmation (not on batch save)
   - `TLS_WARNING` audit event logged at `MintrudApiClient` initialization if TLS disabled
   - Removed stale TODO comment

## v3.1.0 "Version Bump"

### Version Update (2026-05-22)
- Application version updated from 3.0.0 to 3.1.0 across all sources
- Updated VERSION constant, version_info.txt, documentation headers, and report metadata

## v3.0.1 "Security Audit & Compliance"

### Documentation (2026-05-22)
- Internal security audit report (kept outside the public repository)
- **COMPLIANCE.md** — Comprehensive 152-ФЗ / ПП №1119 / ФСТЭК №21 compliance matrix
- **PRIVACY.md** — Privacy policy document per 152-ФЗ (privacy-by-design)
- **DEPLOYMENT.md** — Secure deployment guide (hardened)
- **AGENTS.md** — Updated with audit findings and compliance requirements

### Security Audit Findings Summary
- **CRITICAL**: Audit HMAC is NEVER verified (security theater)
- **HIGH**: 17/34 audit events never emitted (dead code); SNILS leak in xlsx_importer error messages
- **HIGH**: Master key lives in module-level global, not zeroed; no thread safety in crypto
- **HIGH**: XML pattern in SensitiveDataFilter is broken (trailing regex anchor)
- **MEDIUM**: TOCTOU in XSD validation (file read twice); PKWARE ZipCrypto for backups
- **MEDIUM**: No retention policy, no secure delete, no clipboard auto-clear

## v2.2.0 "Logging & Observability"

### Logging System Overhaul
- **Improved log format**: `timestamp | thread | level | module | message` — thread name and module path for easier debugging
- **Increased rotation**: `backup_count` 3→5 (5 rotating files × 5MB = 25MB max history)
- **`tail_log()` utility**: Efficiently reads last N lines from file using `seek()` (never loads entire file)
- **`get_log_files()` utility**: Lists all log files including rotated backups sorted by recency

### Log Viewer (LogViewerDialog)
- **New file**: `utils/log_viewer_dialog.py` — full-featured in-app log viewer
- **Tail-based loading**: Reads from end of file using seek, supports files of any size
- **Auto-refresh**: QTimer-based, every 2 seconds, reads only new bytes since last position
- **Level filter**: Combo box for DEBUG/INFO/WARNING/ERROR/CRITICAL
- **Text search**: Real-time case-insensitive filtering
- **Log highlighting**: QSyntaxHighlighter with color-coded levels (DEBUG=gray, WARNING=orange, ERROR=red, CRITICAL=bold red bg)
- **Smart auto-scroll**: Tracks scrollbar position — disables auto-scroll when user scrolls up
- **Actions**: Clear logs (with confirmation), Open log folder, Save ZIP archive, Copy all
- **Status bar**: Shows "shown / buffer total" with active filters

### Toolbar & Menu
- **QToolBar**: New toolbar with buttons: О программе, Настройки, Помощь, Логи
- **Menu**: New "Инструменты → Просмотр логов" menu item
- Non-movable, non-floatable toolbar placed between menu bar and tab widget

## v2.1.0 "Stable XLSX Import"

### XLSX Import Stability
- **Threaded import**: XLSX loading moved to `QThread` — UI stays responsive even on large files
- **Real progress reporting**: `ExcelImportWorker` emits `progress(current, total)` and `status_message` signals; progress bar shows actual row count
- **Cancel button**: "✕ Отменить импорт" with graceful cancellation — thread stops cleanly, UI resets
- **Streaming**: Always uses `openpyxl read_only=True` — workbook never fully loaded into memory
- **Explicit resource cleanup**: Workbook closed via `try/finally`, no stale file handles
- **Limits enforced**: File size (`MAX_XLSX_FILE_SIZE_MB=10`) checked before open; row count (`MAX_XLSX_ROWS=100000`) checked during streaming
- **Logging**: Full INFO/WARNING/ERROR logging for every import stage
- **Custom exception**: `ImportCancelledError` for clean cancellation handling
- **Integration**: `data_entry_tab.py` uses `ExcelImportWorker` via `QThread`, not direct `load_xlsx()` call
- **Backward compatible**: `load_xlsx()` API extended with optional `progress_callback` and `cancel_check` parameters

## v2.0.0 "Performance & Virtualization"

### Performance Improvements
- **Model/View architecture**: Replaced QTableWidget with QTableView + QAbstractTableModel in:
  - `data_view_tab.py` — DataViewTableModel with virtual scrolling for 5000+ records
  - `exam_journal_tab.py` — ExamJournalTableModel with deferred model reset
- **MultiColumnFilterProxyModel**: Text filtering now searches all columns via overridden `filterAcceptsRow()` instead of row-by-row iteration
- **Batch DB queries**: `EmployeeProgramsRepo.get_by_employee_ids()` and `EmployeesRepo.get_all_with_programs()` reduce N+1 queries to single JOIN
- **SQL-level filtering**: `ExamJournalRepo.search()` uses WHERE clause for set_id, status, date ranges (uses indexes)
- **PRAGMA optimization**: `synchronous=NORMAL`, 8MB cache, `temp_store=MEMORY`, `PRAGMA optimize` on app close
- **DB schema indexes**: Composite index `idx_ep_employee_program`, date indexes on `exam_journal`
- **Fernet caching**: Singleton cipher + LRU encrypt/decrypt caches avoid re-deriving keys
- **Workers**: `ExcelImportWorker`, `XmlGenerationWorker`, `ApiBulkQueryWorker`, `PlanGenerationWorker` for background threading
- **LRU caches**: Summary cache and API response caches with TTL in `utils/cache.py`
- **`--profile` CLI flag**: Enables cProfile profiling, saves `profile.prof` to log directory
- **Read-only XLSX import**: Files > 512 KB use `openpyxl read_only=True` to avoid loading entire workbook

## v1.3.0 "Security & UX polish"

### Security Improvements (from v1.2.4)
- Added `check_master_key_security()` — detects DPAPI/raw key mode
- Added `create_master_key_backup()` / `restore_master_key_backup()` for master.key
- Added security status indicator and backup button in AboutDialog
- Added `validate_api_key_remote()` — auto-tests API key on save via server request
- Replaced `xml.etree.ElementTree` with `defusedxml` in all parsers (XXE protection)
- Added `security_audit()` call on startup — logs master.key, API key, DB encryption status
- Database backups now use password-protected ZIP (SHA256 of master key)
- Added color-coded API key indicator in StatusBar (green/red circle)
- Updated `docs/SECURITY.md` with complete architecture documentation

### UX Improvements (v1.3.0)
- **Centralized error handling**: `utils/error_utils.py` — `show_error_dialog()` with traceback details
- **Toast notifications**: `utils/toast.py` — animated sliding notifications (info/success/warning/error)
- **Visual field validation**: `utils/field_validators.py` — `ValidatedLineEdit` with red border + tooltip
- All dialogs now inherit from `BaseDialog` (PlanDialog, EmployeeAddDialog, EmployeeEditDialog, EditDialog, ProgramsDialog)
- Improved AboutDialog with security section and master.key backup button
- Enhanced StatusBar with version display, progress bar, and better API key indicator
- **Drag & Drop** file loading on DataEntry tab (XLSX/XML)
- **Copy SNILS** on double-click in DataView tab (column 3)
- Auto-save notifications via Toast

### Code Quality
- Added type hints to `utils/crypto.py`, `db/database.py`, `utils/app_paths.py`
- Added `show_progress()` / `show_progress_indeterminate()` helpers to MainWindow
- Improved docstrings across key modules
- Added `QCoreApplication.processEvents()` for UI responsiveness during long operations

## v1.2.0
- Added checkbox "Обучение по программам В (№6-29) — 1 раз в 3 года" on Employee Summary tab
- When unchecked: programs 6-29 use 1-year training period instead of 3 years
- Dynamic recalculation of employee statuses, training plans, current snapshot, and trained report
- Modular implementation in `utils/training_rules.py` — easily removable
- Updated help, README, and technical specification docs

## v1.1.0
- Added .sig file selection field for electronic signature on Data Transfer tab
- Added red "Отправить XML и ПОДПИСАТЬ" button for sending XML with signature to РОЛ
- Implemented .sig file inclusion in .olot archive (ZIP with Data.xml + signature)
- Added `<NeedSend>true</NeedSend>` flag for immediate РОЛ forwarding in signed mode
- Added confirmation dialog before signed send
- Response parsing includes `<SendEducatedPerson>` and `<Message>` elements

## v1.0.1
- Documentation restructure: README split into main + docs/SECURITY.md + docs/API_MINTTRUD.md
- Updated Техническое_задание_2.md with implemented features
- Added app icon to README

## v1.0.0
- Initial release: Employee Summary, Training Plan, XML generation, Mintrud API, encryption, themes
