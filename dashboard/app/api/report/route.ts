import { loadRun } from '../../../lib/data';
export async function GET() {return Response.json(await loadRun(),{headers:{'Content-Disposition':'attachment; filename="necromancer-run.v1.json"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});}
