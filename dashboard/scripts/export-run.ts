import { writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { collectRun } from '../lib/data.ts';
const run=await collectRun(path.resolve(process.cwd(),'..'));
await mkdir('recorded',{recursive:true});
await writeFile('recorded/run.v1.json',JSON.stringify(run,null,2)+'\n');
console.log(`Exported schema v1: provider=${run.provider}, model=${run.model}, visible=${run.visible?.passed}/${run.visible?.total}, heldout=${run.heldout?.passed}/${run.heldout?.total}, integrity=${run.fixtureIntegrity.status}`);
