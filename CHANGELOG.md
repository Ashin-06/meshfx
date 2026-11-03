# Changelog

All notable changes to this project. Versions follow [semantic versioning](https://semver.org/).

## 1.0.0 — 2026-11-03

### Added
- An analysis API (`meshfx serve`): `POST /v1/flash` (partition table, files with SHA-256s and the
  timeline, as JSON, CSV or HTML), `POST /v1/app`, `POST /v1/carve` and `GET /v1/analyses[/{id}]`.
  Evidence is not stored; each analysis records its input SHA-256, the counts found and who asked,
  in SQLite or Postgres with numbered migrations (`meshfx migrate`).
- Settings from `MESHFX_*` environment variables, checked at startup; production refuses to start
  without hashed API keys and a database. Roles on keys, rate limit, body cap, security headers,
  JSON logs with request IDs, `/healthz`, `/readyz` and Prometheus `/metrics`.
- `pyproject.toml` 1.0.0 (Python 3.12+, with the generated `proto` packages listed so they ship in
  the wheel), pinned lock files, a container image (slim, non-root, health check), CI with ruff,
  bandit, pip-audit and coverage (it replaces the old test workflow and keeps its import-order
  check and warnings-as-errors).
- `SECURITY.md`, `docs/threat-model.md`, `docs/runbook.md`, MIT licence.

### Fixed
- `extract -o` joined file names from the seized image onto the output folder unchecked, so a
  crafted name could write outside it. Paths that resolve outside the folder are now refused.
- The iOS app reader put column names from the database's own schema into queries unquoted; they
  are quoted as identifiers now. App databases are opened with `trusted_schema = OFF`.
- The CLI left evidence files open after reading them.

### Unchanged
- Parsing, carving and timelines; the 19 original tests pass unchanged apart from two
  `assert False` lines rewritten as `raise AssertionError` and one line split into four.
