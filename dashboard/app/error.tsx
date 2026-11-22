'use client';
export default function ErrorPage({reset}:{reset:()=>void}) { return <main className="loading"><h1>Evidence unavailable</h1><p>The report could not be loaded.</p><button onClick={reset}>Try again</button></main>; }
