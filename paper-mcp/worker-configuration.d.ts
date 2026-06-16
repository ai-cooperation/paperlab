// Regenerate with `npm run generate-types` after editing wrangler.jsonc.
interface Env {
  DB: D1Database;
  ARTIFACTS: R2Bucket;
  PAPER_JOB_SERVICE_URL: string;
  PAPER_JOB_SERVICE_TOKEN?: string;
  // A/B engine routing: "/jobs" (old paper_driver, default) | "/v2/jobs" (new engine).
  // The viability-lock submit gate is enforced only for the /v2 path.
  A_ENGINE_ENDPOINT?: string;
  PAPERLAB_ISSUER_SECRET?: string;
  DEEP_RESEARCH_ENDPOINT?: string;
  DEFAULT_FREE_QUOTA: string;
  DEFAULT_VIP_QUOTA: string;
  TOKEN_TTL_DAYS: string;
}
