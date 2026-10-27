# Project Context for AI Agents

## Tech Stack
- Python 3.12, PySide6, SQLite (via custom DatabaseManager)
- openpyxl, lxml, cryptography, dateutil, requests
- PyInstaller for EXE builds

## Build & Test
- Tests: `py -m pytest tests -v`
- Production mode: `set EXCEL_XML_PROD=1` before running (blocks plaintext keys)

### EXE Build & Release
1. Remove old build: `Remove-Item -Path "dist\NormaOT_Reestr" -Recurse -Force`
2. Build EXE: `py -m PyInstaller NormaOT_Reestr.spec --noconfirm` (spec is versioned; onedir build, data dirs `schema/`, `templates/`, `resources/` go to `_internal/`; EXE file version is read from `utils/about_dialog.py:VERSION` — bump it first)
3. Sign the EXE (UX-15): `powershell -ExecutionPolicy Bypass -File tools\sign_build.ps1`
   - Certificate is never in the repo: `$env:NORMAOT_SIGN_THUMBPRINT` (store/USB token) or `-PfxPath`. Current self-signed cert: thumbprint `981BDD1AEC938BD5BA0CAA2D84BDFB44CB6C83CB` in `Cert:\CurrentUser\My` (created by `tools/make_signing_cert.ps1`; public part `docs/signing/NormaOT_CodeSigning.cer`, IT instructions `docs/CODE_SIGNING.md`)
   - Exit code 2 = no certificate configured, build stays unsigned (SmartScreen warns); any other failure must stop the release
   - Signing is always timestamped; re-sign after every rebuild (PyInstaller rewrites the EXE), i.e. sign BEFORE zipping
4. Create zip: `Compress-Archive -Path "dist\NormaOT_Reestr\*" -DestinationPath "dist\NormaOT-Reestr.zip" -Force` (a zip cannot be Authenticode-signed — publish its SHA-256 instead)
5. Publish the zip on the website only: copy it to `D:\Project\public_html\NormaOT-Reestr.zip` (served by `download.php?f=reestr`), then update version/date/size/SHA-256 in `tools/site_gen/common.py`, `reestr.html`, `changelog.html` and README.md
6. Commit source and docs only. `dist/` is gitignored: never commit release archives or build output (binaries were purged from git history on 2026-10-24 to keep the GitFlic/GitHub repositories small)

### Linux Build & Release (L-06, scripts in `tools/linux/`)
- Use a PORTABLE Python (`uv python install 3.12; uv venv ~/venv-build --python 3.12; uv pip install --python ~/venv-build/bin/python -r requirements.txt`); the distro Python raises the glibc floor. The spec drops the build host's system libs from the bundle, so the floor is set by the wheels (2.34 now; `tools/linux/glibc_floor.sh` prints it)
- One command: `tools/linux/build_all.sh` → `dist/normaot-reestr-<ver>-linux-<arch>.tar.gz`, `normaot-reestr_<ver>_amd64.deb` (Astra), `normaot-reestr-<ver>-alt1.x86_64.rpm` (ALT, soname-based Requires), each with `.sha256`. Steps separately: `build_linux.sh`, `make_deb.sh`, `make_rpm.sh` (`RPMBUILD=` path if rpmbuild is not installed)
- `libxcb-cursor.so.0` is fetched from Debian 12 with a pinned SHA-256 (`fetch_extra_libs.sh`) and bundled
- Signature: `NORMAOT_GPG_KEY=<fingerprint> tools/linux/sign_release.sh dist/<file>` (key never in the repo; exit 2 = not signed, publish SHA-256 only)
- Shell scripts must keep LF line endings (`.gitattributes`)
- `.deb` is built with `dpkg-deb -Zxz`: Ubuntu's default zstd cannot be read by dpkg < 1.21.18 (Astra SE 1.7, Debian 9-11). Astra CE 2.12 «orel» (glibc 2.24) is below the glibc floor

## SECURITY: Critical Rules
1. **ALL XML from external sources** MUST use `defusedxml.ElementTree` (not stdlib `xml.etree`)
2. **ALL XML from external sources** MUST go through `utils.xml_safe.safe_parse_xml()` or `safe_fromstring_xml()`
3. **NO f-string logging** with user data — use `%s` formatting with `filter_sensitive_text()`
4. **NO raw exceptions** in UI — use `utils.error_utils.show_exception_dialog()`
5. **NO plaintext master key** in production mode — raises `CryptoProductionModeError`
6. **NO hardcoded secrets** — backup password MUST derive from master key via PBKDF2
7. **TLS verify=True** by default — disabling MUST log audit event `TLS_WARNING`
8. **ALL SQL queries** MUST use parameterized queries (no string concatenation)
9. **ALL sensitive logging** MUST pass through `SensitiveDataFilter`
10. **Thread-local connections** MUST be closed at end of background thread via `DatabaseManager.close_thread_connection()`

## Key Architecture
- `importers/` — XLSX/XML file loading (employees import; `.xls` removed, use `.xlsx` only)
  - XLSX uses `openpyxl read_only=True` (streaming), background `QThread`, progress reporting, cancel support
  - Limits: `MAX_XLSX_FILE_SIZE_MB=10`, `MAX_XLSX_ROWS=100000`
- `exporters/` — XML/XLSX generation
- `api/` — Mintrud API client (mintrud_api.py, payload_builder.py, response_parser.py, backends/)
- `db/` — SQLite via DatabaseManager, EmployeesRepo, EmployeeProgramsRepo
- `tabs/` — screens (pages of the main window): employee_summary_tab, data_entry_tab, data_view_tab, data_transfer_tab, exam_journal_tab, protocol_tab, single_worker_protocol_tab
- `utils/` — crypto, proxy_manager, logger, audit, app_paths, log_viewer_dialog, secure_temp

## Database Architecture (`db/database.py`)

### Connection Lifecycle
- **Thread-local connections** via `threading.local()` — each thread gets its own connection on first use
- **`_thread_connections` dict** (class-level, `_connections_lock` protected) — tracks all open connections by thread ID
- **Auto-closed** on app shutdown via `atexit.register(cls.close_all)` in `get_instance()`

### Key Methods
| Method | Description |
|---|---|
| `get_instance(db_path)` | Singleton, registers `atexit` cleanup on first creation |
| `_get_connection()` | Creates thread-local connection with WAL+FK+optimized PRAGMAs |
| `get_conn()` | Context manager — yields connection, rolls back on `DatabaseError` |
| `transaction()` | Context manager — commits on success, retries on lock (`_BUSY_RETRIES=3`), rolls back on error |
| `execute(sql, params)` | Implicit cursor via `get_conn()` |
| `executemany(sql, seq)` | Batch execute via `get_conn()` |
| `fetchone(sql, params)` | Returns `dict` or `None` |
| `fetchall(sql, params)` | Returns `list[dict]` |
| **`close_thread_connection()`** | Closes current thread's connection, removes from `_thread_connections` dict. Call in background threads at end of `run()`. |
| **`close()`** | Instance method — delegates to `close_thread_connection()` |
| **`close_all()`** | Classmethod, closes ALL tracked connections, clears dict + thread-local. Idempotent. |

### Rules for Background Threads
- **Always** call `DatabaseManager.close_thread_connection()` at the end of `QThread.run()` if the thread used the database
- Currently applied in: `tabs/employee_summary_tab.py:ApiQueryThread.run()`
- Connections created in tests are cleaned up by fixture teardown calling `db.close_all()`

### Error Handling
- `DatabaseLockError` — raised after `_BUSY_RETRIES` exhausted (all retries got "database is locked")
- Lock retries: 3 attempts, 100ms delay between retries
- Logging: connection open/close at DEBUG, rollback at ERROR, lock timeout at WARNING
- `except BaseException` changed to `except Exception` — no longer catches `KeyboardInterrupt`/`SystemExit`

### Backup Security
- Backup password derived from master key via `get_key_fingerprint()` or PBKDF2
- NEVER use hardcoded or date-based passwords
- Backup rotation: max 5 copies

## Crypto Architecture (`utils/crypto.py`)

### Key Hierarchy
```
Windows DPAPI (user + machine + entropy)
    └── Master Key (32 bytes, Fernet AES-128-CBC)
         ├── [Optional] Passphrase (PBKDF2-HMAC-SHA256, 600K iterations)
         │    └── Passphrase-wrapped key
         ├── API key (Fernet-encrypted)
         ├── Proxy credentials (Fernet-encrypted)
         └── Field-level encryption (ФИО, СНИЛС)
```

### Production Mode
- Set `EXCEL_XML_PROD=1` to enable strict mode
- Blocks: plaintext master keys, missing DPAPI, insecure fallbacks
- Raises `CryptoProductionModeError` on violation

### Key Metadata
- Stored in `master.key.json` with HMAC-SHA256 integrity tag
- Version tracking, creation/rotation timestamps, key fingerprint
- `verify_metadata_integrity()` checks HMAC before use
- Linux passphrase-file store: the startup passphrase wraps master.key, so `uses_keystore_passphrase()` hides the optional second passphrase in About/Security; the session lock uses `has_lock_passphrase()` / `verify_lock_passphrase()` (optional passphrase first, else the key-store one)
- HMAC key = RAW master key only (`_raw_master_key_for_hmac()`); pass `key=` to `_save_key_metadata()` whenever `_MASTER_KEY` is not set yet (key creation, entropy migration). NEVER key it by the DPAPI-encrypted file bytes (v3.2–3.5 bug → permanent "INTEGRITY FAIL"); such old tags are migrated in `verify_metadata_integrity()` after successful DPAPI decryption
- Corrupted keys archived to `corrupted_keys/` directory

### Security Rules
- `encrypt_value()` / `decrypt_value()` — field-level Fernet
- `hash_for_search()` — SHA-256 of normalized value (for DB indexing)
- Cache: only ciphertext (never plaintext), max 2000 items
- Backup: PBKDF2-derived password from master key (NO hardcoded constants)

### Factory Reset / Delete All Data
- Menu: `Инструменты → Удалить все данные приложения` (`main.py:_delete_all_app_data`)
- Button in Security dialog (`utils/security_dialog.py:_delete_all_data`)
- Deletes ALL files in `get_app_data_dir()` (Roaming\NormaOT)
- Requires typing "УДАЛИТЬ" confirmation
- App closes immediately after deletion
- Audit event: `FACTORY_RESET`

## Data Directory (`utils/app_paths.py`)
- Data dir: `%APPDATA%\NormaOT` (`APP_DIR_NAME`); logs: `%APPDATA%\NormaOT\log`
- **Single source of truth** — always use `get_app_data_dir()` / `get_app_log_dir()`; `utils/crypto.py:_key_dir()` delegates to it. Never build the path from `APPDATA` manually.
- **Legacy migration** (v3.6.0+): on the first `get_app_data_dir()` call in a process, `%APPDATA%\Excel_to_XML` is **renamed** (atomic, keeps ACLs, no PD copies) to `NormaOT`
  - new dir missing or empty → rename → status `migrated`, audit `DATA_DIR_MIGRATED`
  - both dirs contain data → nothing touched, new dir used → status `skipped`, user warned to delete the legacy dir
  - rename fails (file locked by a running old version) → legacy dir used this session → status `failed`, retried on next start
  - logging is not configured at resolution time, so `main.py:_report_data_dir_migration()` logs/audits via `get_migration_status()` after `setup_audit_log()`
- **DO NOT rename** `_DPAPI_ENTROPY = b"Excel_to_XML_MasterKey_v3_secure"` or other crypto constants containing `Excel_to_XML` — existing master keys would become undecryptable
- Tests: `tests/conftest.py` redirects `APPDATA` to a temp dir for the whole session — tests must never touch the real data dir

## Organizations & License (UX-10, `utils/org_profiles.py`, `utils/license.py`)
- Per-organization files: ALWAYS resolve via `get_org_data_dir()` (DB, `api_key.json`, `org_settings.json`, protocol/commission/programs/summary/journal settings). Global files via `get_app_data_dir()`: master key, logs/audit, `license.json`, theme, window/table layouts, proxy settings, `organizations.json`
- First organization = root data dir; added ones = `orgs/<12-hex id>/`. Organization names are encrypted (may be PD for ИП)
- Active organization is fixed per process (`--org=<id>` or startup dialog) BEFORE the DB/tabs are created; switching = relaunch (`main._RELAUNCH`, `--no-splash`)
- License codes: Ed25519 signature check offline; app ships only the public key (`PUBLIC_KEY_B64`); private key never in repo/site (`tools/license_tool.py`, key dir outside repo); holder name is PD — never log it
- Splash «Поддержите проект»: 10 s at startup, 30 s org switch, 60 s org add; skipped with a suitable license (`show_support_if_needed(require_org=...)`)

## Logging Security (`utils/logger.py`)

### SensitiveDataFilter (27+ patterns)
- SNILS, passports, phones, emails, API keys, tokens, JWT
- Full Russian names (ФИО), initials
- Passwords, proxies, cookies, session IDs
- JSON sensitive key values (recursive)
- XML/SOAP payload tagging

### Production Logging
- Main handler: INFO level (NOT DEBUG)
- Error handler: ERROR level
- Third-party libs: urllib3, requests, openpyxl → WARNING
- Safe exception formatting via `safe_format_exception()`
- `filter_sensitive_text()` for all log messages

### Prohibited in Logs
- Raw PDn (SNILS, names)
- Endpoint URLs
- File paths containing sensitive data
- Full traceback in user-facing dialogs
- Raw HTTP request/response bodies

## Audit System (`utils/audit.py`)

### 35 Security Events
`SEND_XML`, `SEND_XML_SIGNED`, `QUERY_SETID`, `QUERY_SNILS`,
`IMPORT_XLSX`, `IMPORT_XML`, `EXPORT_XML`, `EXPORT_XLSX`,
`LOGIN`, `BACKUP`, `KEY_ACCESS`, `KEY_ROTATION`,
`KEY_BACKUP`, `KEY_RESTORE`, `PASSPHRASE_SET`, `PASSPHRASE_REMOVED`,
`TLS_WARNING`, `TLS_ERROR`, `XML_VALIDATION_ERROR`, `XML_SECURITY_ERROR`,
`EXPORT_PLAN`, `EXPORT_SNAPSHOT`, `EXPORT_TRAINED_REPORT`,
`IMPORT_CANCELLED`, `SECURITY_WARNING`, `STARTUP`, `SHUTDOWN`,
`CRASH`, `ERROR_RESPONSE_SAVED`, `PROXY_CHANGE`, `BACKEND_CHANGE`,
`AUDIT_INTEGRITY_CHECK`, `FACTORY_RESET`

### HMAC Protection
Each audit entry includes HMAC-SHA256 tag: `[hmac_tag] EVENT | detail`
- The line timestamp MUST be the one used for the HMAC chain (`log_audit()` passes `extra={"audit_ts": ...}`, `_AuditFormatter` writes it) — never rely on `asctime`
- Signed entries are sanitized BEFORE signing and must not be modified afterwards; `_AuditSensitiveFilter` skips them (any post-sign change breaks `verify_audit_log()`)
- The chain continues across restarts: `setup_audit_log()` seeds `_PREV_HASH` from the last tag of `audit.log` / `audit.log.1`; never reset it to zeros in app code

## XML Security (`utils/xml_safe.py`)

### Required for ALL external XML
- `safe_parse_xml(file_path)` — file-based parsing with defusedxml
- `safe_fromstring_xml(data)` — string-based parsing with defusedxml
- `LimitedXMLParser` — limits: 50000 elements, depth 20, size 100MB

### Require check for lxml usage
When using `lxml.etree` for XSD validation, ALWAYS use:
```python
parser = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    dtd_validation=False,
    huge_tree=False,
)
```

### Prohibited
- `xml.dom.minidom.parseString()` for external XML
- `lxml.etree.parse()` without secure parser settings
- `xml.etree.ElementTree` without defusedxml wrapper

## Temp File Security (`utils/secure_temp.py`)
- Per-process isolated temp directory: `%TEMP%/excel_xml_secure_<UUID>`
- ACL-restricted to current user
- Secure deletion: 3-pass overwrite before delete
- Auto-cleanup on process exit via `atexit`

## Requirements (Implemented)

### FR-001: Employee Status (Employee-level, NOT program-level)
- Status per employee is determined by scanning ALL their `need_training=1` programs:
  - If **any** program has `status='not_trained'` (null exam_date) → employee = "Не обучен"
  - Else if **any** program has `status='expired'` → employee = "Просрочено"
  - Else all programs are `trained` → employee = "Обучен"
- Priority: `not_trained` > `expired` > `trained`

### FR-002: Stats Cards Count Employees, Not Programs
- `_update_stats()` iterates all employees, calls `_get_employee_status()` per employee
- Counts how many employees are in each status category
- Same logic used in `_build_table()` for per-row overall_status

### FR-003: Current Snapshot Report (Per-Program)
- Button "Текущая ситуация" (replaces old "Обновить данные")
- Generates a report dialog showing **every program** per employee with expiry dates
- One row per employee **per program** with `need_training=1`
- Uses PlanDialog for display (10 columns: includes "Название" column)
- For each program: computes effective status and expiry date individually
- Status priority used for sorting only: Не обучен (Высокий) > Просрочено (Высокий) > Обучен (Низкий)

### FR-004: Plan Generation (Per-Program)
- `_generate_plan()` iterates employees, iterates ALL `need_training=1` programs per employee
- Per-program rows (not one per employee):
  - **not_trained employees**: one row per program with 60d expiry
  - **expired employees**: one row per program with 30d expiry
  - **trained employees**: one row per program IF `compute_expiry_date().year == plan_year`
  - **failed results**: one row per program with `result=0`
- Columns in PlanDialog: №, ФИО, СНИЛС, Должность, Программа, **Название**, Последняя дата обучения, Дата окончания действия, Основание, Приоритет

### Export Fix: Visible Rows Only
- `_export_xlsx()` reads the rows currently shown in the table (the sort/filter proxy of the summary model), not the DB
- Deleted/filtered-out rows are excluded from exports
- Both modes use table data: «Экспорт в XLSX (как в таблице)» and «Экспорт всех программ» (Экспорт ▾ menu)

### Table sorting and frozen columns (3.9.0)
- Header click cycles ascending → descending → natural order (`TriStateSort`); the summary table has no header rows in the data any more (grouped two-level header, frozen «Сотрудник / СНИЛС / Статус»)
- Rows of the summary model carry the employee id in `ROLE_EMP_ID`; there is no hidden id column

### Save Confirmations
- Export save confirmations use `safe_message_box()` (QMessageBox)
- `Toast` is painted with QPainter on theme tokens (no white-on-transparent bug); used for short notes only

### FR-009: Training Period for Type B Programs (№6-29)
- All programs (1-4 and 6-29) use a fixed 3-year period (v3.6.0, UX-04 — the toggle checkbox was removed)
- `EmployeeSummaryTab._b_period_3years` is always `True`; legacy `b_period_3years` in `summary_programs.json` is ignored and no longer written
- Period logic still lives in `utils/training_rules.py` (the `b_period_3years=False` branch is kept but unused by the UI)

### FR-005: SetId Capture on XML Send
- SetId from `send_xml` response is saved to UI display field and journal
- Located in `data_transfer_tab.py:send_xml()`

### FR-006: API SNILS Query Format
- SNILS sent to server in `XXX-XXX-XXX XX` format (with dashes and space)
- `<ApiKey>` element required in all EducatedPersonFilter queries
- No XML namespace on EducatedPersonFilter
- Pagination: break when `len(records) < page_size`

### FR-007: API Date Normalization
- `_normalize_api_date()` in `employee_summary_tab.py` converts ISO dates (`2025-09-26T00:00:00`) to `DD.MM.YYYY`
- Applied in `_process_api_records()` and `_query_single()`

### FR-008: Error Response Saving
- Full server error responses saved to `log/error_response.txt` (UTF-8 BOM)
- Implemented in `mintrud_api.py:_save_error_response()`
- Filtered through `filter_sensitive_text()` before saving

## Key Files
- `tabs/employee_summary_tab.py` — main tab for registry sync, plan, stats
- `tabs/data_entry_tab.py` — XML/XLSX import tab
- `tabs/data_transfer_tab.py` — API send/query tab
- `utils/constants.py` — shared constants (VALID_PROGRAMS, PROGRAM_TITLES)
- `tabs/programs_dialog.py` — training programs editor dialog
- `utils/dialog_base.py` — `BaseDialog`; pass `scrollable=True` for tall dialogs (scroll body, screen-height cap)
- `utils/ui_helpers.py` — `HeaderStatePersistence` (column widths → `table_layouts.json`), `EmptyStateOverlay`, `busy_cursor`
- `api/mintrud_api.py` — MintrudClient class
- `api/backends/` — transport backends (Requests, WinINET)
- `utils/crypto.py` — Fernet + DPAPI encryption + production mode enforcement
- `utils/audit.py` — 35 security events with HMAC integrity (incl. FACTORY_RESET)
- `utils/logger.py` — SensitiveDataFilter (27+ patterns, recursive)
- `utils/xml_safe.py` — defusedxml wrapper with element/depth limits
- `utils/secure_temp.py` — isolated temp directory, secure deletion
- `utils/error_utils.py` — safe exception display (no PII)
- `utils/training_rules.py` — training period rules (program A vs B period, easily removable)
- `network/client.py` — network diagnostics (no USERNAME)
- `db/employee_programs_repo.py` — program data per employee
- `db/employees_repo.py` — employee CRUD

## Design system and UI frame (v3.9.0 «Норма»)
- **Tokens, not colours.** `utils/tahoe_style.py`: three themes `norma` (default) / `monokaiDark` / `monokaiLight`, token dicts → `get_colors(theme)` (`.tokens`, lowercase attributes like `c.surface`, `c.cta`, `c.err_text`; old upper-case names kept for legacy QSS). `get_global_stylesheet(theme)` builds the one QSS. Old theme keys (`light|dark|dracula|monokai`) migrate in `normalize_theme()`. NO hex colours in `tabs/` and `utils/` (guard test `tests/test_dialogs_redesign.py`); exceptions: status fills (`icons.py`, `toast.py`) and the always-dark log view/plates.
- **Fonts:** Rubik + Space Grotesk (OFL 1.1) in `resources/fonts/`, loaded by `load_app_fonts()` in `main.py`; QSS has fallbacks.
- **Buttons:** `btn.setProperty("role", "primary|dark|secondary|ghost|danger")` (use `ui_helpers.set_role`). Never add per-widget colour stylesheets; use objectName/property rules in the global QSS (`#card`, `#hintLabel`, `#notice[kind]`, `#chip[kind]`, `#darkPlate`).
- **Icons:** only from `utils/icons.py` (`nav_icon`, `themed_icon(name, token, size)`, `status_icon(kind)`); no emoji, no `QStyle.SP_*` (test `tests/test_icons.py`). Status icons: ok / warn / deleted / not_trained (red disc, no mark) / pending / unknown.
- **Frame:** `main.py` = `Sidebar` (`utils/sidebar.py`, 220 px, «today» block) + `QStackedWidget`; each page = `PageHeader` + the tab widget (`MainWindow._tab_widgets`, sidebar order; `Ctrl+1…7`). No menu bar / status bar; old menu items live in `utils/settings_dialog.py` («Настройки и темы»).
- **Dialogs:** subclass `BaseDialog` (header with title/subtitle, footer with `add_action_buttons()` / `add_footer_button()`); dark header plates via `ui_helpers.make_dark_plate()`; cards via `ui_helpers.make_card()`. Shared programs picker: `utils/programs_picker.py`.
- **Tables:** header click = ascending → descending → off (`utils/table_sort.py`: `install_model_sort`, `install_widget_sort`, `SmartSortProxyModel`; dates/numbers by value, empties last). «Сводка» uses `utils/frozen_table.py` (`FrozenColumnsTable`, `GroupedHeaderView`), model rows are data only (employee id in `ROLE_EMP_ID` of column 0). Column widths persist via `HeaderStatePersistence`.
- **XML output:** `utils/xml_output.py` (folder rule, `ДДММГГГГ-ЧЧ-ММ.xml`, «-2» on collision); the folder pref is stored in `ui_prefs.json`.
- Screens: `tabs/*.py`; the spec and mock-ups are in `INFO/` (local, not committed).

## Window Geometry Persistence
- `main.py` — saves/restores window size+position via `saveGeometry()` / `restoreGeometry()` (QByteArray → base64)
- File: `%APPDATA%\NormaOT\window_settings.json` (plain JSON)
- Save: `_save_window_geometry()` called in `closeEvent` (`main.py:356-359`)
- Restore: `_restore_window_geometry()` called in `__init__` after `resize()` (`main.py:48`)
- Fallbacks to default 1000×700 on first launch or on corrupt/missing file
- AppUserModelID set via `SetCurrentProcessExplicitAppUserModelID("excelxml.mintrud.3.1")` for correct Windows taskbar icon (`main.py:444`)

## Documentation
- `README.md` — main project overview (comprehensive: architecture, PDn protection, compliance, threat model)
- `docs/SECURITY.md` — cryptography spec, supported versions, vulnerability reporting, secure deployment
- `docs/HARDENING.md` — Windows hardening guide (BitLocker, antivirus, firewall, restricted users, audit)
- `docs/OPSEC_GUIDE.md` — operational security guide (Mermaid diagrams, key rotation, incident response)
- `docs/API_MINTTRUD.md` — Mintrud API reference
- `docs/Техническое_задание.md` — full TS with section 9 (ИБ, model угроз, требования к окружению/хранению/доступу)
- `reports/hardening_report.md` — v3.1.0 security audit report (18 vulnerabilities fixed)
- `reports/compliance_audit.md` — 152-ФЗ / ПП 1119 compliance audit (юридико-технический аудит)
- `reports/threat_model.md` — STRIDE threat model (8 components, 48 threat/mitigation pairs)
- `reports/data_flow.md` — 11 data flows, data matrix, storage table, deletion scheme
- `reports/risk_register.md` — 24 risks with probability/consequence scoring
- `reports/security_checklist.md` — 7 checklists (deploy, daily, weekly, monthly, incident, disposal, personnel)
- `reports/dpia.md` — Data Protection Impact Assessment (ОВЗД по 152-ФЗ)
- `CHANGELOG.md` — version history
