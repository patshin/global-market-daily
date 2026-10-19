#!/usr/bin/env python3
"""One-time, anchor-checked October lens migration. Apply on reviewed repair branch."""
from pathlib import Path
import json, subprocess
R=Path(__file__).resolve().parents[1]

def replace(path,a,b):
    p=R/path;s=p.read_text(encoding='utf-8')
    if b in s and a not in s:return
    assert s.count(a)==1,(path,a[:120],s.count(a))
    p.write_text(s.replace(a,b),encoding='utf-8')

replace('scripts/build_market_lens.py','from pathlib import Path','from pathlib import Path\nfrom lens_history_support import cached_points, merge_history, historical_proxy, editorial_direction')
replace('scripts/build_market_lens.py',"            if not path.exists() or path.stat().st_size<=100:\n                raise", "            if not path.exists() or path.stat().st_size<=100:\n                cached=cached_points(HISTORY_DIR.parent,sid)\n                if not cached: raise\n                with path.open('w',encoding='utf-8',newline='') as output:\n                    writer=csv.writer(output);writer.writerow(['observation_date',sid])\n                    writer.writerows((p['date'],p['value']) for p in cached)")
replace('scripts/build_market_lens.py',"raw={sid:read_csv(HISTORY_DIR/f'{sid}.csv',sid) for sid in SERIES}","raw={sid:merge_history(HISTORY_DIR.parent,sid,read_csv(HISTORY_DIR/f'{sid}.csv',sid) if (HISTORY_DIR/f'{sid}.csv').is_file() else []) for sid in SERIES}")
replace('scripts/build_market_lens.py',"enriched.append({'date':p['date'],'value':p['value']})","enriched.append(dict(p))")
replace('scripts/build_market_lens.py',"signals[key]='↑' if '↑' in str(cur) else '↓' if '↓' in str(cur) else '→' if '→' in str(cur) else '?'","signals[key]=editorial_direction(cur)")
a="""            days.append({'date':d,'source_mode':report_mode,'regime_code':code,'regime_label':regime_label,
                         'dominant_theme_id':catalysts[0]['theme_id'] if catalysts else 'market_structure','signals':signals,
                         'catalysts':catalysts[:3]})"""
b="""            day={'date':d,'source_mode':report_mode,'regime_code':code,'regime_label':regime_label,
                 'dominant_theme_id':catalysts[0]['theme_id'] if catalysts else 'market_structure','signals':signals,
                 'catalysts':catalysts[:3]}
            proxy=historical_proxy(HISTORY_DIR.parent,r)
            if proxy:
                day['price_proxy']=proxy
                day['editorial_regime_label']=regime_label
                for key,value in proxy['signals'].items():
                    if day['signals'].get(key)=='?': day['signals'][key]=value
                if code=='unclassified' and proxy['regime_code']!='unclassified':
                    day['regime_code']=proxy['regime_code']
                    day['regime_label']='市场价格代理（非原编辑判断） · '+proxy['regime_code']
                    day['regime_basis']='historical_price_proxy'
            days.append(day)"""
replace('scripts/build_market_lens.py',a,b)
a="    # use native tape if present for current day; otherwise historical changes"
b=r"""    # The explicit directional statement overrides a positive generic theme template.
    # In particular, a selloff/negative AI call must not treat falling AI equities as divergence.
    current_source=native.get(current['date'],{})
    lead=(current_source.get('top_catalysts') or [{}])[0]
    lead_direction=str(lead.get('direction',''))
    negative_ai=(tid=='ai_earnings' and (re.search(r'^\s*↓[^/]*(?:AI|semiconductor|科技|半导体)',lead_direction,re.I) or re.search(r'\brisk[- ]off\b|bearish',lead_direction,re.I)))
    if negative_ai: expected={'NASDAQCOM':-1,'SP500':-1,'VIXCLS':1}
    expectation_note='Explicit leading catalyst: '+lead_direction if lead_direction else 'Thematic conditional comparison; not a verified causal attribution.'
    # use native tape if present for current day; otherwise historical changes"""
replace('scripts/build_market_lens.py',a,b)
replace('scripts/build_market_lens.py',"        asset=tape.get(aliases.get(sid,''))","        asset=tape.get(aliases.get(sid,''))\n        if asset is None and sid=='VIXCLS':asset=tape.get('CBOE VIX') or tape.get('Cboe VIX')")
replace('scripts/build_market_lens.py',"                num=float(rawc.replace('%','').replace('bp','').replace('+','').strip())\n                delta=num",r"""                match=re.fullmatch(r'\s*([+-]?\d+(?:\.\d+)?)\s*(?:%|bp|bps|pp|pts|points)?\s*',rawc)
                if match:delta=float(match.group(1))""")
replace('scripts/build_market_lens.py',"'interpretation_note':f\"{len(confirms)} 项资产确认当前主线，{len(diverges)} 项出现背离。\",","'expectation_basis':expectation_note,'interpretation_note':f\"{len(confirms)} 项资产方向与当前主线一致，{len(diverges)} 项出现背离；不是因果证明。\",")
a="    (OUT_DIR/'market-history.json').write_text"
b="""    month_start=as_of[:7]+'-01'
    expected=[(date.fromisoformat(month_start)+timedelta(days=i)).isoformat() for i in range((as_of_date-date.fromisoformat(month_start)).days+1)]
    month_days=[d for d in days if month_start<=d['date']<=as_of]
    rolling['monthly_coverage']={'month':as_of[:7],'through':as_of,'expected_days':len(expected),'present_days':len(month_days),
        'missing_dates':[d for d in expected if not any(x['date']==d for x in month_days)],
        'unclassified_dates':[d['date'] for d in month_days if d['regime_code'] in {'unclassified','unavailable'}],
        'unknown_signal_cells':sum(v=='?' for d in month_days for v in d.get('signals',{}).values()),
        'price_proxy_dates':[d['date'] for d in month_days if d.get('price_proxy')],
        'note':'Calendar coverage, editorial provenance and underlying-provider freshness are separate; price proxies do not restore missing original judgments.'}
    rolling['series_freshness']={sid:{'last_observation':s['points'][-1]['date'] if s['points'] else None,'source':s['source'],
        'note':'Independent provider as_of; no forward-fill or cross-instrument substitution.'} for sid,s in rolling['series'].items()}
    (OUT_DIR/'market-history.json').write_text"""
replace('scripts/build_market_lens.py',a,b)
replace('docs/assets/trends.js','  const ol=e("ol");','''  if(day.price_proxy){
    target.append(e("p","lens-proxy-note",day.price_proxy.note));
    const detail=e("ul","lens-proxy-details");
    Object.entries(day.price_proxy.details).forEach(([key,item])=>{
      const observations=item.observations.map(o=>`${o.asset} ${o.change_1d} · ${o.session_date} · ${o.sources.join(",")}`).join("; ");
      detail.append(e("li","",`${key}: ${item.direction} · ${item.formula} · ${observations||"证据未恢复"}`));
    });target.append(detail);
  }
  const ol=e("ol");''')
replace('docs/assets/trends.js','`${code} ${day.source_mode==="native_daily"?"native":""}`.trim()','`${code} ${day.source_mode==="native_daily"?"native":""} ${day.price_proxy?"proxy":""}`.trim()')
replace('docs/assets/trends.js','direction=["↑","↓","→"].includes(value)?value:"?"','direction=["↑","↓","→","↕","↔"].includes(value)?value:"?"')
replace('docs/assets/trends.js','direction==="→"?"signal-cell--flat":"signal-cell--unknown"','(direction==="→"||direction==="↔")?"signal-cell--flat":direction==="↕"?"signal-cell--mixed":"signal-cell--unknown"')
replace('docs/assets/trends.js','cell.title=`${d.date} · ${label}：${direction==="?"?"方向未判定；不是中性":direction}`;','cell.title=`${d.date} · ${label}：${direction==="?"?"方向未判定；不是中性":direction}${d.price_proxy?" · 市场价格代理，非原编辑判断 · "+(d.price_proxy.details[key]?.formula||""):""}`;\n      if(d.price_proxy)cell.classList.add("signal-cell--proxy");')
replace('docs/assets/trends.js','  q("#lens-footer").textContent=`As of ${data.as_of}`;','''  q("#lens-footer").textContent=`As of ${data.as_of}`;
  if(data.monthly_coverage){const c=data.monthly_coverage,note=e("p","lens-proxy-note",`${c.month} 截至 ${c.through}：${c.present_days}/${c.expected_days} 个覆盖日；${c.price_proxy_dates.length} 日采用有来源的价格代理；${c.missing_dates.length} 日缺失。下划线仅代表原生来源，不代表风险大小。`);q("#lens-hero-meta").after(note);}
''')
replace('docs/assets/trends.js',"card.append(head);const S=svg('svg'", "card.append(head,e('p','lens-observation-date',`观测截至 ${s.points.at(-1).date} · 不前向填充；与日报日期分开`));const S=svg('svg'")
replace('docs/assets/p0.js','day.source_mode === "native_daily" ? " regime-ribbon__cell--native" : ""','day.source_mode === "native_daily" ? " regime-ribbon__cell--native" : day.price_proxy ? " regime-ribbon__cell--proxy" : ""')
css=R/'docs/assets/market-lens.css'
addition='''
/* Historical price proxies retain nonnative provenance and visible source basis. */
.lens-full-ribbon button.proxy,.regime-ribbon__cell--proxy{background-image:repeating-linear-gradient(135deg,transparent 0,transparent 7px,rgba(255,255,255,.5) 7px,rgba(255,255,255,.5) 9px)}
.signal-cell--proxy{box-shadow:inset 0 -2px 0 #9c845e}
.signal-cell--mixed{background:linear-gradient(135deg,#e6eee9 0,#e6eee9 50%,#f0e1df 50%,#f0e1df 100%);font-weight:700}
.lens-proxy-note{font-size:.8rem;line-height:1.65;color:var(--charcoal);padding:12px 0}
.lens-proxy-details{padding-left:20px;font-size:.75rem;overflow-wrap:anywhere}
.lens-observation-date{font-size:.7rem;color:var(--muted);margin:8px 0}
'''
if addition not in css.read_text():css.write_text(css.read_text()+addition)
replace('docs/trends.html','<span>↓ 下降</span>','<span>↓ 下降</span><span>↕ 分化 / ↔ 区间</span><span>斜纹颜色：有来源的价格代理，非原编辑判断</span>')
policy={'schema_version':'1.0.0','dates':[f'2026-10-{i:02}' for i in range(1,9)],'basis':'opt-in prior-session canonical tape only','note':'User-authorized October gap repair. Preserve existing source_mode, report text, original unknown editorial fields and historical timestamps.'}
(R/'docs/data/trends/historical-proxy-policy.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n')
test=R/'scripts/test_market_lens_native_accumulation.py'
regression='''
# Explicit proxy evidence, native exclusion, future-session rejection and cache isolation.
from lens_history_support import editorial_direction, merge_history, historical_proxy
assert editorial_direction('↔ range')=='↔'
assert editorial_direction('↕ mixed')=='↕'
assert editorial_direction('unknown')=='?'
with tempfile.TemporaryDirectory() as tmp:
    base=Path(tmp);target=base/'docs/data/trends';target.mkdir(parents=True)
    (target/'historical-series-supplement.json').write_text(json.dumps({'series':{'SP500':{'points':[{'date':'2026-10-01','value':100,'source_url':'https://example.test/source'},{'date':'2026-10-02','value':101,'source_url':'https://example.test/source'}]}}}))
    result=merge_history(base,'SP500',[{'date':'2026-10-01','value':99}])
    assert [x['value'] for x in result]==[99,101],result
    (target/'historical-proxy-policy.json').write_text(json.dumps({'dates':['2026-10-02']}))
    r={'date':'2026-10-02','reconstruction':{'is_reconstructed':True},'market_tape':[]}
    for name,delta in [('S&P 500',1),('Nasdaq Composite',2),('VIX',-1),('DXY',-0.5),('UST 10Y',-3),('Brent',-2)]:
        r['market_tape'].append({'asset':name,'as_of':'2026-10-01 close','change_1d':f'{delta:+}%', 'sources':['S01']})
    proxy=historical_proxy(base,r)
    assert proxy['regime_code']=='risk_on' and all(v!='?' for v in proxy['signals'].values()),proxy
    assert proxy['signals']['earnings']=='↑' and proxy['signals']['liquidity']=='↑'
    r['market_tape'][0]['as_of']='2026-10-02 close'
    proxy=historical_proxy(base,r);assert proxy['regime_code']=='unclassified' and proxy['signals']['growth']=='?'
    r['reconstruction']['is_reconstructed']=False
    assert historical_proxy(base,r) is None
print('HISTORICAL PROXY REGRESSION PASSED — explicit sources, native exclusion, no future close, no overwrite or unknown-as-neutral')
'''
if regression not in test.read_text():test.write_text(test.read_text()+regression)
subprocess.run(['python','scripts/stamp_assets.py'],cwd=R,check=True)
print('OCTOBER LENS MIGRATION APPLIED; existing publication facts and latest pointer were not edited')
