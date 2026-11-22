import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {strict as assert} from 'node:assert';
import path from 'node:path';
import {collectRun,projectSnapshot} from '../lib/data.ts';
const root=path.resolve('..');
await mkdir(path.join(root,'.tmp'),{recursive:true});
const temporary=await mkdtemp(path.join(root,'.tmp','dashboard-test-'));
const test=async(name:string,fn:()=>void|Promise<void>)=>{await fn();console.log('PASS '+name);};
try {
 await test('real report metrics and patch match original JSON',async()=>{
  const r=await collectRun(root),raw=JSON.parse(await readFile(path.join(root,'repair-report.json'),'utf8'));
  assert.equal(r.provider,raw.llm_provider);assert.equal(r.model,raw.llm_model);assert.equal(r.patch,raw.applied_patch);assert.equal(r.initialRegressions,raw.initial_regressions);
  for(const [file,c] of [['verification-report.json',r.visible],['heldout-summary.json',r.heldout]] as const){const source=JSON.parse(await readFile(path.join(root,file),'utf8'));assert.equal(c?.passed,source.passed);assert.equal(c?.total,source.total);}
  assert.equal(r.fixtureIntegrity.status,'passed');assert.equal(r.fixtureIntegrity.checked,8);
  assert(!/guest-edge|member-abc|fixtures\/heldout|api_key/i.test(JSON.stringify(r)));
 });
 await test('missing reports yield unavailable metrics',async()=>{const r=await collectRun(temporary);assert.equal(r.visible,null);assert.equal(r.heldout,null);assert.equal(r.patch,null);assert.equal(r.fixtureIntegrity.status,'unavailable');});
 await mkdir(path.join(temporary,'fixtures/visible'),{recursive:true});await mkdir(path.join(temporary,'fixtures/heldout'),{recursive:true});
 const files={'allowlist.yml':'{}','fixtures/scenarios.json':'{}','fixtures/visible/example.json':JSON.stringify({id:'example',expected:{ok:true}}),'fixtures/heldout/private.json':'PRIVATE_EXPECTED_SENTINEL'};
 for(const [name,value]of Object.entries(files))await writeFile(path.join(temporary,name),value);
 const manifest=Object.entries(files).map(([name,value])=>createHash('sha256').update(value).digest('hex')+'  '+name).join('\n')+'\n';
 await writeFile(path.join(temporary,'fixtures/manifest.sha256'),manifest);
 await writeFile(path.join(temporary,'repair-report.json'),JSON.stringify({llm_provider:'mock',llm_model:'test',api_key:'PRIVATE_KEY_SENTINEL',notes:['PRIVATE_NOTES_SENTINEL'],heldout_verification:{passed:1,total:1,results:['PRIVATE_EXPECTED_SENTINEL']}}));
 await writeFile(path.join(temporary,'heldout-summary.json'),JSON.stringify({passed:1,total:1,results:['PRIVATE_EXPECTED_SENTINEL']}));
 await test('private details and arbitrary report fields never serialize',async()=>{const r=await collectRun(temporary);assert.equal(r.fixtureIntegrity.status,'passed');assert(!/PRIVATE_|private.json|api_key|notes/i.test(JSON.stringify(r)));assert.deepEqual(r.heldout,{passed:1,total:1});});
 await test('modified evidence fails SHA-256 integrity',async()=>{await writeFile(path.join(temporary,'fixtures/heldout/private.json'),'tampered');assert.equal((await collectRun(temporary)).fixtureIntegrity.status,'failed');});
 await test('traversal manifest entry is rejected',async()=>{await writeFile(path.join(temporary,'fixtures/manifest.sha256'),manifest+'0'.repeat(64)+'  ../.env\n');assert.equal((await collectRun(temporary)).fixtureIntegrity.status,'failed');});
 await test('invalid and empty snapshot schemas yield unavailable state',()=>{assert.equal(projectSnapshot({schemaVersion:999}).status,'UNAVAILABLE');assert.equal(projectSnapshot({schemaVersion:1,mode:'Recorded Verification Results'}).visible,null);});
 await test('snapshot API projection rejects unknown secret fields',async()=>{const r=await collectRun(root);const result=projectSnapshot({...r,api_key:'PRIVATE_KEY_SENTINEL',heldout:{passed:2,total:2,results:['PRIVATE_EXPECTED_SENTINEL']}});assert(!JSON.stringify(result).includes('PRIVATE_'));assert.equal(result.visible?.passed,4);});
 await test('invalid counts cannot claim success',async()=>{const r=await collectRun(root);assert.equal(projectSnapshot({...r,visible:{passed:99,total:2}}).visible,null);});
} finally {
 // The only recursive deletion is a verified, newly created test directory.
 if(path.dirname(temporary)!==path.join(root,'.tmp')||!path.basename(temporary).startsWith('dashboard-test-'))throw Error('Unsafe cleanup target');
 await rm(temporary,{recursive:true,force:true});
}
