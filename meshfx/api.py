"""Analysis service: flash dumps, companion-app databases and carving behind an API, with a log.

    POST /v1/flash             an ESP32 flash dump (body): partitions, files with hashes, timeline [analyse]
    POST /v1/app               an Android or iOS companion-app database (body): messages and nodes [analyse]
    POST /v1/carve             any raw image (body): message records found anywhere in it [analyse]
    GET  /v1/analyses[/{id}]   the analysis log: who submitted which input (by SHA-256), what was found [read]
    GET  /healthz, /readyz, /metrics

Evidence is analysed in memory or in a temporary file removed afterwards, and is not stored: each
analysis keeps the SHA-256 of its input, the counts found and who asked. Callers send an API key
whose role decides the permissions in brackets; settings come from MESHFX_* variables (see ops.py
and docs/runbook.md).

    python -m meshfx serve
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import text

from . import apps, db, flash, msgstore, ops, report

settings = ops.load_settings()
ops.setup_logging(settings.log_level)
engine = db.connect(settings.database_url)
_lock = threading.Lock()

app = FastAPI(title="MeshFX analysis service", version="1.0.0")
ops.install(app, settings, {"database": lambda: engine.connect().close()})


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _log(ident: dict, kind: str, label: str, sha: str, summary: Dict[str, Any]) -> str:
    aid = uuid.uuid4().hex
    with _lock, engine.begin() as c:
        c.execute(text("INSERT INTO analyses VALUES (:i, :t, :u, :k, :l, :n, :s)"),
                  {"i": aid, "t": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                   "u": ident["user"] or "demo", "k": kind, "l": label, "n": json.dumps({kind: sha}),
                   "s": json.dumps(summary)})
    ops.DECISIONS.labels(decision=kind).inc()
    return aid


async def _body(request: Request, what: str) -> bytes:
    data = await request.body()
    if not data:
        raise HTTPException(422, f"send the {what} as the request body")
    return data


@app.post("/v1/flash")
async def flash_dump(request: Request, fmt: Literal["json", "csv", "html"] = Query("json", alias="format"),
                     label: str = Query("", max_length=200),
                     ident: dict = Depends(ops.require("analyse"))) -> Response:
    data = await _body(request, "ESP32 flash dump")
    try:
        parts = flash.parse_partition_table(data)
        files = flash.extract_files(data)
        events = report.build_timeline(report.from_flash(data))
    except Exception:  # a seized image can be corrupt in any way; the parsers raise many kinds
        raise HTTPException(422, "not a readable ESP32 flash dump (partition table and LittleFS data partition)") from None
    sha = _sha(data)
    summary = {"partitions": len(parts), "files": len(files), "events": len(events),
               "messages": sum(1 for e in events if e.get("kind") == "message")}
    aid = _log(ident, "flash", label, sha, summary)
    headers = {"x-analysis-id": aid, "x-input-sha256": sha}
    if fmt != "json":
        out = (report.to_csv if fmt == "csv" else report.to_html)(events)
        return Response(out, media_type="text/csv; charset=utf-8" if fmt == "csv" else "text/html; charset=utf-8",
                        headers=headers)
    body = {"analysis_id": aid, "input_sha256": sha, "partitions": parts,
            "files": [{"path": p, "bytes": len(b), "sha256": _sha(b)} for p, b in sorted(files.items())],
            "timeline": events}
    return Response(json.dumps(body, ensure_ascii=False, default=str), media_type="application/json", headers=headers)


@app.post("/v1/app")
async def app_db(request: Request, label: str = Query("", max_length=200),
                 ident: dict = Depends(ops.require("analyse"))) -> Response:
    data = await _body(request, "companion-app database")
    if not data.startswith(b"SQLite format 3\x00"):
        raise HTTPException(422, "send a Meshtastic companion-app SQLite database as the request body")
    fd, path = tempfile.mkstemp(prefix="meshfx-", suffix=".db")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        rows = apps.read(path)
    except (ValueError, sqlite3.Error):
        raise HTTPException(422, "not a recognised Meshtastic companion-app database") from None
    finally:
        os.unlink(path)
    sha = _sha(data)
    summary = {"messages": sum(1 for r in rows if r.get("kind") == "message"),
               "nodes": sum(1 for r in rows if r.get("kind") == "node")}
    aid = _log(ident, "app", label, sha, summary)
    body = {"analysis_id": aid, "input_sha256": sha, "rows": report.build_timeline(rows)}
    return Response(json.dumps(body, ensure_ascii=False, default=str), media_type="application/json")


@app.post("/v1/carve")
async def carve(request: Request, label: str = Query("", max_length=200),
                ident: dict = Depends(ops.require("analyse"))) -> Response:
    data = await _body(request, "raw image")
    records = msgstore.carve_msgs(data)
    sha = _sha(data)
    aid = _log(ident, "carve", label, sha, {"records": len(records), "bytes": len(data)})
    body = {"analysis_id": aid, "input_sha256": sha, "records": records}
    return Response(json.dumps(body, ensure_ascii=False, default=str), media_type="application/json")


def _row(r) -> Dict[str, Any]:
    d = dict(r)
    for k in ("inputs", "summary"):
        if k in d:
            d[k] = json.loads(d[k])
    return d


@app.get("/v1/analyses", dependencies=[Depends(ops.require("read"))])
def list_analyses(limit: int = Query(50, ge=1, le=1000)) -> Dict[str, Any]:
    with engine.connect() as c:
        rows = c.execute(text("SELECT * FROM analyses ORDER BY created_at DESC LIMIT :n"), {"n": limit}).mappings().all()
    return {"analyses": [_row(r) for r in rows]}


@app.get("/v1/analyses/{analysis_id}", dependencies=[Depends(ops.require("read"))])
def get_analysis(analysis_id: str) -> Dict[str, Any]:
    with engine.connect() as c:
        r = c.execute(text("SELECT * FROM analyses WHERE id = :i"), {"i": analysis_id[:64]}).mappings().first()
    if r is None:
        raise HTTPException(404, "analysis not found")
    return _row(r)
