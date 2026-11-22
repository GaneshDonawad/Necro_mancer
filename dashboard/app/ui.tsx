import type { ReactNode } from 'react';
import type { Counts } from '../lib/contracts';
export const count=(c:Counts|null)=>c?`${c.passed}/${c.total}`:'—';
export const percent=(c:Counts|null)=>c?`${Math.round(c.passed/c.total*100)}%`:'Unavailable';
export const time=(t:string|null)=>t?new Date(t).toISOString().replace('T',' · ').replace('Z',' UTC'):'Timestamp not recorded';
export function Icon({name='grid'}:{name?:string}) { const paths:Record<string,string>={grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',shield:'M12 3l8 3v6c0 5-8 9-8 9S4 17 4 12V6z M8 12l3 3 5-6',code:'M8 6l-6 6 6 6 M16 6l6 6-6 6 M14 3l-4 18',clock:'M12 8v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0',file:'M6 3h8l4 4v14H6z M14 3v5h4 M9 12h6 M9 16h6',bolt:'M13 2L4 14h7l-1 8 10-13h-7z',check:'M5 12l4 4L19 6',download:'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5'};return <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]||paths.grid}/></svg>; }
export function Badge({children,tone='green'}:{children:ReactNode;tone?:string}) {return <span className={`badge ${tone}`}>{children}</span>}
export function Code({value,diff=false}:{value:string|null;diff?:boolean}) {return <pre className="code"><code>{value?value.split('\n').map((line,i)=><span className={diff?(line.startsWith('+')&&!line.startsWith('+++')?'added':line.startsWith('-')&&!line.startsWith('---')?'removed':''):''} key={i}><i>{i+1}</i>{line||' '}</span>):'Not retained in the report.'}</code></pre>}
