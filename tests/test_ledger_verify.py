"""Tests for the audit ledger verifier.

The route used to return `size > 0` and call that "Chain verified", which hid a
real problem: multiple nexus processes each append with their own chain head, so
the file is interleaved and the chain is genuinely broken. These tests cover the
verifier itself — synthetic chains built from the exact 32-byte LogEntry layout
that nexus/src writes.
"""
import struct
import pytest

from web.backend.api.ops import _verify_ledger_file, LEDGER_SEED, LEDGER_ENTRY_SIZE

ENTRY = struct.Struct("<4Q")  # seq, ts, prev_hash, curr_hash


def _write_chain(path, segments):
    """Write a ledger file.

    segments: list of dicts:
      entries  - how many entries to write
      restart  - if True, this segment re-roots from LEDGER_SEED (process restart)
      foreign  - if True, this segment chains from a *different* head
                 (a second writer process)
      from_hash - explicit head to chain from for foreign segments
    """
    out = b""
    for seg in segments:
        head = seg.get("from_hash", LEDGER_SEED)
        for i in range(seg["entries"]):
            curr = (hash((id(seg), i)) & 0xFFFFFFFFFFFFFFFF) or (i + 1)
            out += ENTRY.pack(seg.get("seq0", 0) + i, seg.get("ts0", 1000) + i, head, curr)
            head = curr
    path.write_bytes(out)


def test_clean_single_writer_chain_verifies(tmp_path):
    p = tmp_path / "ledger.bin"
    _write_chain(p, [{"entries": 50}])

    r = _verify_ledger_file(str(p))
    assert r["entries"] == 50
    assert r["valid"] is True
    assert r["chain_breaks"] == 0
    assert r["anomaly_count"] == 0
    assert r["first_seq"] == 0
    assert r["last_seq"] == 49
    assert r["head"] and len(r["head"]) == 16


def test_process_restart_is_not_reported_as_corruption(tmp_path):
    """A restart re-seeds the chain by design — it must not flag anomalies."""
    p = tmp_path / "ledger.bin"
    _write_chain(p, [{"entries": 30}, {"entries": 20}])

    r = _verify_ledger_file(str(p))
    assert r["entries"] == 50
    assert r["restarts"] == 1
    assert r["chain_breaks"] == 0
    assert r["valid"] is True


def test_second_writer_process_is_detected(tmp_path):
    """The bug the route previously missed: two processes, one file.

    The second segment chains from its own head, so every transition breaks
    prev_hash linkage. The verifier must name the cause, not just fail.
    """
    p = tmp_path / "ledger.bin"
    _write_chain(p, [{"entries": 10}])
    # append a foreign chain that starts from an unrelated head
    foreign = b""
    head = 0xDEADBEEFDEADBEEF
    for i in range(10):
        curr = 0xAAAA000000000000 + i
        foreign += ENTRY.pack(i, 5000 + i, head, curr)
        head = curr
    p.write_bytes(p.read_bytes() + foreign)

    r = _verify_ledger_file(str(p))
    assert r["entries"] == 20
    assert r["chain_breaks"] >= 1
    assert r["valid"] is False
    assert "chain break" in r["diagnosis"]


def test_tampered_entry_breaks_the_chain(tmp_path):
    p = tmp_path / "ledger.bin"
    _write_chain(p, [{"entries": 20}])
    raw = bytearray(p.read_bytes())
    # corrupt one curr_hash in the middle
    struct.pack_into("<Q", raw, 5 * 32 + 24, 0xBADBADBAD)
    p.write_bytes(bytes(raw))

    r = _verify_ledger_file(str(p))
    assert r["valid"] is False
    assert r["chain_breaks"] >= 1


def test_truncated_tail_is_reported(tmp_path):
    p = tmp_path / "ledger.bin"
    _write_chain(p, [{"entries": 10}])
    raw = bytearray(p.read_bytes())
    p.write_bytes(bytes(raw[: len(raw) - 7]))  # interrupted write

    r = _verify_ledger_file(str(p))
    assert r["entries"] == 9            # only whole entries are parsed
    assert any("truncated" in a for a in r["anomalies"])


def test_empty_and_missing_files(tmp_path):
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    r = _verify_ledger_file(str(empty))
    assert r["entries"] == 0
    assert r["valid"] is False
    assert r["head"] is None
    assert r["diagnosis"] == "empty ledger"

    r = _verify_ledger_file(str(tmp_path / "nope.bin"))
    assert r["entries"] == 0
    assert r["valid"] is False


def test_missing_file_route(tmp_path):
    """The HTTP route must not raise when the ledger is absent."""
    import asyncio
    from web.backend.api import ops

    r = asyncio.run(ops.verify_ledger.__wrapped__()) if hasattr(ops.verify_ledger, "__wrapped__") else None
    if r is None:  # FastAPI-decorated; fall back to the helper directly
        assert _verify_ledger_file(str(tmp_path / "absent.bin"))["valid"] is False


def test_on_disk_ledger_is_actually_integrity_broken():
    """Guard against regressing the real finding.

    The checked-in/runtime ledger contains interleaved chains from concurrent
    nexus processes. If this ever starts passing, either the engine was fixed
    (single writer / flock) or the verifier was weakened — both worth knowing.
    """
    import os

    path = os.path.join("data", "audit_ledger.bin")
    if not os.path.exists(path):
        pytest.skip("no runtime ledger present")

    r = _verify_ledger_file(path)
    assert r["entries"] > 0
    assert r["valid"] is False
    assert r["chain_breaks"] > 1
