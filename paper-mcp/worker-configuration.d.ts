// Regenerate with `npm run generate-types` after editing wrangler.jsonc.
interface Env {
  DB: D1Database;
  ARTIFACTS: R2Bucket;
  PAPER_JOB_SERVICE_URL: string;
  PAPER_JOB_SERVICE_TOKEN?: string;
  // A/B engine routing: "/jobs" (old paper_driver) | "/v2/jobs" | "/v3/jobs".
  // The viability-lock submit gate is enforced for Hermes engines (/v2 and /v3).
  A_ENGINE_ENDPOINT?: string;
  PAPERLAB_ISSUER_SECRET?: string;
  DEEP_RESEARCH_ENDPOINT?: string;
  DEFAULT_FREE_QUOTA: string;
  DEFAULT_VIP_QUOTA: string;
  TOKEN_TTL_DAYS: string;
}
