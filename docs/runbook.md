# Runbook

How to deploy and operate the analysis service. Commands assume the repository root.

## Deploy

```bash
docker build -t meshfx:1.0.0 .
python -m meshfx.ops keygen             # one API key per examiner, viewer and monitor
docker run -d --name meshfx -p 8101:8101 -v meshfx-data:/data \
  -e MESHFX_KEYS_FILE=/run/secrets/meshfx-keys.json \
  meshfx:1.0.0
curl -fsS http://127.0.0.1:8101/readyz
```

The image runs in production mode as a non-root user with its log in SQLite under `/data`. It
refuses to start, and logs why, without hashed API keys or a database URL. It needs no outbound
network access.

## Use

Send hash-verified working copies, never the original evidence.

```bash
curl -fsS -H "x-api-key: $KEY" --data-binary @flash.bin "http://127.0.0.1:8101/v1/flash?label=radio%201" > radio1.json
curl -fsS -H "x-api-key: $KEY" --data-binary @flash.bin "http://127.0.0.1:8101/v1/flash?format=html" > radio1.html
curl -fsS -H "x-api-key: $KEY" --data-binary @meshtastic_database "http://127.0.0.1:8101/v1/app?label=phone%201"
curl -fsS -H "x-api-key: $KEY" --data-binary @nrf52.bin http://127.0.0.1:8101/v1/carve
```

For a database, copy it with its `-wal` and `-shm` files and checkpoint the copy first, or recent
rows in the WAL are missed.

## Configure

| Variable | Required in production | Meaning |
|---|---|---|
| `MESHFX_ENV` | — | `development` (default) or `production` |
| `MESHFX_API_KEYS` / `MESHFX_KEYS_FILE` | yes | JSON `{"sha256:<hex>": {"user": "...", "role": "..."}}`. Roles: `examiner` (analyse, read), `viewer`, `monitor`, `admin` |
| `MESHFX_DATABASE_URL` | yes | the analysis log: `sqlite:////data/meshfx.db` or `postgresql://...` |
| `MESHFX_HOST`, `MESHFX_PORT` | — | default `127.0.0.1:8101`; any other address needs API keys |
| `MESHFX_RATE_LIMIT`, `MESHFX_MAX_BODY_BYTES` | — | default 120/min per client, 40,000,000 bytes |
| `MESHFX_CORS_ORIGINS` | — | comma-separated origins allowed to call the API from a browser |

## Watch

- `GET /healthz`; `GET /readyz` (database); `GET /metrics` (role `monitor`): requests, latency,
  errors, `meshfx_decisions_total{decision="flash|app|carve"}`.

## Rotate keys

Add the new API key hash, restart, hand over the key, remove the old hash, restart.

## Back up and restore

Back up the log like any SQLite or Postgres database (`python -m meshfx migrate` creates the schema
on a fresh one). Restrict access to it: it shows which devices were examined and when.

## Incidents

1. **Leaked API key.** Remove its hash and restart; list that user's entries.
2. **A timeline is challenged.** Find the entry, compare its input hash with the image's hash in
   the acquisition notes, and re-run the same image with the same version.
