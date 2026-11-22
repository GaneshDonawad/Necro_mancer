// Node-only report projection. Never import into a client component.
import { readFile, readdir, lstat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import type { Run, Counts } from './contracts.ts';
type Obj = Record<string, unknown>;
const object = (v: unknown): Obj => v && typeof v === 'object' && !Array.isArray(v) ? v as Obj : {};
const integer = (v: unknown): number | null => Number.isSafeInteger(v) && (v as number) >= 0 ? v as number : null;
const bool = (v: unknown) => typeof v === 'boolean' ? v : null;
const safe = (v: unknown, fallback = 'Unavailable') => typeof v === 'string' && /^[a-zA-Z0-9_./:+ -]{1,120}$/.test(v) && publicValue(v) === v ? v : fallback;
const fieldPath = (v: unknown) => typeof v === 'string' && /^[\w.$\[\]-]{1,200}$/.test(v) ? v : 'Unavailable';
const patchValue = (v: unknown): string | null => typeof v==='string' && v.length<20000 && /^--- (?:a\/)?modern-app\/src\/invoice\.php\n\+\+\+ (?:b\/)?modern-app\/src\/invoice\.php\n/.test(v) && publicValue(v)===v ? v : null;
const date = (v: unknown) => typeof v === 'string' && /^\d{4}-\d\d-\d\dT[\d:.+Z-]+$/.test(v) && Number.isFinite(Date.parse(v)) ? v : null;
const counts = (v: unknown): Counts | null => { const o = object(v); const p = integer(o.passed), t = integer(o.total); return p !== null && t !== null && t > 0 && p <= t ? {passed:p,total:t} : null; };
async function read(root: string, rel: string) { const file = path.join(root, rel); if ((await lstat(file)).isSymbolicLink()) throw Error('Symlink'); return readFile(file,'utf8'); }
async function json(root: string, rel: string): Promise<Obj> { try { return object(JSON.parse(await read(root,rel))); } catch { return {}; } }
const hash = (s: string | Buffer) => createHash('sha256').update(s).digest('hex');
function publicValue(v: unknown): unknown {
  if (v === null || typeof v === 'boolean' || typeof v === 'number') return v;
  if (typeof v === 'string') return v.slice(0,20000).replace(/AIza[\w-]+|(?:sk-|gsk_)[\w-]{12,}|(?:api[_-]?key|token|password|secret)\s*[:=]\s*\S+/gi,'[REDACTED]');
  if (Array.isArray(v)) return v.slice(0,50).map(publicValue);
  return Object.fromEntries(Object.entries(object(v)).slice(0,50).filter(([k])=> !/key|secret|token|password/i.test(k)).map(([k,v])=>[k,publicValue(v)]));
}
export async function collectRun(root: string): Promise<Run> {
  const [r,v,h] = await Promise.all([json(root,'repair-report.json'),json(root,'verification-report.json'),json(root,'heldout-summary.json')]);
  const warnings: string[] = [];
  if (!r.run_id) warnings.push('Repair audit is unavailable. No repair success can be established.');
  const provider = safe(r.llm_provider);
  if (provider === 'mock') warnings.push('Mock provider recorded. This audit does not establish a live Gemini API repair.');
  const rawAttempts = Array.isArray(r.attempts) ? r.attempts : [];
  const attempts = rawAttempts.map(x => { const a = object(x); return {number: integer(a.attempt_number) ?? 0, timestamp:date(a.timestamp), status:safe(a.status), validation:bool(a.validation_passed), visible:counts({passed:a.visible_tests_passed,total:a.visible_tests_total}),duration:typeof a.duration_seconds === 'number' && a.duration_seconds >= 0 ? a.duration_seconds : null}; });
  let fixtureIntegrity: Run['fixtureIntegrity'] = {status:'unavailable',checked:0,manifestSha256:null};
  try {
    const manifest = await read(root,'fixtures/manifest.sha256');
    const [visibleFiles,hiddenFiles] = await Promise.all([readdir(path.join(root,'fixtures/visible')),readdir(path.join(root,'fixtures/heldout'))]);
    const allowed = new Set(['allowlist.yml','fixtures/scenarios.json',...visibleFiles.filter(n=>n.endsWith('.json')).map(n=>'fixtures/visible/'+n),...hiddenFiles.filter(n=>n.endsWith('.json')).map(n=>'fixtures/heldout/'+n)]);
    const rows = manifest.trim().split(/\r?\n/).map(row=>row.split('  '));
    const seen = new Set<string>();
    let valid = rows.length === allowed.size;
    for (const [digest,rel] of rows) {
      if (!allowed.has(rel) || seen.has(rel) || !/^[a-f0-9]{64}$/.test(digest)) {valid=false;continue;}
      seen.add(rel);
      // Private fixtures are hashed only, never serialized.
      const file = path.join(root,rel);
      if ((await lstat(file)).isSymbolicLink() || hash(await readFile(file)) !== digest) valid=false;
    }
    fixtureIntegrity={status:valid?'passed':'failed',checked:seen.size,manifestSha256:hash(manifest)};
  } catch { warnings.push('Current fixture integrity could not be checked.'); }
  const results = Array.isArray(v.results) ? v.results : [];
  const scenarios: Run['scenarios'] = [];
  try {
    const names = (await readdir(path.join(root,'fixtures/visible'))).filter(n=>/^[\w-]+\.json$/.test(n)).sort();
    for (const name of names) {
      const f = await json(root,'fixtures/visible/'+name);
      const result = object(results.find(x=>object(x).scenario===f.id));
      scenarios.push({id:safe(f.id,name.replace('.json','')),pass:bool(result.pass),expected:f.expected ? object(publicValue(f.expected)) : null,differences:Array.isArray(result.differences)?result.differences.map(x=>{const d=object(x);return {path:fieldPath(d.path),expected:publicValue(d.expected),actual:publicValue(d.actual)};}):[]});
    }
  } catch { warnings.push('Visible golden-master fixtures are unavailable.'); }
  let patch = patchValue(r.applied_patch);
  if (patch?.includes('[REDACTED]')) patch=null;
  if (patch) {
    try { const modern=await read(root,'modern-app/src/invoice.php'); const added=patch.split('\n').filter(l=>l.startsWith('+')&&!l.startsWith('+++')).map(l=>l.slice(1)); if (added.some(l=>!modern.includes(l))) warnings.push('Current modern source differs from the recorded patch. The comparison shows the audit artifact, not the current file.'); } catch { warnings.push('Current modern source is unavailable for patch comparison.'); }
  }
  const visible=counts(v),heldout=counts(h),auditHeldout=counts(r.heldout_verification);
  if (heldout && auditHeldout && (heldout.passed!==auditHeldout.passed||heldout.total!==auditHeldout.total)) warnings.push('Held-out summary disagrees with repair audit.');
  if (visible && (results.length!==visible.total || results.filter(x=>object(x).pass===true).length!==visible.passed)) warnings.push('Visible report totals disagree with scenario results.');
  const last=attempts.at(-1)?.visible;
  if (visible && last && (visible.passed!==last.passed||visible.total!==last.total)) warnings.push('Visible summary disagrees with repair audit.');
  warnings.push('Standalone verification summaries have no run ID or timestamp; their association with this repair cannot be independently established.');
  return {schemaVersion:1,exportedAt:new Date().toISOString(),mode:'Recorded Verification Results',runId:typeof r.run_id==='string'&&/^[a-f0-9-]{36}$/.test(r.run_id)?r.run_id:null,timestamp:date(r.timestamp),provider,model:safe(r.llm_model),status:safe(r.final_status),initialRegressions:integer(r.initial_regressions),visible,heldout,auditIntegrity:bool(r.evidence_integrity_verified),fixtureIntegrity,attempts,patch,scenarios,warnings};
}
export async function loadRun(): Promise<Run> {
  const snapshot=await json(process.cwd(),'recorded/run.v1.json');
  return projectSnapshot(snapshot);
}
export function projectSnapshot(s: Obj): Run {
  const empty: Run={schemaVersion:1,exportedAt:new Date().toISOString(),mode:'Recorded Verification Results',runId:null,timestamp:null,provider:'Unavailable',model:'Unavailable',status:'UNAVAILABLE',initialRegressions:null,visible:null,heldout:null,auditIntegrity:null,fixtureIntegrity:{status:'unavailable',checked:0,manifestSha256:null},attempts:[],patch:null,scenarios:[],warnings:['A valid versioned export is unavailable. Run npm run export:run locally, then rebuild.']};
  if(s.schemaVersion!==1||s.mode!==empty.mode||!Array.isArray(s.scenarios)||!Array.isArray(s.attempts)||!Array.isArray(s.warnings)) return empty;
  const f=object(s.fixtureIntegrity);
  const patch=patchValue(s.patch);
  // Re-project even the saved snapshot: unknown fields can never leak through the API.
  return {...empty,exportedAt:date(s.exportedAt)??empty.exportedAt,runId:typeof s.runId==='string'&&/^[a-f0-9-]{36}$/.test(s.runId)?s.runId:null,timestamp:date(s.timestamp),provider:safe(s.provider),model:safe(s.model),status:safe(s.status),initialRegressions:integer(s.initialRegressions),visible:counts(s.visible),heldout:counts(s.heldout),auditIntegrity:bool(s.auditIntegrity),fixtureIntegrity:{status:f.status==='passed'||f.status==='failed'?f.status:'unavailable',checked:integer(f.checked)??0,manifestSha256:typeof f.manifestSha256==='string'&&/^[a-f0-9]{64}$/.test(f.manifestSha256)?f.manifestSha256:null},patch,
    attempts:s.attempts.map(x=>{const a=object(x);return {number:integer(a.number)??0,timestamp:date(a.timestamp),status:safe(a.status),validation:bool(a.validation),visible:counts(a.visible),duration:typeof a.duration==='number'&&Number.isFinite(a.duration)&&a.duration>=0?a.duration:null};}),
    scenarios:s.scenarios.map(x=>{const a=object(x);return {id:safe(a.id),pass:bool(a.pass),expected:a.expected?object(publicValue(a.expected)):null,differences:Array.isArray(a.differences)?a.differences.map(x=>{const d=object(x);return {path:typeof d.path==='string'?String(publicValue(d.path)).slice(0,200):'Unavailable',expected:publicValue(d.expected),actual:publicValue(d.actual)};}):[]};}),
    warnings:s.warnings.filter((x): x is string=>typeof x==='string').map(x=>String(publicValue(x))),
  };
}
