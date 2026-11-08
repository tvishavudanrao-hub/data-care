-- PROPOSAL ONLY. Not applied anywhere. Replace with / map onto Andy's existing
-- Neon dev schema before use (see verify/store.py for the column mapping).

-- Shared: readable by the Recovery Manager and the rest of the team.
-- Holds outcome, attempt metadata and LIMITED feedback only.
CREATE TABLE IF NOT EXISTS verdicts (
    verdict_id        text PRIMARY KEY,
    job_id            text NOT NULL,
    case_id           text NOT NULL,
    artifact_id       text NOT NULL,
    artifact_version  text NOT NULL,
    artifact_sha256   text NOT NULL,
    attempt           integer NOT NULL CHECK (attempt >= 1),
    retry_count       integer NOT NULL CHECK (retry_count >= 0),
    max_retries       integer NOT NULL,
    outcome           text NOT NULL CHECK (outcome IN ('pass', 'fail', 'error', 'untested')),
    verdict           text NOT NULL CHECK (verdict IN ('pass', 'fail')),   -- legacy field
    next_action       text NOT NULL,
    created_at        timestamptz NOT NULL,
    feedback          jsonb NOT NULL                                      -- verify.schema to_feedback()
);

-- Private: full per-example expected vs actual. Grant to the validation role only.
CREATE SCHEMA IF NOT EXISTS validation_private;
CREATE TABLE IF NOT EXISTS validation_private.verdict_details (
    verdict_id  text PRIMARY KEY REFERENCES verdicts (verdict_id),
    detail      jsonb NOT NULL                                            -- verify.schema to_private()
);
-- REVOKE ALL ON SCHEMA validation_private FROM PUBLIC;
-- GRANT USAGE ON SCHEMA validation_private TO validation_agent;
-- GRANT INSERT, SELECT ON validation_private.verdict_details TO validation_agent;
