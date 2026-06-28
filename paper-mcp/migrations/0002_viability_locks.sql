-- Viability-lock (BSIDE_WEB_INTEGRATION_PLAN §4): the b-side stores the a-side-
-- returned contract_hash + verdict; submit to the /v2 engine refuses without an
-- approved, hash-matched, viable lock. The lock also binds the engine_base_url so a
-- staging lock cannot authorize a production submit.
CREATE TABLE IF NOT EXISTS viability_locks (
  session_id       TEXT NOT NULL,
  user_id          TEXT NOT NULL,
  contract_hash    TEXT NOT NULL,         -- a-side authoritative hash (b never recomputes)
  viable           INTEGER NOT NULL,      -- 1/0
  engine_base_url  TEXT,
  approved         INTEGER NOT NULL DEFAULT 0,
  created_at       TEXT NOT NULL,
  PRIMARY KEY (session_id, user_id)
);
