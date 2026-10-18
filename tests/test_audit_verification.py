"""
Tests for audit log HMAC verification and integrity checking.
"""
import os
import re
import json
import hmac
import hashlib
import tempfile
import logging
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock


def _cleanup_audit_logger():
    audit_logger = logging.getLogger("audit")
    for h in audit_logger.handlers[:]:
        h.close()
        audit_logger.removeHandler(h)


class TestAuditVerification:
    """Tests for verify_audit_log functionality."""

    def _cleanup_and_setup(self, tmpdir):
        _cleanup_audit_logger()
        from utils.audit import setup_audit_log, _PREV_HASH, _AUDIT_HMAC_KEY
        import utils.audit as audit_mod
        audit_mod._PREV_HASH = "0" * 64
        log_path = setup_audit_log(tmpdir)
        return log_path

    def test_written_timestamp_matches_hmac_timestamp(self):
        """Regression: the line must carry the HMAC timestamp, not the later record time
        (crossing a second boundary used to flag genuine entries as tampered)."""
        import utils.audit as audit_mod
        from utils.audit import log_audit, verify_audit_log

        class _PastDatetime:
            @staticmethod
            def now():
                return datetime(2020, 1, 1, 0, 0, 0)

        tmpdir = tempfile.mkdtemp()
        try:
            log_path = self._cleanup_and_setup(tmpdir)
            with patch.object(audit_mod, "datetime", _PastDatetime):
                log_audit("STARTUP", "ts test")
                log_audit("SHUTDOWN", "ts test")
            _cleanup_audit_logger()
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
            assert lines and all(l.startswith("2020-01-01 00:00:00 | ") for l in lines)
            assert verify_audit_log(log_path) == []
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def _restart(self, tmpdir):
        """Simulate an application restart: new process state, same log dir."""
        import utils.audit as audit_mod
        _cleanup_audit_logger()
        audit_mod._PREV_HASH = "0" * 64
        return audit_mod.setup_audit_log(tmpdir)

    def test_chain_continues_across_restart(self):
        """Regression: every launch restarted the chain from zeros, so the first entry
        of each session was reported as tampered."""
        from utils.audit import log_audit, verify_audit_log
        tmpdir = tempfile.mkdtemp()
        try:
            log_path = self._cleanup_and_setup(tmpdir)
            log_audit("STARTUP", "session 1"); log_audit("SHUTDOWN", "session 1")
            self._restart(tmpdir)
            log_audit("STARTUP", "session 2"); log_audit("SHUTDOWN", "session 2")
            _cleanup_audit_logger()
            assert verify_audit_log(log_path) == []
        finally:
            _cleanup_audit_logger()
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_deleted_entry_still_detected_after_restart(self):
        from utils.audit import log_audit, verify_audit_log
        tmpdir = tempfile.mkdtemp()
        try:
            log_path = self._cleanup_and_setup(tmpdir)
            log_audit("STARTUP", "a"); log_audit("EXPORT_XML", "b")
            self._restart(tmpdir)
            log_audit("STARTUP", "c")
            _cleanup_audit_logger()
            with open(log_path, encoding='utf-8') as f:
                lines = f.readlines()
            with open(log_path, 'w', encoding='utf-8') as f:
                f.writelines([lines[0], lines[2]])  # drop the middle entry
            assert len(verify_audit_log(log_path)) == 1
        finally:
            _cleanup_audit_logger()
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_legacy_restarted_chain_is_accepted(self):
        """Logs written before the fix restart from zeros at each launch: not a violation."""
        import utils.audit as audit_mod
        from utils.audit import log_audit, verify_audit_log
        tmpdir = tempfile.mkdtemp()
        try:
            log_path = self._cleanup_and_setup(tmpdir)
            log_audit("STARTUP", "old 1")
            audit_mod._PREV_HASH = "0" * 64  # old behaviour on restart
            log_audit("STARTUP", "old 2")
            _cleanup_audit_logger()
            assert verify_audit_log(log_path) == []
        finally:
            _cleanup_audit_logger()
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_rotated_file_chains_from_predecessor(self):
        import os as _os
        from utils.audit import log_audit, verify_audit_log
        tmpdir = tempfile.mkdtemp()
        try:
            log_path = self._cleanup_and_setup(tmpdir)
            log_audit("STARTUP", "before rotation")
            _cleanup_audit_logger()
            _os.replace(log_path, log_path + ".1")       # what RotatingFileHandler does
            self._restart(tmpdir)                         # chain seeded from audit.log.1
            log_audit("STARTUP", "after rotation")
            _cleanup_audit_logger()
            assert verify_audit_log(log_path) == []
        finally:
            _cleanup_audit_logger()
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_signed_tag_not_rewritten_by_sensitive_filter(self):
        """Regression: a hex tag with a phone-like digit run was masked by the handler
        filter (e.g. '…+7***…'), making genuine entries fail verification."""
        import utils.audit as audit_mod
        from utils.audit import log_audit

        phone_like_tag = ("89161234567" + "a" * 53)
        assert len(phone_like_tag) == 64
        tmpdir = tempfile.mkdtemp()
        try:
            log_path = self._cleanup_and_setup(tmpdir)
            with patch.object(audit_mod, "_compute_audit_hmac", lambda msg: phone_like_tag):
                log_audit("STARTUP", "filter test")
            _cleanup_audit_logger()
            with open(log_path, 'r', encoding='utf-8') as f:
                line = f.readline()
            assert "[%s]" % phone_like_tag in line
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_verify_clean_audit_log(self):
        """Verify that an unmodified audit log passes integrity check."""
        from utils.audit import log_audit, verify_audit_log

        tmpdir = tempfile.mkdtemp()
        try:
            log_path = self._cleanup_and_setup(tmpdir)
            log_audit("STARTUP", "Test startup")
            log_audit("SHUTDOWN", "Test shutdown")
            _cleanup_audit_logger()

            violations = verify_audit_log(log_path)
            assert violations == [], f"Expected no violations, got: {violations}"
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_verify_tampered_audit_log(self):
        """Verify that a modified audit log is detected."""
        from utils.audit import log_audit, verify_audit_log

        tmpdir = tempfile.mkdtemp()
        try:
            log_path = self._cleanup_and_setup(tmpdir)
            log_audit("STARTUP", "Before tamper")
            _cleanup_audit_logger()

            fake_tag = "f" * 64
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"2025-01-01 12:00:00 | [{fake_tag}] TAMPERED | malicious data\n")

            violations = verify_audit_log(log_path)
            assert len(violations) > 0, f"Expected violations for tampered log, got {len(violations)}"
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_hmac_tag_length_64(self):
        """Verify new audit entries use 64-char HMAC tags."""
        from utils.audit import log_audit

        tmpdir = tempfile.mkdtemp()
        try:
            log_path = self._cleanup_and_setup(tmpdir)
            log_audit("STARTUP", "Tag length test")
            _cleanup_audit_logger()

            with open(log_path, 'r', encoding='utf-8') as f:
                line = f.readline()
            match = re.search(r'\[([a-f0-9]+)\]', line)
            assert match, f"No HMAC tag found in: {line}"
            tag = match.group(1)
            assert len(tag) == 64, f"Expected 64-char tag, got {len(tag)}: {tag}"
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    @patch('utils.crypto.get_key_fingerprint')
    def test_no_hmac_key_no_tag(self, mock_fingerprint):
        """Without master key, entries should have [no-hmac] tag."""
        mock_fingerprint.side_effect = Exception("No key")
        from utils.audit import log_audit

        import utils.audit as audit_mod
        audit_mod._AUDIT_HMAC_KEY = None

        tmpdir = tempfile.mkdtemp()
        try:
            log_path = self._cleanup_and_setup(tmpdir)
            log_audit("STARTUP", "No key test")
            _cleanup_audit_logger()

            with open(log_path, 'r', encoding='utf-8') as f:
                line = f.readline()
            assert '[no-hmac]' in line, f"Expected [no-hmac] tag in: {line}"
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_hash_chaining(self):
        """Verify that hash chaining detects reordering of entries."""
        from utils.audit import log_audit, verify_audit_log

        tmpdir = tempfile.mkdtemp()
        try:
            log_path = self._cleanup_and_setup(tmpdir)
            log_audit("STARTUP", "First entry")
            log_audit("LOGIN", "Second entry")
            _cleanup_audit_logger()

            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(lines[1])
                f.write(lines[0])

            violations = verify_audit_log(log_path)
            assert len(violations) > 0, f"Expected violations for reordered entries, got {len(violations)}"
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
