"""Tests for utils.crypto._zero_memory (L-00)."""
import pytest

from utils.crypto import _zero_memory, _zero_memory_bytes


@pytest.mark.parametrize("size", [1, 32, 44, 1000])
def test_zero_memory_wipes_all_bytes(size):
    data = bytearray(b"\xAB" * size)
    _zero_memory(data)
    assert len(data) == size
    assert data == bytearray(size)


def test_zero_memory_empty_and_none():
    _zero_memory(bytearray())
    _zero_memory(None)
    _zero_memory_bytes(None)
    _zero_memory_bytes(b"")


def test_zero_memory_object_stays_usable():
    data = bytearray(b"secret-key-material")
    _zero_memory(data)
    data.append(1)
    data.extend(b"xyz")
    assert len(data) == len(b"secret-key-material") + 4


def test_zero_memory_does_not_corrupt_neighbours():
    guard_before = bytearray(b"\x55" * 64)
    data = bytearray(b"\xAB" * 44)
    guard_after = bytearray(b"\x55" * 64)
    _zero_memory(data)
    assert guard_before == bytearray(b"\x55" * 64)
    assert guard_after == bytearray(b"\x55" * 64)


def test_zero_memory_bytes_does_not_raise():
    _zero_memory_bytes(b"\x01" * 32)


def test_rotate_master_key_really_zeros_old_encoded(monkeypatch):
    from utils import crypto

    seen = []
    real_zero = crypto._zero_memory

    def spy(data):
        snapshot_len = len(data) if data is not None else 0
        real_zero(data)
        seen.append((snapshot_len, data is not None and bytes(data) == bytes(snapshot_len)))

    monkeypatch.setattr("utils.crypto._zero_memory", spy)
    monkeypatch.setattr("utils.crypto._get_or_create_master_key", lambda: b"\x02" * 32)
    monkeypatch.setattr("utils.crypto.os.urandom", lambda n: b"\x01" * n)
    monkeypatch.setattr("utils.crypto._write_key_file", lambda kf, kb: None)
    monkeypatch.setattr("utils.crypto._save_key_metadata", lambda m: None)
    monkeypatch.setattr("utils.crypto._load_key_metadata", lambda: {})
    monkeypatch.setattr("utils.crypto._is_production_mode", lambda: False)

    ok, _ = crypto.rotate_master_key()
    assert ok
    assert (44, True) in seen
    assert all(wiped for _, wiped in seen)
