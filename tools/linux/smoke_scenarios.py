#!/usr/bin/env python3
"""End-to-end smoke scenarios for the Linux port (L-07). Headless, runs from a source checkout.

    QT_QPA_PLATFORM=offscreen python tools/linux/smoke_scenarios.py [--keyring]

Everything happens in a temporary XDG tree; the real data dir is never touched. By default the master key
uses the passphrase-file store; --keyring switches to the REAL Secret Service of the current session
(the test key is removed from it at the end). Prints PASS / FAIL / SKIP per scenario; exit code 1 on FAIL.
GUI-only items are in docs/LINUX_TEST_CHECKLIST.md.
"""
import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import traceback

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

ap = argparse.ArgumentParser()
ap.add_argument("--keyring", action="store_true", help="use the real Secret Service instead of the passphrase file")
ARGS = ap.parse_args()

TMP = tempfile.mkdtemp(prefix="normaot_smoke_")
for var, sub in (("XDG_DATA_HOME", "data"), ("XDG_CONFIG_HOME", "config"), ("XDG_RUNTIME_DIR", "run")):
    os.makedirs(os.path.join(TMP, sub), mode=0o700, exist_ok=True)
    os.environ[var] = os.path.join(TMP, sub)
os.environ["APPDATA"] = os.path.join(TMP, "appdata")  # harmless off Windows, keeps Windows runs isolated too
os.environ.pop("EXCEL_XML_PROD", None)
if not ARGS.keyring:
    os.environ["NORMAOT_KEYSTORE"] = "passphrase_file"
else:
    os.environ.pop("NORMAOT_KEYSTORE", None)

from utils import keystore, platform_info  # noqa: E402
from utils import crypto  # noqa: E402
from utils.app_paths import get_app_data_dir, get_app_log_dir  # noqa: E402

PASSPHRASE = "smoke-test-phrase-1"
RESULTS = []


def scenario(name):
    def deco(fn):
        def run():
            try:
                outcome = fn()
                RESULTS.append((name, "SKIP" if outcome and outcome.startswith("skip") else "PASS", outcome or ""))
            except Exception as e:  # noqa: BLE001 - report everything
                RESULTS.append((name, "FAIL", "%s: %s" % (type(e).__name__, e)))
                traceback.print_exc()
        run.scenario_name = name
        SCENARIOS.append(run)
        return fn
    return deco


SCENARIOS = []
STATE = {}


def reload_process():
    """Simulate a new start: forget the key and the unlock passphrase held in memory."""
    crypto._MASTER_KEY = None
    crypto._FERNET_INSTANCE = None
    crypto.clear_caches()
    keystore.set_unlock_passphrase(None)


@scenario("S01 first start: key is created and stored protected")
def s01():
    data = get_app_data_dir()
    if crypto.keystore_needs_passphrase():
        crypto.unlock_keystore(PASSPHRASE)
    key = crypto._get_or_create_master_key()
    STATE["key"] = key
    blob = open(os.path.join(data, "master.key"), "rb").read()
    assert blob.startswith(b"NOTK1\n"), "master.key is not a NOTK1 marker"
    assert key not in blob, "raw key found in master.key"
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(data).st_mode) == 0o700, "data dir is not 0700"
        assert stat.S_IMODE(os.stat(os.path.join(data, "master.key")).st_mode) == 0o600, "master.key is not 0600"
    store = keystore.marker_store_name(blob)
    return "store=%s" % store


@scenario("S02 restart: same key; wrong passphrase rejected; key file unchanged")
def s02():
    data = get_app_data_dir()
    before = open(os.path.join(data, "master.key"), "rb").read()
    reload_process()
    store = keystore.marker_store_name(before)
    if store == keystore.STORE_PASSPHRASE_FILE:
        try:
            crypto.unlock_keystore("definitely wrong")
        except crypto.CryptoPassphraseRequiredError:
            pass
        else:
            raise AssertionError("wrong passphrase accepted")
        crypto.unlock_keystore(PASSPHRASE)
    assert crypto._get_or_create_master_key() == STATE["key"], "key changed after restart"
    assert open(os.path.join(data, "master.key"), "rb").read() == before, "master.key was rewritten"
    assert not os.path.exists(os.path.join(data, "corrupted_keys")), "key was archived as corrupted"


@scenario("S03 field encryption round trip and metadata integrity")
def s03():
    token = crypto.encrypt_value("Иванов Иван Иванович")
    assert "Иванов" not in token
    assert crypto.decrypt_value(token) == "Иванов Иван Иванович"
    assert crypto.verify_metadata_integrity() is True


@scenario("S04 database + schema + encrypted backup")
def s04():
    from db.database import DatabaseManager
    from db.schema import create_schema
    path = os.path.join(get_app_data_dir(), "app_data.db")
    db = DatabaseManager.get_instance(path)
    db.initialize()
    create_schema()
    db.execute("INSERT INTO employees (snils_enc, snils_hash) VALUES (?, ?)", ("x", "y"))
    backup = db.create_backup()
    assert backup and os.path.exists(backup), "backup not created"
    import zipfile
    with zipfile.ZipFile(backup) as zf:
        name = zf.namelist()[0]
        try:
            zf.read(name)  # no password -> must fail for an encrypted archive
        except RuntimeError:
            pass
        else:
            raise AssertionError("backup is readable without a password")


@scenario("S05 XLSX import")
def s05():
    from importers.xlsx_importer import COLUMNS, load_xlsx
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(COLUMNS)
    ws.append(["Иванов", "Иван", "Иванович", "12345678964", "Инженер", "7701123456", "ООО Тест", "7701123456",
               "УЦ Тест", "Удовлетворительно", "1", "02.01.2026", "П-1"])
    ws.append(["Петрова", "Анна", "Сергеевна", "11223344595", "Мастер", "7701123456", "ООО Тест", "7701123456",
               "УЦ Тест", "Неудовлетворительно", "2", "02.01.2026", "П-2"])
    path = os.path.join(TMP, "import.xlsx")
    wb.save(path)
    records, details, bad_rows, msg = load_xlsx(path)
    assert records and len(records) == 2, "unexpected import result: records=%s errors=%s msg=%s" % (
        records and len(records), details[:2], msg)
    STATE["records"] = records
    return "%d records, %d error rows" % (len(records), len(bad_rows))


@scenario("S06 XML export validates against the XSD and re-imports")
def s06():
    from exporters.xml_exporter import export_to_xml
    from lxml import etree
    from importers.xml_importer import load_xml
    out = os.path.join(TMP, "export.xml")
    xsd_path = os.path.join(ROOT, "schema", "educated_person_import_v1.0.9.xsd")
    export_to_xml(STATE["records"], out)
    parser = etree.XMLParser(resolve_entities=False, no_network=True, dtd_validation=False, huge_tree=False)
    schema = etree.XMLSchema(etree.parse(xsd_path, parser))
    doc = etree.parse(out, parser)
    assert schema.validate(doc), str(schema.error_log)[:300]
    records, errors, messages, xsd_errors = load_xml(out, xsd_path)
    assert records and not xsd_errors, "re-import failed: %s" % (xsd_errors or messages)


@scenario("S07 DOCX protocol is generated; fonts for Times New Roman")
def s07():
    from exporters.protocol_exporter import ProtocolExporter
    from protocol.programs_manager import ProgramsManager
    out = os.path.join(TMP, "protocol.docx")
    pm = ProgramsManager(os.path.join(TMP, "pm"))
    commission = {"org_name": "ООО Тест", "order_number": "1", "order_date": "01.01.2026",
                  "exam_date": "02.01.2026", "chairman_fio": "Петров П.П.", "chairman_position": "Директор",
                  "member1_fio": "Сидоров С.С.", "member2_fio": "Кузнецов К.К.", "member3_fio": "", "union_fio": ""}
    workers = [{"last_name": "Иванов", "first_name": "Иван", "middle_name": "Иванович", "snils": "123-456-789 64",
                "position": "Инженер", "result": "Удовлетворительно", "program": "1", "date": "02.01.2026",
                "protocol": "П-1"}]
    ok, msg = ProtocolExporter.generate_from_commission(
        commission, "1", workers, pm, out,
        os.path.join(ROOT, "templates", "Protokol_proverki_znanii_OT.docx"), TMP)
    assert ok and os.path.getsize(out) > 5000, msg
    note = []
    if shutil.which("fc-match"):
        fam = subprocess.run(["fc-match", "Times New Roman"], capture_output=True, text=True).stdout.strip()
        note.append("fc-match: " + fam)
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        r = subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", TMP, out],
                           capture_output=True, text=True, timeout=180)
        note.append("pdf: " + ("ok" if os.path.exists(os.path.join(TMP, "protocol.pdf")) else "FAILED " + r.stderr[:100]))
    else:
        note.append("LibreOffice not installed: layout not checked")
    return "; ".join(note)


@scenario("S08 master key backup -> restore")
def s08():
    ok, zip_path = crypto.create_master_key_backup(os.path.join(TMP, "kb"))
    assert ok, zip_path
    data = get_app_data_dir()
    path = os.path.join(data, "master.key")
    original = open(path, "rb").read()
    # The backup password is derived from the LOADED master key, so restore only works while that key is
    # in memory (limitation on every OS, see docs/LINUX_TEST_CHECKLIST.md): damage the file, then restore.
    with open(path, "wb") as f:
        f.write(b"damaged")
    ok, msg = crypto.restore_master_key_backup(zip_path)
    assert ok, msg
    assert open(path, "rb").read() == original, "restored master.key differs"
    reload_process()
    if keystore.marker_store_name(original) == keystore.STORE_PASSPHRASE_FILE:
        crypto.unlock_keystore(PASSPHRASE)
    assert crypto._get_or_create_master_key() == STATE["key"], "restored key differs"


@scenario("S09 organizations")
def s09():
    from utils import org_profiles as orgs
    orgs._reset_for_tests()
    org = orgs.add_org("ООО Смоук")
    assert org.id in [o.id for o in orgs.list_orgs()]
    assert os.path.isdir(orgs.org_dir(org.id))
    orgs.delete_org(org.id)
    assert org.id not in [o.id for o in orgs.list_orgs()]


@scenario("S10 proxy from environment and backend order")
def s10():
    from utils import proxy_manager
    from api import mintrud_api
    for var in ("http_proxy", "https_proxy", "no_proxy", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
        os.environ.pop(var, None)
    assert proxy_manager.detect_system_proxy() is None
    os.environ["https_proxy"] = "proxy.local:3128"
    try:
        assert proxy_manager.detect_system_proxy() == "http://proxy.local:3128"
    finally:
        os.environ.pop("https_proxy", None)
    assert mintrud_api._backend_order()[0] == ("requests" if platform_info.IS_LINUX else "wininet")
    assert mintrud_api.MintrudClient()._backend.name == ("requests" if platform_info.IS_LINUX else "wininet")


@scenario("S11 TLS context verifies certificates")
def s11():
    import ssl
    from utils.tls_context import build_ssl_context
    ctx = build_ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    return type(ctx).__module__


@scenario("S12 audit log hash chain verifies")
def s12():
    from utils.audit import setup_audit_log, log_audit, verify_audit_log
    setup_audit_log(get_app_log_dir())
    log_audit("STARTUP", "smoke")
    log_audit("SHUTDOWN", "smoke")
    path = os.path.join(get_app_log_dir(), "audit.log")
    assert os.path.exists(path)
    bad = verify_audit_log(path)
    assert not bad, "violations: %s" % bad[:2]


@scenario("S13 factory reset removes the key from the OS key store and the data dir")
def s13():
    from db.database import DatabaseManager
    DatabaseManager.close_all()
    data = get_app_data_dir()
    blob = open(os.path.join(data, "master.key"), "rb").read()
    store = keystore.marker_store_name(blob)
    assert crypto.forget_master_key() is True
    if store == keystore.STORE_SECRET_SERVICE:
        import keyring
        fp = keystore._unpack(blob)["fp"]
        assert keyring.get_password(keystore.SERVICE_NAME, fp) is None, "key still in Secret Service"
    for entry in os.listdir(data):
        p = os.path.join(data, entry)
        shutil.rmtree(p) if os.path.isdir(p) else os.unlink(p)
    assert os.listdir(data) == []
    return "store=%s" % store


def main():
    if sys.platform == "win32":
        print("SKIP all: Linux-only scenarios (NOTK1 key markers, XDG paths)")
        return 0
    print("Platform: %s | keystore mode: %s | tmp: %s" % (
        sys.platform, "real keyring" if ARGS.keyring else "passphrase file", TMP))
    if ARGS.keyring and not keystore.SecretServiceKeyStore().is_available():
        print("SKIP all: no usable Secret Service backend in this session")
        return 0
    for run in SCENARIOS:
        run()
    width = max(len(n) for n, _, _ in RESULTS)
    for name, status, note in RESULTS:
        print("%-5s %-*s  %s" % (status, width, name, note))
    failed = [r for r in RESULTS if r[1] == "FAIL"]
    print("\n%d passed, %d failed, %d skipped" % (
        sum(r[1] == "PASS" for r in RESULTS), len(failed), sum(r[1] == "SKIP" for r in RESULTS)))
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
