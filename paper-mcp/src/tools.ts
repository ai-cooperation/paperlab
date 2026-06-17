import { z } from "zod";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { buildContract, coerceLevel, grillFramework, nextGrillState, parseGrillState } from "./contracts";
import { assertQuota, sha256Hex, textResult } from "./security";
import {
  addFinding,
  audit,
  getSession,
  incrementQuota,
  listSessions,
  readIdempotency,
  readViabilityLock,
  recordJob,
  saveContractDraft,
  storeViabilityLock,
  updateSessionState,
  writeIdempotency
} from "./storage";
import type { AuthUser, ResearchContract } from "./types";

type RemoteResponse = {
  ok: boolean;
  status: number;
  payload: unknown;
};

export function registerPaperTools(server: McpServer, env: Env, user: AuthUser): void {
  server.tool(
    "start_paper_session",
    "Start a paper grill session and return the 7-step framework.",
    { topic_seed: z.string().min(1) },
    async ({ topic_seed }) => textResult(await startPaperSession(env, user, topic_seed))
  );

  server.tool(
    "get_paper_session",
    "Read one paper grill session.",
    { session_id: z.string().min(1) },
    async ({ session_id }) => textResult(await getPaperSession(env, user, session_id))
  );

  server.tool(
    "list_paper_sessions",
    "List recent paper grill sessions for the authenticated user.",
    {},
    async () => textResult({ sessions: await listSessions(env, user) })
  );

  server.tool(
    "resume_paper_session",
    "Resume a paper grill session and return the next required step.",
    { session_id: z.string().min(1) },
    async ({ session_id }) => textResult(await getPaperSession(env, user, session_id))
  );

  server.tool(
    "record_grill_decision",
    "Record one grill step decision. Steps must be recorded in order.",
    {
      session_id: z.string().min(1),
      step: z.number().int().min(1).max(7),
      decision: z.unknown()
    },
    async ({ session_id, step, decision }) => textResult(await recordGrillDecision(env, user, session_id, step, decision))
  );

  server.tool(
    "confirm_research_contract",
    "Build and persist the exact a-side research_contract for submission.",
    {
      session_id: z.string().min(1),
      decisions: z.record(z.string(), z.unknown()).optional()
    },
    async ({ session_id, decisions }) => textResult(await confirmResearchContract(env, user, session_id, decisions || {}))
  );

  server.tool(
    "validate_research_contract",
    "Validate a research_contract against the a-side dry-run endpoint.",
    { research_contract: z.record(z.string(), z.unknown()) },
    async ({ research_contract }) => textResult(await callJobService(env, "/jobs/dry-run", "POST", research_contract))
  );

  server.tool(
    "deep_research",
    "Run configured external deep research. Returns unavailable if no endpoint is configured.",
    {
      session_id: z.string().min(1),
      query: z.string().min(1)
    },
    async ({ session_id, query }) => textResult(await deepResearch(env, user, session_id, query))
  );

  server.tool(
    "probe_data_source",
    "Probe a data source through the a-side data availability gate.",
    {
      session_id: z.string().min(1),
      source: z.record(z.string(), z.unknown())
    },
    async ({ session_id, source }) => textResult(await probeDataSource(env, user, session_id, source))
  );

  server.tool(
    "add_finding",
    "Persist an evidence-backed finding. source_url is required.",
    {
      session_id: z.string().min(1),
      claim: z.string().min(1),
      source_url: z.string().url()
    },
    async ({ session_id, claim, source_url }) => textResult(await addPaperFinding(env, user, session_id, claim, source_url))
  );

  server.tool(
    "assess_feasibility",
    "Assess readiness using recorded findings, grill completion, and data probe state.",
    { session_id: z.string().min(1) },
    async ({ session_id }) => textResult(await assessFeasibility(env, user, session_id))
  );

  server.tool(
    "probe_viability",
    "Probe research viability on the a-side (collect corpus + poolable-k) and store an approved viability-lock. Required before submitting to the /v2 engine.",
    {
      session_id: z.string().min(1),
      research_contract: z.record(z.string(), z.unknown())
    },
    async ({ session_id, research_contract }) =>
      textResult(await probeViability(env, user, session_id, research_contract as ResearchContract))
  );

  server.tool(
    "submit_to_pipeline",
    "Submit a confirmed research_contract to the a-side FastAPI job service. Requires confirm=true and idempotency_key.",
    {
      session_id: z.string().min(1).optional(),
      research_contract: z.record(z.string(), z.unknown()),
      idempotency_key: z.string().min(8),
      confirm: z.boolean()
    },
    async ({ session_id, research_contract, idempotency_key, confirm }) =>
      textResult(await submitToPipeline(env, user, session_id || null, research_contract as ResearchContract, idempotency_key, confirm))
  );

  server.tool(
    "get_job_status",
    "Fetch a-side job status through the tunnel URL.",
    { job_id: z.string().min(1) },
    async ({ job_id }) => textResult(await getJobStatus(env, user, job_id))
  );

  server.tool(
    "get_paper_result",
    "Fetch a-side paper result and mirror result metadata locally.",
    { job_id: z.string().min(1) },
    async ({ job_id }) => textResult(await getPaperResult(env, user, job_id))
  );

  server.tool(
    "search_existing_topics",
    "Search recent sessions for overlapping topic text.",
    { query: z.string().min(1) },
    async ({ query }) => textResult(await searchExistingTopics(env, user, query))
  );
}

async function startPaperSession(env: Env, user: AuthUser, topicSeed: string) {
  const { createSession } = await import("./storage");
  const session = await createSession(env, user, topicSeed);
  await audit(env, "start_paper_session", { user, sessionId: session.session_id, payload: { topic_seed: topicSeed } });
  return {
    session_id: session.session_id,
    grill_framework: grillFramework(null),
    existing_topic_match: await searchExistingTopics(env, user, topicSeed)
  };
}

async function getPaperSession(env: Env, user: AuthUser, sessionId: string) {
  const session = await getSession(env, sessionId, user);
  const state = parseGrillState(session.grill_state);
  return {
    session_id: session.session_id,
    level: session.level,
    tier: session.tier,
    topic_seed: session.topic_seed,
    grill_state: state,
    contract_draft: session.contract_draft ? JSON.parse(session.contract_draft) : null,
    grill_framework: grillFramework(session.level),
    next_step: state.current_step <= 7 ? state.current_step : null
  };
}

async function recordGrillDecision(env: Env, user: AuthUser, sessionId: string, step: number, decision: unknown) {
  const session = await getSession(env, sessionId, user);
  const updated = nextGrillState(parseGrillState(session.grill_state), step, decision);
  const level = step === 1 ? coerceLevel(extractDecisionValue(decision, "level")) : null;
  await updateSessionState(env, sessionId, user, JSON.stringify(updated), level);
  await audit(env, "record_grill_decision", { user, sessionId, payload: { step, decision } });
  return {
    session_id: sessionId,
    next_step: updated.current_step <= 7 ? updated.current_step : null,
    level: level || session.level,
    level_constraints: grillFramework(level || session.level).level_constraints
  };
}

async function confirmResearchContract(env: Env, user: AuthUser, sessionId: string, decisions: Record<string, unknown>) {
  const session = await getSession(env, sessionId, user);
  const contract = buildContract(session, parseGrillState(session.grill_state), decisions);
  await saveContractDraft(env, sessionId, user, contract);
  await audit(env, "confirm_research_contract", { user, sessionId, payload: { job_id: contract.job_id, level: contract.level } });
  return {
    research_contract: contract,
    validation: await callJobService(env, "/jobs/dry-run", "POST", contract)
  };
}

async function deepResearch(env: Env, user: AuthUser, sessionId: string, query: string) {
  await getSession(env, sessionId, user);
  if (!env.DEEP_RESEARCH_ENDPOINT) {
    await audit(env, "deep_research_unavailable", { user, sessionId, payload: { query } });
    return { status: "unavailable", reason: "DEEP_RESEARCH_ENDPOINT is not configured", findings: [], gaps: [], competitors: [] };
  }
  const result = await fetchJson(env.DEEP_RESEARCH_ENDPOINT, "POST", { session_id: sessionId, query }, {});
  await audit(env, "deep_research", { user, sessionId, payload: { query, status: result.status } });
  return result.payload;
}

async function probeDataSource(env: Env, user: AuthUser, sessionId: string, source: Record<string, unknown>) {
  const session = await getSession(env, sessionId, user);
  const state = parseGrillState(session.grill_state);
  const contract = buildContract(session, state, { "4": { data_source: source }, job_id: `probe-${crypto.randomUUID()}` });
  const result = await callJobService(env, "/jobs/probe-data-source", "POST", contract);
  await audit(env, "probe_data_source", { user, sessionId, payload: { source, result } });
  return result;
}

async function addPaperFinding(env: Env, user: AuthUser, sessionId: string, claim: string, sourceUrl: string) {
  const findingId = await addFinding(env, sessionId, user, claim, sourceUrl);
  await audit(env, "add_finding", { user, sessionId, payload: { finding_id: findingId, source_url: sourceUrl } });
  return { finding_id: findingId };
}

async function assessFeasibility(env: Env, user: AuthUser, sessionId: string) {
  const session = await getSession(env, sessionId, user);
  const state = parseGrillState(session.grill_state);
  const findings = await env.DB.prepare(`SELECT COUNT(*) AS count FROM findings WHERE session_id = ?`).bind(sessionId).first<{ count: number }>();
  const completed = state.completed_steps.length;
  const dataDecision = state.decisions["4"];
  const dataText = JSON.stringify(dataDecision || {});
  const dataOk = dataText.includes("available");
  const verdict = completed >= 7 && dataOk && Number(findings?.count || 0) > 0 ? "ready" : "needs_more_work";
  return {
    value_score: Number(findings?.count || 0) > 0 ? "evidence_present" : "no_evidence_yet",
    novelty_check: session.level === "phd" ? "requires innovation-positioning review" : "application value acceptable",
    data_ok: dataOk,
    verdict
  };
}

async function probeViability(env: Env, user: AuthUser, sessionId: string, contract: ResearchContract) {
  // The a-side owns the corpus + the canonical contract_hash; b stores the verdict +
  // approves the lock if viable (b never recomputes the hash). Thin handoff: only the
  // structured contract crosses, never dense numbers (a-side rejects those too).
  const verdict = await callJobService(env, "/jobs/viability-probe", "POST", contract) as {
    contract_hash: string; viable: boolean; [k: string]: unknown };
  await storeViabilityLock(env, sessionId, user, {
    contract_hash: verdict.contract_hash, viable: verdict.viable,
    engine_base_url: env.PAPER_JOB_SERVICE_URL, approved: !!verdict.viable
  });
  await audit(env, "probe_viability", { user, sessionId, payload: { contract_hash: verdict.contract_hash, viable: verdict.viable } });
  return { ...verdict, lock_stored: true, approved: !!verdict.viable };
}

async function submitToPipeline(env: Env, user: AuthUser, sessionId: string | null, contract: ResearchContract, key: string, confirm: boolean) {
  if (!confirm) throw new Error("submit_to_pipeline requires confirm=true because it triggers real compute");
  assertQuota(user);
  const endpoint = env.A_ENGINE_ENDPOINT || "/jobs";
  // The /v2 engine requires an approved, hash-matched, viable lock (§4). The old /jobs
  // path is unchanged (A/B-safe; default until a golden A/B passes).
  if (endpoint.includes("/v2/")) {
    if (!sessionId) throw new Error("v2 submit requires session_id (for the viability-lock)");
    const lock = await readViabilityLock(env, sessionId, user);
    if (!lock || !lock.approved) throw new Error("submit refused: run probe_viability first to obtain an approved viability-lock");
    if (lock.engine_base_url !== env.PAPER_JOB_SERVICE_URL) throw new Error("submit refused: viability-lock was issued for a different engine");
    const reprobe = await callJobService(env, "/jobs/viability-probe", "POST", contract) as { contract_hash?: string; viable?: boolean };
    if (!reprobe.viable) throw new Error("submit refused: contract is non-viable");
    if (reprobe.contract_hash !== lock.contract_hash) throw new Error("submit refused: scope changed since approval (hash mismatch) — re-probe + re-approve");
  }
  const requestHash = await sha256Hex(JSON.stringify(contract));
  const existing = await readIdempotency(env, key, user);
  if (existing) {
    if (existing.request_hash !== requestHash) throw new Error("idempotency_key already used with a different research_contract");
    return { ...JSON.parse(existing.response_json), idempotent_replay: true };
  }
  const result = await callJobService(env, endpoint, "POST", contract, { "Idempotency-Key": key });
  const jobId = extractJobId(result);
  await writeIdempotency(env, key, user, requestHash, jobId, result);
  await recordJob(env, user, sessionId, jobId, "submitted", result);
  await incrementQuota(env, user);
  const auditDetail = sessionId
    ? { user, sessionId, jobId, payload: { key, job_id: jobId } }
    : { user, jobId, payload: { key, job_id: jobId } };
  await audit(env, "submit_to_pipeline", auditDetail);
  return { ...objectPayload(result), idempotent_replay: false };
}

async function getJobStatus(env: Env, user: AuthUser, jobId: string) {
  const result = await callJobService(env, `/jobs/${encodeURIComponent(jobId)}/status`, "GET");
  await recordJob(env, user, null, jobId, extractStatus(result), result);
  return result;
}

async function getPaperResult(env: Env, user: AuthUser, jobId: string) {
  const result = await callJobService(env, `/jobs/${encodeURIComponent(jobId)}/result`, "GET");
  await recordJob(env, user, null, jobId, extractStatus(result), result);
  await audit(env, "get_paper_result", { user, jobId, payload: { status: extractStatus(result) } });
  return result;
}

async function searchExistingTopics(env: Env, user: AuthUser, query: string) {
  const words = query.toLowerCase().split(/\s+/).filter((word) => word.length > 3);
  const sessions = await listSessions(env, user);
  const matches = sessions
    .map((session) => {
      const topic = String((session as Record<string, unknown>).topic_seed || "").toLowerCase();
      const score = words.filter((word) => topic.includes(word)).length;
      return { ...session, match_score: score };
    })
    .filter((session) => session.match_score >= 2)
    .slice(0, 5);
  return { matches };
}

async function callJobService(env: Env, path: string, method: "GET" | "POST", body?: unknown, extraHeaders: Record<string, string> = {}) {
  const base = env.PAPER_JOB_SERVICE_URL.replace(/\/+$/, "");
  const headers: Record<string, string> = { ...extraHeaders };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (env.PAPER_JOB_SERVICE_TOKEN) headers.Authorization = `Bearer ${env.PAPER_JOB_SERVICE_TOKEN}`;
  const result = await fetchJson(`${base}${path}`, method, body, headers);
  if (!result.ok) throw new Error(`job service ${path} failed with HTTP ${result.status}: ${JSON.stringify(result.payload)}`);
  return result.payload;
}

async function fetchJson(url: string, method: "GET" | "POST", body: unknown, headers: Record<string, string>): Promise<RemoteResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort("timeout"), 30_000);
  try {
    const init: RequestInit = body === undefined
      ? { method, headers, signal: controller.signal }
      : { method, headers, body: JSON.stringify(body), signal: controller.signal };
    const response = await fetch(url, init);
    const payload = await response.json().catch(() => ({ error: "response was not JSON" }));
    return { ok: response.ok, status: response.status, payload };
  } finally {
    clearTimeout(timeout);
  }
}

function extractDecisionValue(decision: unknown, key: string): unknown {
  if (decision && typeof decision === "object" && key in decision) return (decision as Record<string, unknown>)[key];
  return decision;
}

function extractJobId(payload: unknown): string {
  if (payload && typeof payload === "object" && "job_id" in payload) return String((payload as Record<string, unknown>).job_id);
  throw new Error("job service response did not include job_id");
}

function extractStatus(payload: unknown): string {
  if (payload && typeof payload === "object" && "status" in payload) return String((payload as Record<string, unknown>).status);
  return "unknown";
}

function objectPayload(payload: unknown): Record<string, unknown> {
  if (payload && typeof payload === "object" && !Array.isArray(payload)) return payload as Record<string, unknown>;
  return { payload };
}
