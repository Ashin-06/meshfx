"""The analysis API: settings, auth, limits, headers, metrics, health, the log and migrations."""
import hashlib
import importlib
import json
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_apps import _android_db
from test_flash import build_esp32_image

from meshfx import cli, db, flash, ops

KEY = "meshfx_" + "x" * 40
HASHED = {f"sha256:{hashlib.sha256(KEY.encode()).hexdigest()}": {"user": "examiner-1", "role": "examiner"}}
IMAGE = build_esp32_image()


def boot(monkeypatch, **env):
    for k in [k for k in os.environ if k.startswith("MESHFX_")]:
        monkeypatch.delenv(k)
    for k, v in env.items():
        monkeypatch.setenv(f"MESHFX_{k}", v)
    import meshfx.api as api

    return importlib.reload(api)


@pytest.mark.parametrize("change, message", [
    ({"MESHFX_API_KEYS": None}, "API keys"),
    ({"MESHFX_DATABASE_URL": None}, "DATABASE_URL"),
    ({"MESHFX_API_KEYS": json.dumps({KEY: {"user": "x", "role": "examiner"}})}, "sha256"),
    ({"MESHFX_API_KEYS": json.dumps({"sha256:" + "0" * 64: {"user": "x", "role": "root"}})}, "roles"),
    ({"MESHFX_CORS_ORIGINS": "*"}, "CORS"),
])
def test_production_settings_refused(change, message):
    env = {"MESHFX_ENV": "production", "MESHFX_API_KEYS": json.dumps(HASHED), "MESHFX_DATABASE_URL": "sqlite://"}
    assert ops.load_settings(env).production
    env.update(change)
    with pytest.raises(ops.ConfigError, match=message):
        ops.load_settings({k: v for k, v in env.items() if v is not None})


def test_no_public_bind_and_readable_exit():
    with pytest.raises(ops.ConfigError, match="without API keys"):
        ops.load_settings({"MESHFX_HOST": "0.0.0.0"})
    env = {k: v for k, v in os.environ.items() if not k.startswith("MESHFX_")}
    r = subprocess.run([sys.executable, "-m", "meshfx", "serve", "--host", "0.0.0.0"], env=env,
                       capture_output=True, text=True, timeout=120, check=False)
    assert r.returncode != 0 and "without API keys" in r.stderr


def test_analyses_are_logged_across_a_restart(monkeypatch, tmp_path):
    url = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'a.db'}"
    c = TestClient(boot(monkeypatch, DATABASE_URL=url).app)
    r = c.post("/v1/flash", content=IMAGE, params={"label": "radio 1"})
    f = r.json()
    assert r.status_code == 200 and f["input_sha256"] == hashlib.sha256(IMAGE).hexdigest()
    assert [p["label"] for p in f["partitions"]] == ["nvs", "app0", "spiffs"]
    assert {x["path"] for x in f["files"]} == {"/prefs/config.proto", "/Messages_default.msgs"}
    assert all(len(x["sha256"]) == 64 for x in f["files"])
    html = c.post("/v1/flash", content=IMAGE, params={"format": "html"})
    assert html.headers["content-type"].startswith("text/html")

    _android_db(str(tmp_path / "app.db"))
    a = c.post("/v1/app", content=(tmp_path / "app.db").read_bytes(), params={"label": "phone 1"}).json()
    assert {row["kind"] for row in a["rows"]} >= {"message", "node"}

    c = TestClient(boot(monkeypatch, DATABASE_URL=url).app)  # restart
    got = c.get(f"/v1/analyses/{f['analysis_id']}").json()
    assert got["kind"] == "flash" and got["label"] == "radio 1" and got["summary"]["files"] == 2
    assert got["inputs"] == {"flash": hashlib.sha256(IMAGE).hexdigest()}
    assert [x["kind"] for x in c.get("/v1/analyses").json()["analyses"]] == ["app", "flash", "flash"]
    assert c.get("/v1/analyses/nope").status_code == 404


def test_carving_and_bad_inputs(monkeypatch):
    from test_msgstore import rec

    c = TestClient(boot(monkeypatch).app)
    raw = b"\xff" * 5000 + rec("meet at the ridge") + b"\xff" * 3000
    found = c.post("/v1/carve", content=raw).json()["records"]
    assert any("ridge" in (r.get("text") or "") for r in found)
    assert c.post("/v1/flash", content=b"").status_code == 422
    assert c.post("/v1/flash", content=b"\xff" * 100_000).status_code == 422  # erased flash, no table
    assert c.post("/v1/app", content=b"not sqlite").status_code == 422
    assert c.post("/v1/app", content=b"SQLite format 3\x00" + b"\0" * 200).status_code == 422


def test_extract_refuses_paths_outside_the_output(monkeypatch, tmp_path):
    img = tmp_path / "flash.bin"
    img.write_bytes(IMAGE)
    monkeypatch.setattr(flash, "extract_files", lambda data: {"/prefs/ok.proto": b"ok", "/../../evil.txt": b"x"})
    out = tmp_path / "out"
    with pytest.raises(SystemExit, match="outside"):
        cli.main(["extract", str(img), "-o", str(out)])
    assert not (tmp_path / "evil.txt").exists() and not (tmp_path.parent / "evil.txt").exists()


def test_roles_and_metrics(monkeypatch):
    keys = {"k-ex": {"user": "asha", "role": "examiner"}, "k-view": {"user": "vic", "role": "viewer"},
            "k-mon": {"user": "prom", "role": "monitor"}}
    c = TestClient(boot(monkeypatch, API_KEYS=json.dumps(keys)).app)
    assert c.post("/v1/flash", content=IMAGE).status_code == 401
    assert c.post("/v1/flash", content=IMAGE, headers={"x-api-key": "wrong"}).status_code == 401
    assert c.post("/v1/flash", content=IMAGE, headers={"x-api-key": "k-view"}).status_code == 403
    assert c.post("/v1/flash", content=IMAGE, headers={"x-api-key": "k-ex"}).status_code == 200
    log = c.get("/v1/analyses", headers={"authorization": "Bearer k-view"}).json()["analyses"]
    assert log[0]["requested_by"] == "asha"
    assert c.get("/metrics", headers={"x-api-key": "k-ex"}).status_code == 403
    m = c.get("/metrics", headers={"x-api-key": "k-mon"})
    assert m.status_code == 200 and 'meshfx_decisions_total{decision="flash"}' in m.text


def test_limits_headers_errors_and_health(monkeypatch):
    c = TestClient(boot(monkeypatch, RATE_LIMIT="3").app)
    codes = [c.get("/v1/analyses").status_code for _ in range(5)]
    assert codes[:3] == [200] * 3 and codes[3:] == [429, 429]
    api = boot(monkeypatch, MAX_BODY_BYTES="500")

    @api.app.get("/boom")
    def boom():
        raise RuntimeError("secret detail: node !a1b2c3d4 at 51.5,-0.1")

    c = TestClient(api.app)
    assert c.post("/v1/carve", content=b"x" * 600).status_code == 413

    def chunks():
        for _ in range(10):
            yield b"a" * 100

    assert c.post("/v1/flash", content=chunks()).status_code == 413
    crash = c.get("/boom")
    assert crash.status_code == 500 and "a1b2c3d4" not in crash.text and crash.json()["request_id"]
    bad = c.get("/v1/analyses", params={"limit": "SECRETNODE"})
    assert bad.status_code == 422 and "SECRETNODE" not in bad.text
    r = c.get("/v1/analyses", headers={"x-request-id": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123" and r.headers["content-security-policy"] == ops.API_CSP
    assert c.get("/healthz").json() == {"status": "ok"}
    assert c.get("/readyz").json()["checks"] == {"database": True}
    monkeypatch.setattr(api.engine, "connect", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    assert c.get("/readyz").status_code == 503


def test_json_logs_carry_request_ids(capsys):
    ops.setup_logging("INFO")
    token = ops.request_id.set("rid-1")
    ops.log.info("hello")
    ops.request_id.reset(token)
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["request_id"] == "rid-1"


def test_migrations_apply_once(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    eng = db.engine(url)
    assert db.migrate(eng) == ["001_init.sql"] and db.migrate(eng) == []
    with eng.connect() as c:
        tables = {r[0] for r in c.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))}
    assert {"analyses", "schema_migrations"} <= tables
    env = {**{k: v for k, v in os.environ.items() if not k.startswith("MESHFX_")}, "MESHFX_DATABASE_URL": url}
    out = subprocess.run([sys.executable, "-m", "meshfx", "migrate"], env=env, capture_output=True, text=True,
                         timeout=120, check=False)
    assert out.returncode == 0 and "up to date" in out.stdout
