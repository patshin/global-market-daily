"use strict";
const DATA_URL="data/trends/rolling-30d.json";
const NS="http://www.w3.org/2000/svg";
const q=s=>document.querySelector(s);
function e(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n}
function svg(tag,attrs={}){const n=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,String(v)));return n}
function modeBadge(mode){
  const label=mode==="native_daily"?"原生日报":mode==="verified_event"?"官方事件":"市场重建";
  const cls=mode==="native_daily"?"native":mode==="verified_event"?"verified":"";
  return e("span",`source-mode-badge ${cls}`,label);
}
function themeLabel(data,id){return data.themes?.[id]?.label||id||"—"}
function categoryLabel(data,id){return data.category_labels?.[id]||id}
function renderHero(data){
  const meta=q("#lens-hero-meta");
  [["Window",`${data.window_start} → ${data.window_end}`],["Sessions",data.coverage.market_sessions],["Native Daily",data.coverage.native_daily_days],["Verified Event Days",data.coverage.verified_event_days||0]].forEach(([l,v])=>{const x=e("div");x.append(e("span","",l),e("strong","",v));meta.append(x)});
  const current=data.days.at(-1),top=data.persistent_themes?.[0],transition=data.regime_transitions?.at(-1),strip=q("#lens-summary-strip");
  [["Current Regime",current?.regime_label],["Dominant Theme",themeLabel(data,current?.dominant_theme_id)],["Most Persistent",top?.theme_label],["Last Regime Shift",transition?`${transition.date} · ${transition.from} → ${transition.to}`:"No change in window"],["Historical Series",data.coverage.historical_series_start]].forEach(([l,v])=>{const x=e("div");x.append(e("span","",l),e("strong","",v||"—"));strip.append(x)});
  q("#lens-footer").textContent=`As of ${data.as_of}`;
}
function appendSource(target,c){
  if(!(c.source_name||c.source_url))return;
  const source=e("div","lens-catalyst-source");source.append(modeBadge(c.source_mode));
  if(c.source_url){const a=e("a","",c.source_name||c.source_title||"Primary source");a.href=c.source_url;a.target="_blank";a.rel="noopener noreferrer";source.append(a)}
  else source.append(document.createTextNode(c.source_name||c.source_title));
  target.append(source);
}
function renderDayDetail(data,day,target){
  target.replaceChildren();
  target.append(e("div","lens-detail__title",`${day.date} · ${day.regime_label} · ${themeLabel(data,day.dominant_theme_id)}`));
  const ol=e("ol");
  day.catalysts.forEach(c=>{const li=e("li");const line=e("div","lens-detail__catalyst-line");line.append(e("strong","",`${c.rank}. ${c.title}`),modeBadge(c.source_mode));li.append(line,e("p","",c.evidence));appendSource(li,c);ol.append(li)});
  target.append(ol);
}
function renderRibbon(data){const root=q("#lens-full-ribbon");root.style.setProperty("--cols",data.days.length);data.days.forEach(day=>{const b=e("button",`${day.regime_code} ${day.source_mode==="native_daily"?"native":""}`,day.date.slice(5).replace("-","/"));b.type="button";b.title=`${day.date} · ${day.regime_label}`;b.onclick=()=>renderDayDetail(data,day,q("#regime-detail"));root.append(b)});renderDayDetail(data,data.days.at(-1),q("#regime-detail"))}
function renderSignals(data){const root=q("#signal-matrix");root.style.setProperty("--cols",data.days.length);root.append(e("div","signal-matrix__rowlabel","Signal / Date"));data.days.forEach(d=>root.append(e("div","",d.date.slice(5))));const rows=[['growth','Growth Proxy'],['inflation','Inflation'],['rates','Rates'],['earnings','Earnings / Growth'],['liquidity','Liquidity'],['geopolitics','Geopolitics']];rows.forEach(([key,label])=>{root.append(e("div","signal-matrix__rowlabel",label));data.days.forEach(d=>{const s=d.signals?.[key]||'→',cls=s==='↑'?'signal-cell--up':s==='↓'?'signal-cell--down':'signal-cell--flat';root.append(e("div",cls,s))})})}
function biasColor(bias){return bias==='risk_off'?'#8b1e2d':bias==='risk_on'?'#245f43':'#817c73'}
function renderCatalystDetail(data,c,day){
  const target=q("#catalyst-detail");target.replaceChildren();
  target.append(e("div","lens-detail__title",`${day.date} · Rank ${c.rank} · ${c.title}`));
  const m=e("div","lens-detail__meta");m.append(modeBadge(c.source_mode),document.createTextNode(` · ${themeLabel(data,c.theme_id)} · ${c.importance||'★★★'}`));
  target.append(m,e("p","",c.evidence),e("p","",`Transmission: ${c.transmission||'—'}`));
  if(c.confirmation)target.append(e("p","",`Confirmation: ${c.confirmation}`));
  if(c.invalidation)target.append(e("p","",`Invalidation: ${c.invalidation}`));
  appendSource(target,c);
}
function renderCatalystMap(data){
  const categories=Object.keys(data.category_labels),dates=data.days.map(d=>d.date),el=q("#catalyst-map"),W=1180,H=420,left=190,right=22,top=24,bottom=48;
  el.setAttribute('viewBox',`0 0 ${W} ${H}`);const x=i=>left+(W-left-right)*(dates.length===1?0:i/(dates.length-1)),y=i=>top+(H-top-bottom)*(i/(categories.length-1));
  const counts=Object.fromEntries(categories.map(c=>[c,0]));data.days.forEach(day=>day.catalysts.forEach(c=>{if(c.category in counts)counts[c.category]+=1}));
  categories.forEach((cat,i)=>{const yy=y(i);el.append(svg('line',{x1:left,y1:yy,x2:W-right,y2:yy,stroke:'#d4cec3','stroke-width':1}));const txt=svg('text',{x:4,y:yy+4,class:'catalyst-axis-label'});txt.textContent=categoryLabel(data,cat);el.append(txt);if(counts[cat]===0){const empty=svg('text',{x:W-right,y:yy+4,class:'catalyst-empty-label','text-anchor':'end'});empty.textContent='过去30日无 Top 3 事件';el.append(empty)}});
  dates.forEach((d,i)=>{if(i%3!==0&&i!==dates.length-1)return;const txt=svg('text',{x:x(i),y:H-15,class:'catalyst-date-label','text-anchor':'middle'});txt.textContent=d.slice(5);el.append(txt)});
  data.days.forEach((day,di)=>day.catalysts.forEach(c=>{const ci=categories.indexOf(c.category);if(ci<0)return;const offset=(Number(c.rank||2)-2)*9,cy=y(ci)+offset;const circle=svg('circle',{cx:x(di),cy,r:5+(c.importance_level-3)*3,fill:biasColor(c.market_bias),class:`catalyst-dot ${c.source_mode==='native_daily'?'native':c.source_mode==='verified_event'?'verified':''}`,tabindex:0,role:'button','aria-label':`${day.date} 第${c.rank}位 ${c.title}`});const activate=()=>renderCatalystDetail(data,c,day);circle.addEventListener('click',activate);circle.addEventListener('focus',activate);circle.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();activate()}});const title=svg('title');title.textContent=`${day.date} · #${c.rank} ${c.title}`;circle.append(title);el.append(circle);const rank=svg('text',{x:x(di),y:cy+3,'text-anchor':'middle','font-size':8,fill:'#fff','pointer-events':'none'});rank.textContent=c.rank;el.append(rank)}));
  const last=data.days.at(-1);if(last?.catalysts?.[0])renderCatalystDetail(data,last.catalysts[0],last);renderMobileCatalysts(data);
}
function renderMobileCatalysts(data){const root=q("#mobile-catalyst-weeks"),groups=[];for(let i=0;i<data.days.length;i+=5)groups.push(data.days.slice(i,i+5));groups.forEach((g,idx)=>{const w=e("section","mobile-week");w.append(e("h3","",`Week ${String(idx+1).padStart(2,'0')} · ${g[0].date.slice(5)} → ${g.at(-1).date.slice(5)}`));g.forEach(day=>day.catalysts.forEach(c=>{const card=e("button","mobile-catalyst");card.type="button";card.append(e("strong","",`${day.date.slice(5)} · #${c.rank} ${c.title}`),e("span","",`${themeLabel(data,c.theme_id)} · ${c.evidence}`));card.onclick=()=>renderCatalystDetail(data,c,day);w.append(card)}));root.append(w)})}
function renderThemes(data){const t=q("#theme-table"),head=e("thead"),hr=e("tr");['Theme','State','Days in Top 3','Best Rank','First Seen','Last Seen','Source'].forEach(x=>hr.append(e("th","",x)));head.append(hr);const body=e("tbody"),labels={native_daily:'Native',verified_event:'Verified Event',objective_market_reconstruction:'Reconstructed'};(data.persistent_themes||[]).forEach(x=>{const r=e("tr"),modes=(x.source_modes||[]).map(m=>labels[m]||m).join(' + '),cells=[x.theme_label,x.state,x.days_in_top3,`#${x.best_rank}`,x.first_seen,x.last_seen,modes];cells.forEach((v,i)=>r.append(e("td",i===1?'theme-state':'',v)));body.append(r)});t.replaceChildren(head,body)}
function sparkPath(points,w,h,pad=6){const vals=points.map(p=>p.value),min=Math.min(...vals),max=Math.max(...vals),range=max-min||1;return points.map((p,i)=>`${i?'L':'M'} ${pad+(w-pad*2)*(i/(points.length-1||1))} ${pad+(h-pad*2)*(1-(p.value-min)/range)}`).join(' ')}
function renderSparks(data){const root=q("#spark-grid");Object.values(data.series||{}).forEach(s=>{if(!s.points?.length)return;const card=e("article","spark-card"),head=e("div","spark-card__head");head.append(e("h3","",s.label),e("strong","",`${s.points.at(-1).value.toLocaleString(undefined,{maximumFractionDigits:2})}${s.unit==='%'?'%':''}`));card.append(head);const S=svg('svg',{viewBox:'0 0 500 90','aria-label':`${s.label} 30-day trend`});S.append(svg('line',{x1:6,y1:82,x2:494,y2:82,stroke:'#d4cec3','stroke-width':1}));S.append(svg('path',{d:sparkPath(s.points,500,90),fill:'none',stroke:'#171614','stroke-width':2,'vector-effect':'non-scaling-stroke'}));card.append(S);const meta=e("div","spark-card__meta");meta.append(e("span","",s.points[0].date),e("span","",s.source),e("span","",s.points.at(-1).date));card.append(meta);root.append(card)})}
async function init(){try{const r=await fetch(DATA_URL,{cache:'no-store'});if(!r.ok)throw new Error(`${r.status}`);const data=await r.json();renderHero(data);renderRibbon(data);renderSignals(data);renderCatalystMap(data);renderThemes(data);renderSparks(data)}catch(err){console.error(err);q('#lens-app').append(e('div','status-panel status-panel--error',`30D Lens data unavailable: ${err.message}`))}}
document.addEventListener('DOMContentLoaded',init);


/* v2.1 policy-lane state */
(() => {
  const DATA_PATH = "data/trends/rolling-30d.json";
  const renderPolicyState = async () => {
    try {
      const response = await fetch(`${DATA_PATH}?v=2.1.0`, { cache: "no-store" });
      if (!response.ok) return;
      const data = await response.json();
      const monitor = data.policy_monitor;
      if (!monitor) return;
      const section = document.querySelector("#catalysts")?.closest("section") || document.querySelector("#catalysts");
      if (!section || section.querySelector(".policy-lane-state")) return;
      const box = document.createElement("div");
      box.className = "policy-lane-state";
      const count = Number(monitor.events_in_window || 0);
      box.innerHTML = count > 0
        ? `<strong>China / Trade / Industrial Policy</strong><span>${count} 个已确认政策节点 · P 为政策节点</span>`
        : `<strong>China / Trade / Industrial Policy</strong><span>${monitor.empty_state || "本窗口无入选 Top 3 的政策催化剂"}</span>`;
      section.appendChild(box);
    } catch (_) {
      // Core trend page remains available if this non-critical annotation fails.
    }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", renderPolicyState);
  else renderPolicyState();
})();
