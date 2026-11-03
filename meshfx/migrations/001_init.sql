-- The custody log: one row per analysis. Evidence is not stored, only the SHA-256 of each input
-- (inputs), so a result can be matched to an exhibit without keeping flash dumps or app databases.
-- summary holds the counts the analysis found.
CREATE TABLE analyses (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    inputs TEXT NOT NULL,
    summary TEXT NOT NULL
);
CREATE INDEX analyses_created ON analyses (created_at);
