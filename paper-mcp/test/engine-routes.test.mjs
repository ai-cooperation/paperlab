import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

const outDir = mkdtempSync(join(tmpdir(), "paper-mcp-routes-"));
execFileSync(
  process.execPath,
  [
    "node_modules/typescript/bin/tsc",
    "--target",
    "ES2022",
    "--module",
    "NodeNext",
    "--moduleResolution",
    "NodeNext",
    "--outDir",
    outDir,
    "src/engineRoutes.ts"
  ],
  { cwd: new URL("..", import.meta.url), stdio: "inherit" }
);

const routes = await import(join(outDir, "engineRoutes.js"));

test("legacy engine endpoint keeps old paper_driver paths", () => {
  const config = routes.resolveEngineRoutes("/jobs");
  assert.equal(config.engine, "legacy");
  assert.equal(config.submit, "/jobs");
  assert.equal(config.viabilityProbe, "/jobs/viability-probe");
  assert.equal(config.status("job-1"), "/jobs/job-1/status");
  assert.equal(config.result("job-1"), "/jobs/job-1/result");
  assert.equal(config.requiresViabilityLock, false);
});

test("v2 engine endpoint routes submit and status while reusing canonical viability probe", () => {
  const config = routes.resolveEngineRoutes("/v2/jobs");
  assert.equal(config.engine, "v2");
  assert.equal(config.submit, "/v2/jobs");
  assert.equal(config.viabilityProbe, "/jobs/viability-probe");
  assert.equal(config.status("v2_abc"), "/v2/jobs/v2_abc/status");
  assert.equal(config.result("v2_abc"), "/v2/jobs/v2_abc/status");
  assert.equal(config.requiresViabilityLock, true);
});

test("v3 engine endpoint routes submit, viability, and result projection to v3", () => {
  const config = routes.resolveEngineRoutes("/v3/jobs/");
  assert.equal(config.engine, "v3");
  assert.equal(config.submit, "/v3/jobs");
  assert.equal(config.viabilityProbe, "/v3/jobs/viability-probe");
  assert.equal(config.status("v3_abc"), "/v3/jobs/v3_abc/status");
  assert.equal(config.result("v3_abc"), "/v3/jobs/v3_abc/status");
  assert.equal(config.artifact("v3_abc", "references.bib"), "/v3/jobs/v3_abc/artifact/references.bib");
  assert.equal(config.requiresViabilityLock, true);
});

test("engine endpoint must be a path rooted at the a-side service", () => {
  assert.throws(() => routes.resolveEngineRoutes("https://example.com/v3/jobs"), /must be a path/);
  assert.throws(() => routes.resolveEngineRoutes("v3/jobs"), /must be a path/);
});
