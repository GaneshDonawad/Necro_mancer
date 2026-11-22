export type Counts = { passed: number; total: number };
export type Scenario = { id: string; pass: boolean | null; expected: Record<string, unknown> | null; differences: {path: string; expected: unknown; actual: unknown}[] };
export type Attempt = { number: number; timestamp: string | null; status: string; validation: boolean | null; visible: Counts | null; duration: number | null };
export type Run = {
  schemaVersion: 1; exportedAt: string; mode: 'Recorded Verification Results';
  runId: string | null; timestamp: string | null; provider: string; model: string;
  status: string; initialRegressions: number | null; visible: Counts | null; heldout: Counts | null;
  auditIntegrity: boolean | null; fixtureIntegrity: {status: 'passed' | 'failed' | 'unavailable'; checked: number; manifestSha256: string | null};
  attempts: Attempt[]; patch: string | null; scenarios: Scenario[]; warnings: string[];
};
