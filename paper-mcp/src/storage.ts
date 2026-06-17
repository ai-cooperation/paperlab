import { initialGrillState } from "./contracts";
import { quotaLimitForTier, sha256Hex, tokenExpiry } from "./security";
import type { AuthUser, Level, SessionRecord, Tier } from "./types";

type UserRow = {
  user_id: string;
  tier: Tier;
  quota_used: number;
  quota_limit: number;
  token_expires_at: string | null;
};

export async function createOrReplaceTokenUser(env: Env, userId: string, tier: Tier, token: string): Promise<void> {
  const tokenHash = await sha256Hex(token);
  const quotaLimit = quotaLimitForTier(env, tier);
  await env.DB.prepare(
    `INSERT INTO users (user_id, tier, quota_used, quota_limit, token_hash, token_created_at, token_expires_at, updated_at)
     VALUES (?, ?, 0, ?, ?, CURRENT_TIMESTAMP, ?, CURRENT_TIMESTAMP)
     ON CONFLICT(user_id) DO UPDATE SET
       tier = excluded.tier,
       quota_limit = excluded.quota_limit,
       token_hash = excluded.token_hash,
       token_created_at = excluded.token_created_at,
       token_expires_at = excluded.token_expires_at,
       updated_at = CURRENT_TIMESTAMP`
  ).bind(userId, tier, quotaLimit, tokenHash, tokenExpiry(env)).run();
}

export async function userFromToken(env: Env, token: string): Promise<AuthUser | null> {
  const tokenHash = await sha256Hex(token);
  const row = await env.DB.prepare(
    `SELECT user_id, tier, quota_used, quota_limit, token_expires_at
     FROM users WHERE token_hash = ?`
  ).bind(tokenHash).first<UserRow>();
  if (!row) return null;
  if (row.token_expires_at && Date.parse(row.token_expires_at) < Date.now()) return null;
  return {
    userId: row.user_id,
    tier: row.tier,
    quotaUsed: Number(row.quota_used || 0),
    quotaLimit: Number(row.quota_limit || 0)
  };
}

export async function ensureUser(env: Env, user: AuthUser): Promise<void> {
  await env.DB.prepare(
    `INSERT INTO users (user_id, tier, quota_used, quota_limit)
     VALUES (?, ?, ?, ?)
     ON CONFLICT(user_id) DO NOTHING`
  ).bind(user.userId, user.tier, user.quotaUsed, user.quotaLimit).run();
}

export async function createSession(env: Env, user: AuthUser, topicSeed: string): Promise<SessionRecord> {
  const sessionId = `ps-${crypto.randomUUID()}`;
  await ensureUser(env, user);
  await env.DB.prepare(
    `INSERT INTO sessions (session_id, user_id, tier, topic_seed, grill_state)
     VALUES (?, ?, ?, ?, ?)`
  ).bind(sessionId, user.userId, user.tier, topicSeed, JSON.stringify(initialGrillState())).run();
  return getSession(env, sessionId, user);
}

export async function getSession(env: Env, sessionId: string, user: AuthUser): Promise<SessionRecord> {
  const row = await env.DB.prepare(
    `SELECT * FROM sessions WHERE session_id = ? AND user_id = ?`
  ).bind(sessionId, user.userId).first<SessionRecord>();
  if (!row) throw new Error(`unknown session_id: ${sessionId}`);
  return row;
}

export async function listSessions(env: Env, user: AuthUser) {
  const rows = await env.DB.prepare(
    `SELECT session_id, level, tier, topic_seed, updated_at
     FROM sessions WHERE user_id = ? ORDER BY updated_at DESC LIMIT 20`
  ).bind(user.userId).all();
  return rows.results || [];
}

export async function updateSessionState(env: Env, sessionId: string, user: AuthUser, grillState: string, level: Level | null): Promise<void> {
  await env.DB.prepare(
    `UPDATE sessions SET grill_state = ?, level = COALESCE(?, level), updated_at = CURRENT_TIMESTAMP
     WHERE session_id = ? AND user_id = ?`
  ).bind(grillState, level, sessionId, user.userId).run();
}

export async function saveContractDraft(env: Env, sessionId: string, user: AuthUser, contract: unknown): Promise<void> {
  await env.DB.prepare(
    `UPDATE sessions SET contract_draft = ?, updated_at = CURRENT_TIMESTAMP
     WHERE session_id = ? AND user_id = ?`
  ).bind(JSON.stringify(contract), sessionId, user.userId).run();
}

export async function addFinding(env: Env, sessionId: string, user: AuthUser, claim: string, sourceUrl: string): Promise<string> {
  await getSession(env, sessionId, user);
  const findingId = `pf-${crypto.randomUUID()}`;
  const r2Key = `findings/${sessionId}/${findingId}.json`;
  await env.ARTIFACTS.put(r2Key, JSON.stringify({ finding_id: findingId, session_id: sessionId, claim, source_url: sourceUrl }, null, 2), {
    httpMetadata: { contentType: "application/json" }
  });
  await env.DB.prepare(
    `INSERT INTO findings (finding_id, session_id, claim, source_url, r2_key)
     VALUES (?, ?, ?, ?, ?)`
  ).bind(findingId, sessionId, claim, sourceUrl, r2Key).run();
  return findingId;
}

export async function recordJob(env: Env, user: AuthUser, sessionId: string | null, jobId: string, status: string, remotePayload: unknown): Promise<void> {
  await env.DB.prepare(
    `INSERT INTO jobs (job_id, session_id, user_id, status, remote_payload)
     VALUES (?, ?, ?, ?, ?)
     ON CONFLICT(job_id) DO UPDATE SET
       status = excluded.status,
       remote_payload = excluded.remote_payload,
       updated_at = CURRENT_TIMESTAMP`
  ).bind(jobId, sessionId, user.userId, status, JSON.stringify(remotePayload)).run();
}

export async function incrementQuota(env: Env, user: AuthUser): Promise<void> {
  await env.DB.prepare(
    `UPDATE users SET quota_used = quota_used + 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?`
  ).bind(user.userId).run();
}

export type ViabilityLock = {
  contract_hash: string;
  viable: boolean;
  engine_base_url: string;
  approved: boolean;
};

export async function storeViabilityLock(env: Env, sessionId: string, user: AuthUser, lock: ViabilityLock): Promise<void> {
  await env.DB.prepare(
    `INSERT OR REPLACE INTO viability_locks (session_id, user_id, contract_hash, viable, engine_base_url, approved, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  ).bind(sessionId, user.userId, lock.contract_hash, lock.viable ? 1 : 0,
    lock.engine_base_url, lock.approved ? 1 : 0, new Date().toISOString()).run();
}

export async function readViabilityLock(env: Env, sessionId: string, user: AuthUser): Promise<ViabilityLock | null> {
  const row = await env.DB.prepare(
    `SELECT contract_hash, viable, engine_base_url, approved FROM viability_locks WHERE session_id = ? AND user_id = ?`
  ).bind(sessionId, user.userId).first<{ contract_hash: string; viable: number; engine_base_url: string; approved: number }>();
  if (!row) return null;
  return { contract_hash: row.contract_hash, viable: !!row.viable,
    engine_base_url: row.engine_base_url, approved: !!row.approved };
}

export async function readIdempotency(env: Env, key: string, user: AuthUser) {
  return env.DB.prepare(
    `SELECT key, job_id, request_hash, response_json FROM idempotency WHERE key = ? AND user_id = ?`
  ).bind(key, user.userId).first<{ key: string; job_id: string | null; request_hash: string; response_json: string }>();
}

export async function writeIdempotency(env: Env, key: string, user: AuthUser, requestHash: string, jobId: string, responsePayload: unknown): Promise<void> {
  await env.DB.prepare(
    `INSERT INTO idempotency (key, user_id, job_id, request_hash, response_json)
     VALUES (?, ?, ?, ?, ?)`
  ).bind(key, user.userId, jobId, requestHash, JSON.stringify(responsePayload)).run();
}

export async function audit(env: Env, action: string, detail: { user?: AuthUser; sessionId?: string; jobId?: string; payload?: unknown }): Promise<void> {
  await env.DB.prepare(
    `INSERT INTO audit_log (audit_id, user_id, session_id, job_id, action, detail_json)
     VALUES (?, ?, ?, ?, ?, ?)`
  ).bind(
    `pa-${crypto.randomUUID()}`,
    detail.user?.userId || null,
    detail.sessionId || null,
    detail.jobId || null,
    action,
    JSON.stringify(detail.payload || {})
  ).run();
}
