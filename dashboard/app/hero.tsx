'use client';
import {useState} from 'react';
import type {Run} from '../lib/contracts';
import {Icon,count,percent} from './ui';

function Gauge({passed,total}:{passed:number;total:number}) {
 const value=total>0?Math.round(passed/total*100):0;
 return <svg className="gauge" viewBox="0 0 240 145" role="img" aria-label={`${value}% visible behavioural agreement`}>
  {Array.from({length:41},(_,i)=>{const angle=Math.PI+i*Math.PI/40;return <line key={i} x1={120+85*Math.cos(angle)} y1={110+85*Math.sin(angle)} x2={120+99*Math.cos(angle)} y2={110+99*Math.sin(angle)} stroke={total>0&&i<=value/100*40?'#ef4d23':'#e5e5e5'} strokeWidth="3" strokeLinecap="round"/>;})}
  <text x="120" y="100" textAnchor="middle">{total>0?`${value}%`:'N/A'}</text><text className="gauge-caption" x="120" y="124" textAnchor="middle">behavioural agreement</text>
 </svg>;
}

export default function Hero({run:r}:{run:Run}) {
 const [menuOpen,setMenuOpen]=useState(false);
 const links=[['#overview','Overview'],['#pipeline','Pipeline'],['#verification','Verification'],['#evidence','Evidence']];
 return <section className="hero" id="overview" aria-labelledby="hero-title">
  <div className="hero-landscape" aria-hidden="true"><div className="landscape-orbit"/><div className="landscape-grid"/></div>
  <nav className="hero-nav" aria-label="Main navigation">
   <a href="#overview" className="hero-brand" aria-label="Necromancer home"><svg viewBox="0 0 32 32" aria-hidden="true">{Array.from({length:8},(_,i)=><circle key={i} cx={16+10*Math.cos(i*Math.PI/4)} cy={16+10*Math.sin(i*Math.PI/4)} r="3.5"/>)}<circle cx="16" cy="16" r="3.5"/></svg><span>necromancer<span className="brand-version"> / 01</span></span></a>
   <div id="hero-links" className={`hero-links${menuOpen?' is-open':''}`}>{links.map(([href,label])=><a key={href} href={href} onClick={()=>setMenuOpen(false)}>{label}</a>)}</div>
   <a className="nav-export" href="/api/report">Export evidence <Icon name="download"/></a>
   <button className="menu-toggle" aria-label={menuOpen?'Close navigation':'Open navigation'} aria-expanded={menuOpen} aria-controls="hero-links" onClick={()=>setMenuOpen(v=>!v)}>{menuOpen?'✕':'☰'}</button>
  </nav>
  <div className="hero-copy"><span className="hero-badge"><Icon name="bolt"/> A new life for legacy code</span><h1 id="hero-title">Old code.<br/>New life. <em>Same soul.</em></h1><p>Modernize the runtime. Preserve the behaviour.<br/>Every repair backed by evidence you can inspect.</p><div className="hero-actions"><a className="button dark-button" href="#pipeline">Explore the resurrection <Icon name="bolt"/></a><a className="hero-secondary" href="#comparison">Inspect the patch</a></div><div className="hero-caption">PHP 5.6 <span>/</span> PHP 8.3 <span>/</span> AI-assisted repair</div></div>
  <div className="hero-preview"><div className="preview-heading"><span><span className="preview-dot"/> The latest resurrection</span><span>RECORDED SNAPSHOT</span></div><div className="preview-cards">
   <article className="preview-card agreement-card"><div className="preview-card-label">Visible verification <Icon name="shield"/></div><div className="preview-value">{count(r.visible)} <span>scenarios agree</span></div><Gauge passed={r.visible?.passed??0} total={r.visible?.total??0}/><div className="preview-card-foot">{percent(r.visible)} of the recorded visible suite</div></article>
   <article className="preview-card migration-card"><div className="preview-card-label">The migration <Icon name="code"/></div><div className="runtime-path"><span>PHP <strong>5.6</strong><small>Original runtime</small></span><span className="migration-divider">/</span><span>PHP <strong>8.3</strong><small>Modern runtime</small></span></div><div className="migration-result"><Icon name="bolt"/><span>{r.initialRegressions??'Unknown'} initial regressions<br/><strong>{r.attempts.length} recorded repair attempts</strong></span></div><div className="preview-card-foot">Provider <strong>{r.provider}</strong></div></article>
   <article className="preview-card proof-card"><div className="preview-card-label">Proof, preserved <Icon name="file"/></div><div className="proof-mark"><Icon name="shield"/></div><h2>{r.fixtureIntegrity.status==='passed'?'Evidence intact':'Evidence integrity'}</h2><p>{r.fixtureIntegrity.checked} protected files checked at export.<br/>Held-out tests: {count(r.heldout)}.</p><a href="#evidence">Inspect integrity evidence</a></article>
  </div></div>
  <div className="hero-bottom"><span>RESURRECTION WITH PROOF</span><span>Built to inspect. Designed to earn trust.</span></div>
 </section>;
}
