export type EngineName = "legacy" | "v2" | "v3";

export type EngineRoutes = {
  engine: EngineName;
  submit: string;
  dryRun: string;
  dataProbe: string;
  viabilityProbe: string;
  requiresViabilityLock: boolean;
  status: (jobId: string) => string;
  result: (jobId: string) => string;
  artifact: (jobId: string, artifactId: string) => string;
};

export function resolveEngineRoutes(endpoint?: string | null): EngineRoutes {
  const submit = normalizeEndpoint(endpoint);
  const engine = engineName(submit);
  const statusBase = engine === "legacy" ? "/jobs" : `/${engine}/jobs`;

  return {
    engine,
    submit,
    dryRun: "/jobs/dry-run",
    dataProbe: "/jobs/probe-data-source",
    viabilityProbe: engine === "v3" ? "/v3/jobs/viability-probe" : "/jobs/viability-probe",
    requiresViabilityLock: engine !== "legacy",
    status: (jobId: string) => `${statusBase}/${encodeURIComponent(jobId)}/status`,
    result: (jobId: string) => {
      if (engine === "legacy") return `/jobs/${encodeURIComponent(jobId)}/result`;
      return `${statusBase}/${encodeURIComponent(jobId)}/status`;
    },
    artifact: (jobId: string, artifactId: string) =>
      `${statusBase}/${encodeURIComponent(jobId)}/artifact/${encodeArtifactId(artifactId)}`
  };
}

function normalizeEndpoint(endpoint?: string | null): string {
  const value = (endpoint || "/jobs").trim();
  if (!value.startsWith("/") || value.startsWith("//")) {
    throw new Error("A_ENGINE_ENDPOINT must be a path rooted at the a-side service");
  }
  const normalized = value.replace(/\/+$/, "");
  return normalized || "/jobs";
}

function engineName(endpoint: string): EngineName {
  if (endpoint === "/v3/jobs") return "v3";
  if (endpoint === "/v2/jobs") return "v2";
  if (endpoint === "/jobs") return "legacy";
  throw new Error(`unsupported A_ENGINE_ENDPOINT: ${endpoint}`);
}

function encodeArtifactId(artifactId: string): string {
  return artifactId.split("/").map((part) => encodeURIComponent(part)).join("/");
}
