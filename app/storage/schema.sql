-- StegoNexus schema v1  (SQLite)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    number       TEXT    NOT NULL UNIQUE,
    title        TEXT    NOT NULL,
    description  TEXT    DEFAULT '',
    investigator TEXT    DEFAULT '',
    status       TEXT    NOT NULL DEFAULT 'Open',
    notes        TEXT    DEFAULT '',
    tags         TEXT    DEFAULT '',
    created      TEXT    NOT NULL,
    closed       TEXT
);

CREATE TABLE IF NOT EXISTS evidence (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id    INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    name       TEXT    NOT NULL,
    path       TEXT    NOT NULL,
    kind       TEXT    NOT NULL DEFAULT 'original',
    source     TEXT    DEFAULT '',
    notes      TEXT    DEFAULT '',
    size       INTEGER DEFAULT 0,
    mime       TEXT    DEFAULT '',
    md5        TEXT    DEFAULT '',
    sha1       TEXT    DEFAULT '',
    sha256     TEXT    DEFAULT '',
    sha512     TEXT    DEFAULT '',
    status     TEXT    DEFAULT 'imported',
    created    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_case ON evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_evidence_sha256 ON evidence(sha256);

CREATE TABLE IF NOT EXISTS hashes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER REFERENCES cases(id) ON DELETE SET NULL,
    evidence_id INTEGER REFERENCES evidence(id) ON DELETE SET NULL,
    path        TEXT NOT NULL,
    size        INTEGER DEFAULT 0,
    md5         TEXT DEFAULT '',
    sha1        TEXT DEFAULT '',
    sha256      TEXT DEFAULT '',
    sha512      TEXT DEFAULT '',
    elapsed_ms  REAL DEFAULT 0,
    created     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER REFERENCES cases(id) ON DELETE SET NULL,
    evidence_id INTEGER REFERENCES evidence(id) ON DELETE SET NULL,
    kind        TEXT NOT NULL,
    path        TEXT NOT NULL,
    tool        TEXT DEFAULT '',
    status      TEXT DEFAULT '',
    summary     TEXT DEFAULT '',
    payload     TEXT DEFAULT '{}',
    elapsed_ms  REAL DEFAULT 0,
    created     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analyses_kind ON analyses(kind);

CREATE TABLE IF NOT EXISTS metadata_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER REFERENCES cases(id) ON DELETE SET NULL,
    evidence_id INTEGER REFERENCES evidence(id) ON DELETE SET NULL,
    path        TEXT NOT NULL,
    source      TEXT DEFAULT '',
    available   INTEGER DEFAULT 1,
    entries     TEXT DEFAULT '[]',
    hashes      TEXT DEFAULT '{}',
    error       TEXT DEFAULT '',
    created     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extractions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id      INTEGER REFERENCES cases(id) ON DELETE SET NULL,
    evidence_id  INTEGER REFERENCES evidence(id) ON DELETE SET NULL,
    technique    TEXT NOT NULL,
    operation    TEXT NOT NULL,
    engine       TEXT DEFAULT '',
    status_label TEXT DEFAULT '',
    status       TEXT DEFAULT '',
    input_path   TEXT DEFAULT '',
    output_path  TEXT DEFAULT '',
    payload_bytes INTEGER DEFAULT 0,
    capacity_bytes INTEGER DEFAULT 0,
    input_hash   TEXT DEFAULT '',
    output_hash  TEXT DEFAULT '',
    verified     INTEGER,
    error        TEXT DEFAULT '',
    messages     TEXT DEFAULT '[]',
    details      TEXT DEFAULT '{}',
    elapsed_ms   REAL DEFAULT 0,
    created      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_extractions_case ON extractions(case_id);

CREATE TABLE IF NOT EXISTS findings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id      INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    evidence_id  INTEGER REFERENCES evidence(id) ON DELETE SET NULL,
    category     TEXT NOT NULL,
    severity     TEXT NOT NULL,
    title        TEXT NOT NULL,
    description  TEXT DEFAULT '',
    indicator    TEXT DEFAULT '',
    evidence_ref TEXT DEFAULT '',
    confidence   TEXT DEFAULT 'Medium',
    investigator TEXT DEFAULT '',
    created      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS investigation_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    user        TEXT DEFAULT '',
    action      TEXT NOT NULL,
    module      TEXT DEFAULT '',
    target      TEXT DEFAULT '',
    case_id     INTEGER REFERENCES cases(id) ON DELETE SET NULL,
    evidence_id INTEGER REFERENCES evidence(id) ON DELETE SET NULL,
    tool        TEXT DEFAULT '',
    result      TEXT DEFAULT '',
    status      TEXT DEFAULT 'OK',
    hash        TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_logs_case ON investigation_logs(case_id);
CREATE INDEX IF NOT EXISTS idx_logs_ts ON investigation_logs(ts);

CREATE TABLE IF NOT EXISTS tool_executions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tool        TEXT NOT NULL,
    argv        TEXT DEFAULT '[]',
    available   INTEGER DEFAULT 0,
    returncode  INTEGER DEFAULT 0,
    status      TEXT DEFAULT '',
    stdout_len  INTEGER DEFAULT 0,
    stderr_len  INTEGER DEFAULT 0,
    stderr_head TEXT DEFAULT '',
    timed_out   INTEGER DEFAULT 0,
    elapsed_ms  REAL DEFAULT 0,
    case_id     INTEGER REFERENCES cases(id) ON DELETE SET NULL,
    created     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id   INTEGER REFERENCES cases(id) ON DELETE SET NULL,
    title     TEXT NOT NULL,
    fmt       TEXT NOT NULL,
    path      TEXT NOT NULL,
    sha256    TEXT DEFAULT '',
    sections  INTEGER DEFAULT 0,
    created   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
