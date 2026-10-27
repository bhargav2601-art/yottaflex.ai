"""SQLite persistence with restrictive foreign keys and deterministic schema setup."""
import os, sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("CREDENTIA_DB", "data/credentia.db"))

SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS issuers (id TEXT PRIMARY KEY, name TEXT NOT NULL, public_key TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS learners (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS courses (id TEXT PRIMARY KEY, code TEXT NOT NULL UNIQUE, title TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS credential_rules (id TEXT PRIMARY KEY, course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE RESTRICT, min_score REAL NOT NULL CHECK(min_score BETWEEN 0 AND 100), required_status TEXT NOT NULL DEFAULT 'COMPLETED', effective_from TEXT NOT NULL, effective_until TEXT, active INTEGER NOT NULL DEFAULT 1, version INTEGER NOT NULL, UNIQUE(course_id, version));
CREATE TABLE IF NOT EXISTS completions (id TEXT PRIMARY KEY, learner_id TEXT NOT NULL REFERENCES learners(id) ON DELETE RESTRICT, course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE RESTRICT, status TEXT NOT NULL CHECK(status IN ('COMPLETED','IN_PROGRESS','FAILED')), score REAL NOT NULL CHECK(score BETWEEN 0 AND 100), completed_on TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'synthetic');
CREATE INDEX IF NOT EXISTS completion_lookup ON completions(learner_id, course_id);
CREATE TABLE IF NOT EXISTS credentials (id TEXT PRIMARY KEY, learner_id TEXT NOT NULL REFERENCES learners(id) ON DELETE RESTRICT, course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE RESTRICT, completion_id TEXT NOT NULL UNIQUE REFERENCES completions(id) ON DELETE RESTRICT, issuer_id TEXT NOT NULL REFERENCES issuers(id) ON DELETE RESTRICT, rule_id TEXT NOT NULL REFERENCES credential_rules(id) ON DELETE RESTRICT, issued_at TEXT NOT NULL, payload_hash TEXT NOT NULL, signature TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ISSUED' CHECK(status IN ('ISSUED','REVOKED')));
CREATE TABLE IF NOT EXISTS credential_sequence (id INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS verification_sequence (id INTEGER PRIMARY KEY);
CREATE INDEX IF NOT EXISTS credential_lookup ON credentials(learner_id, course_id);
CREATE TABLE IF NOT EXISTS revocations (id TEXT PRIMARY KEY, credential_id TEXT NOT NULL UNIQUE REFERENCES credentials(id) ON DELETE RESTRICT, reason_code TEXT NOT NULL, explanation TEXT NOT NULL, revoked_at TEXT NOT NULL, actor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS verification_requests (id TEXT PRIMARY KEY, credential_id TEXT, decision TEXT NOT NULL, requested_at TEXT NOT NULL, requester_ip TEXT NOT NULL DEFAULT 'local');
CREATE TABLE IF NOT EXISTS audit_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, actor TEXT NOT NULL, occurred_at TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS anomaly_fixtures (id TEXT PRIMARY KEY, issue_type TEXT NOT NULL, expected_decision TEXT NOT NULL, observed TEXT NOT NULL, ground_truth INTEGER NOT NULL, notes TEXT NOT NULL);
'''

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def init_db():
    with connect() as c:
        c.executescript(SCHEMA)
        max_cred = c.execute("SELECT MAX(CAST(substr(id, 10) AS INTEGER)) FROM credentials").fetchone()[0]
        if max_cred:
            c.execute("INSERT OR IGNORE INTO credential_sequence(id) VALUES(?)", (max_cred,))
        max_ver = c.execute("SELECT MAX(CAST(substr(id, 10) AS INTEGER)) FROM verification_requests").fetchone()[0]
        if max_ver:
            c.execute("INSERT OR IGNORE INTO verification_sequence(id) VALUES(?)", (max_ver,))

