"""UX-10 step 5: several organizations in one installation."""
import json
import os

import pytest

from utils import org_profiles as orgs


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(orgs, "_root", lambda: str(tmp_path))
    import utils.audit
    monkeypatch.setattr(utils.audit, "log_audit", lambda *a, **k: None)
    orgs._reset_for_tests()
    yield tmp_path
    orgs._reset_for_tests()


def test_fresh_install_has_default_org_in_root(root):
    assert [o.id for o in orgs.list_orgs()] == [orgs.DEFAULT_ORG_ID]
    assert not orgs.has_multiple_orgs()
    assert orgs.get_org_data_dir() == str(root)  # existing installs: no migration


def test_add_org_gets_own_dir_and_encrypted_name(root):
    org = orgs.add_org("  ООО   Ромашка ")
    assert org.name == "ООО Ромашка"
    assert orgs.has_multiple_orgs()
    raw = (root / orgs.ORGS_FILE).read_text(encoding="utf-8")
    assert "Ромашка" not in raw
    orgs.set_active_org(org.id)
    assert orgs.get_org_data_dir() == os.path.join(str(root), "orgs", org.id)
    assert os.path.isdir(orgs.get_org_data_dir())
    assert orgs.get_active_org().name == "ООО Ромашка"


def test_active_org_remembered(root):
    org = orgs.add_org("ИП Петров")
    orgs.set_active_org(org.id)
    orgs._reset_for_tests()
    assert orgs.get_last_active_id() == org.id


@pytest.mark.parametrize("bad", ["", "   ", "x" * 201])
def test_invalid_names(root, bad):
    with pytest.raises(orgs.OrgError):
        orgs.add_org(bad)


def test_duplicate_name_rejected(root):
    orgs.add_org("ООО Ромашка")
    with pytest.raises(orgs.OrgError, match="уже есть"):
        orgs.add_org("ооо ромашка")


def test_rename(root):
    org = orgs.add_org("Старое")
    orgs.rename_org(org.id, "Новое")
    assert {o.name for o in orgs.list_orgs()} == {orgs.DEFAULT_ORG_NAME, "Новое"}
    orgs.rename_org(orgs.DEFAULT_ORG_ID, "ООО Первая")
    assert orgs.list_orgs()[0].name == "ООО Первая"


def test_unknown_or_bad_ids(root):
    with pytest.raises(orgs.OrgError):
        orgs.set_active_org("0123456789ab")
    with pytest.raises(orgs.OrgError):
        orgs.org_dir("../../etc")


def test_data_isolation(root):
    a = orgs.add_org("А")
    for oid, content in ((orgs.DEFAULT_ORG_ID, "root"), (a.id, "a")):
        orgs.set_active_org(oid)
        with open(os.path.join(orgs.get_org_data_dir(), "org_settings.json"), "w") as f:
            f.write(content)
    orgs.set_active_org(orgs.DEFAULT_ORG_ID)
    assert open(os.path.join(orgs.get_org_data_dir(), "org_settings.json")).read() == "root"


def test_cannot_delete_last_org(root):
    with pytest.raises(orgs.OrgError, match="единственную"):
        orgs.delete_org(orgs.DEFAULT_ORG_ID)


def test_delete_added_org_removes_its_dir_only(root):
    a = orgs.add_org("А")
    (root / "master.key").write_text("keep")
    d = orgs.org_dir(a.id)
    open(os.path.join(d, "app_data.db"), "w").close()
    orgs.delete_org(a.id)
    assert not os.path.exists(d)
    assert (root / "master.key").exists()
    assert [o.id for o in orgs.list_orgs()] == [orgs.DEFAULT_ORG_ID]


def test_delete_default_org_keeps_global_files(root):
    a = orgs.add_org("А")
    for fn in ("app_data.db", "api_key.json", "org_settings.json", "master.key", "license.json", "theme.json"):
        (root / fn).write_text("x")
    (root / "backups").mkdir()
    (root / "log").mkdir()
    orgs.set_active_org(orgs.DEFAULT_ORG_ID)
    orgs.delete_org(orgs.DEFAULT_ORG_ID)
    for fn in ("app_data.db", "api_key.json", "org_settings.json"):
        assert not (root / fn).exists()
    assert not (root / "backups").exists()
    for fn in ("master.key", "license.json", "theme.json"):
        assert (root / fn).exists()
    assert (root / "log").exists()
    assert [o.id for o in orgs.list_orgs()] == [a.id]
    assert orgs.get_last_active_id() == a.id
    data = json.loads((root / orgs.ORGS_FILE).read_text(encoding="utf-8"))
    assert data["default_deleted"] is True


def test_corrupt_registry_falls_back_to_default(root):
    (root / orgs.ORGS_FILE).write_text("{broken", encoding="utf-8")
    assert [o.id for o in orgs.list_orgs()] == [orgs.DEFAULT_ORG_ID]
