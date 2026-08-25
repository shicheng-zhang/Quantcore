from web.backend.runtime import read_json, write_json_atomic


def test_atomic_json_round_trip(tmp_path):
    target = tmp_path / "nested" / "state.json"
    write_json_atomic(target, {"status": "READY", "count": 1})
    assert read_json(target, {}) == {"status": "READY", "count": 1}


def test_invalid_json_returns_default(tmp_path):
    target = tmp_path / "broken.json"
    target.write_text("{")
    assert read_json(target, {"status": "DEGRADED"}) == {"status": "DEGRADED"}
