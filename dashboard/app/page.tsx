import { loadRun } from '../lib/data';
import Dashboard from './dashboard';
export default async function Home() { return <Dashboard run={await loadRun()} />; }
