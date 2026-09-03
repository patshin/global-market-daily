#!/usr/bin/env python3
from __future__ import annotations
import csv, json, math, statistics
from urllib.request import Request, urlopen
from collections import defaultdict, Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_DIR = ROOT / 'history'
DAILY_DIR = ROOT / 'docs/data/daily'
OUT_DIR = ROOT / 'docs/data/trends'
OUT_DIR.mkdir(parents=True, exist_ok=True)
VERIFIED_EVENTS_PATH = OUT_DIR / 'verified-events.json'

FRED_SERIES_IDS = tuple(SERIES_ID for SERIES_ID in (
    'NASDAQCOM','SP500','VIXCLS','DGS2','DGS10','DCOILBRENTEU','DTWEXBGS','BAMLH0A0HYM2'
))


def fred_url(series_id: str) -> str:
    # Keep enough context for rolling z-scores and continue working after 2026.
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=420)
    return (
        'https://fred.stlouisfed.org/graph/fredgraph.csv'
        f'?id={series_id}&cosd={start.isoformat()}&coed={today.isoformat()}'
    )

def ensure_history():
    """Refresh every series, falling back to the last valid local copy on outage."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    for sid in FRED_SERIES_IDS:
        path=HISTORY_DIR/f'{sid}.csv'
        try:
            req=Request(fred_url(sid),headers={'User-Agent':'GlobalMarketDaily/2.1 github.com/patshin/global-market-daily'})
            with urlopen(req,timeout=45) as response:
                payload=response.read()
            if len(payload)<100 or b'observation_date' not in payload[:200]:
                raise RuntimeError(f'{sid}: invalid FRED response')
            tmp=path.with_suffix('.csv.tmp')
            tmp.write_bytes(payload)
            tmp.replace(path)
        except Exception:
            if not path.exists() or path.stat().st_size<=100:
                raise

SERIES = {
    'NASDAQCOM': {'label':'Nasdaq Composite','unit':'Index','source':'Nasdaq, Inc. via FRED','kind':'price'},
    'SP500': {'label':'S&P 500','unit':'Index','source':'S&P Dow Jones Indices via FRED','kind':'price'},
    'VIXCLS': {'label':'VIX','unit':'Index','source':'CBOE via FRED','kind':'price'},
    'DGS2': {'label':'US 2Y Treasury Yield','unit':'%','source':'Federal Reserve H.15 via FRED','kind':'yield'},
    'DGS10': {'label':'US 10Y Treasury Yield','unit':'%','source':'Federal Reserve H.15 via FRED','kind':'yield'},
    'DCOILBRENTEU': {'label':'Brent','unit':'USD/bbl','source':'U.S. EIA via FRED','kind':'price'},
    'DTWEXBGS': {'label':'Broad Trade-Weighted USD','unit':'Index','source':'Federal Reserve via FRED','kind':'price'},
    'BAMLH0A0HYM2': {'label':'US High Yield OAS','unit':'%','source':'ICE BofA via FRED','kind':'yield'},
}

THEMES = {
    'equity_risk_appetite': ('Equity Risk Appetite','growth_macro'),
    'volatility_event_risk': ('Volatility / Event Risk','market_structure'),
    'global_duration': ('Global Duration / Term Premium','inflation_rates'),
    'fed_policy_path': ('Fed Policy Path','central_banks_fiscal'),
    'energy_inflation': ('Energy Inflation','geopolitics_energy'),
    'usd_financial_conditions': ('USD Financial Conditions','liquidity_credit'),
    'credit_conditions': ('Credit Conditions','liquidity_credit'),
    'growth_duration_rotation': ('Growth / Duration Rotation','earnings_ai_semis'),
    'geopolitics_energy': ('Geopolitics / Energy','geopolitics_energy'),
    'ai_earnings': ('AI / Earnings','earnings_ai_semis'),
    'market_structure': ('Market Structure','market_structure'),
    'us_china_trade_controls': ('U.S.–China Trade Controls','china_trade_policy'),
    'china_industrial_policy': ('China Industrial Policy','china_trade_policy'),
    'china_semiconductor_policy': ('China Semiconductor Policy','china_trade_policy'),
}

CATEGORY_LABELS = {
    'growth_macro':'Growth / Macro',
    'inflation_rates':'Inflation / Rates',
    'central_banks_fiscal':'Central Banks / Fiscal',
    'earnings_ai_semis':'Earnings / AI / Semiconductors',
    'geopolitics_energy':'Geopolitics / Energy',
    'china_trade_policy':'China / Trade / Industrial Policy',
    'liquidity_credit':'Liquidity / Credit / Financing',
    'market_structure':'Market Structure / Index / Options',
}

def read_csv(path: Path, series_id: str):
    out = []
    with path.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            raw = row.get(series_id)
            if not raw or raw in {'.','NA'}: continue
            try: value=float(raw)
            except ValueError: continue
            out.append({'date':row['observation_date'], 'value':value})
    return out

def pct(a,b):
    return None if a in (None,0) or b is None else (b/a-1)*100

def zscore(values, idx, window=20):
    if idx <= 1: return 0.0
    start=max(0,idx-window)
    hist=[v for v in values[start:idx] if v is not None]
    if len(hist)<5: return 0.0
    sd=statistics.pstdev(hist)
    if sd<1e-9: return 0.0
    return (values[idx]-statistics.mean(hist))/sd

def sign_symbol(x, threshold=.45):
    return '↑' if x>threshold else '↓' if x<-threshold else '→'

def theme_from_text(text: str):
    t=text.lower()
    china=any(k in t for k in ['china','chinese','中国','北京','国资委','工信部'])
    policy=any(k in t for k in ['policy','roadmap','standards','subsid','industrial','产业','政策','标准','规划','行动计划','6g','nev'])
    trade=any(k in t for k in ['tariff','trade','export control','import restriction','sanction','关税','贸易','出口管制','进口限制','制裁'])
    semis=any(k in t for k in ['semiconductor','chip','eda','集成电路','芯片','半导体'])
    if china and semis and policy: return 'china_semiconductor_policy'
    if china and policy: return 'china_industrial_policy'
    if trade or (china and any(k in t for k in ['u.s.','us ','美国'])): return 'us_china_trade_controls'
    if any(k in t for k in ['hormuz','iran','伊朗','美伊','war','航运']): return 'geopolitics_energy'
    if any(k in t for k in ['dell','broadcom','avgo','nvda','ai','semiconductor','半导体','财报']): return 'ai_earnings'
    if any(k in t for k in ['10y','yield','treasury','jgb','主权债','收益率','term premium']): return 'global_duration'
    if any(k in t for k in ['fed','fomc','加息','降息']): return 'fed_policy_path'
    if any(k in t for k in ['oil','brent','wti','原油','能源']): return 'energy_inflation'
    if any(k in t for k in ['credit','spread','融资','liquidity']): return 'credit_conditions'
    return 'market_structure'

def importance_to_level(x):
    s=str(x or '')
    return 5 if '★★★★★' in s else 4 if '★★★★' in s else 3

def market_bias_from_direction(x):
    s=str(x or '').lower()
    if 'bearish' in s and 'bullish' not in s: return 'risk_off'
    if 'bullish' in s and 'bearish' not in s: return 'risk_on'
    return 'mixed'



def load_verified_events():
    if not VERIFIED_EVENTS_PATH.exists():
        return {}
    doc=json.loads(VERIFIED_EVENTS_PATH.read_text(encoding='utf-8'))
    by_date=defaultdict(list)
    for item in doc.get('events',[]):
        market_date=item.get('market_date')
        if market_date:
            by_date[market_date].append(item)
    return by_date

def load_native_reports():
    native={}
    for p in sorted(DAILY_DIR.glob('*.json')):
        try: r=json.loads(p.read_text(encoding='utf-8'))
        except Exception: continue
        cycle=r.get('publication_cycle') or {}
        if cycle.get('is_final') is False:
            continue
        d=r.get('date')
        if d: native[d]=r
    return native

def build():
    ensure_history()
    raw={sid:read_csv(HISTORY_DIR/f'{sid}.csv',sid) for sid in SERIES}
    maps={sid:{p['date']:p['value'] for p in pts} for sid,pts in raw.items()}
    master_dates=sorted(set(maps['NASDAQCOM']) | set(maps['SP500']))
    native=load_native_reports()
    verified_events=load_verified_events()
    as_of=max(max(master_dates), max(native) if native else max(master_dates))
    as_of_date=date.fromisoformat(as_of)
    window_start=(as_of_date-timedelta(days=29)).isoformat()
    dates=[d for d in master_dates if window_start<=d<=as_of]
    # include native dates even if no close yet
    for d in native:
        if window_start<=d<=as_of and d not in dates: dates.append(d)
    dates=sorted(dates)

    # historical output with changes
    market_history={'schema_version':'1.0.0','retrieved_for':'Global Market Daily 30D Lens','as_of':as_of,'series':{}}
    series_changes={}
    for sid, meta in SERIES.items():
        pts=raw[sid]
        vals=[p['value'] for p in pts]
        changes=[]
        prev=None
        for i,p in enumerate(pts):
            value=p['value']; ch=None
            if prev is not None:
                ch=(value-prev)*100 if meta['kind']=='yield' else pct(prev,value)
            changes.append(ch)
            prev=value
        zs=[0.0]*len(pts)
        for i in range(len(pts)):
            if changes[i] is not None: zs[i]=zscore([x if x is not None else 0 for x in changes],i)
        enriched=[]
        for p,ch,z in zip(pts,changes,zs):
            enriched.append({'date':p['date'],'value':p['value']})
        market_history['series'][sid]={**meta,'points':enriched}
        series_changes[sid]={p['date']:{'value':p['value'],'change':ch,'z':z} for p,ch,z in zip(pts,changes,zs)}

    def v(sid,d,key='value'):
        return series_changes.get(sid,{}).get(d,{}).get(key)

    days=[]
    for d in dates:
        if d in native:
            r=native[d]
            regime_item=(r.get('market_regime') or {}).get('overall')
            regime_label=regime_item.get('state') if isinstance(regime_item,dict) else (regime_item or 'Neutral')
            code={'Risk-On':'risk_on','Neutral':'neutral','Risk-Off':'risk_off','Event Risk':'event_risk'}.get(regime_label,'event_risk' if 'Event' in str(regime_label) else 'neutral')
            catalysts=[]
            for i,c in enumerate(r.get('top_catalysts') or []):
                tid=theme_from_text(c.get('event','')+' '+c.get('what_happened',''))
                catalysts.append({
                    'rank':c.get('rank',i+1),'theme_id':tid,'theme_label':THEMES[tid][0],'category':THEMES[tid][1],
                    'title':c.get('event',''),'evidence':c.get('what_happened',''),'market_bias':market_bias_from_direction(c.get('direction')),
                    'importance_level':importance_to_level(c.get('importance')),'importance':c.get('importance',''),
                    'transmission':c.get('transmission',''),'confirmation':c.get('confirmation',''),'invalidation':c.get('invalidation',''),
                    'source_mode':'native_daily'
                })
            signals={}
            smap={'growth':'growth_impulse','inflation':'inflation_impulse','rates':'rates_pressure','earnings':'earnings_revision','liquidity':'liquidity','geopolitics':'geopolitical_risk'}
            sp=r.get('signal_panel') or {}
            for key,source_key in smap.items():
                item=sp.get(source_key) or {}
                cur=item.get('current','→') if isinstance(item,dict) else '→'
                signals[key]='↑' if '↑' in str(cur) else '↓' if '↓' in str(cur) else '→'
            risks=[]
            for rr in r.get('top_risks') or []:
                tid=theme_from_text(rr.get('risk','')+' '+rr.get('transmission',''))
                risks.append({'theme_id':tid,'title':rr.get('risk',''),'first_asset':rr.get('first_asset',''),'transmission':rr.get('transmission',''),'source_mode':'native_daily'})
            days.append({'date':d,'source_mode':'native_daily','regime_code':code,'regime_label':regime_label,
                         'dominant_theme_id':catalysts[0]['theme_id'] if catalysts else 'market_structure','signals':signals,
                         'catalysts':catalysts[:3]})
            continue

        candidates=[]
        def add(theme_id, score, title, evidence, bias, transmission):
            if score is None: return
            candidates.append({'theme_id':theme_id,'theme_label':THEMES[theme_id][0],'category':THEMES[theme_id][1],
                'score':abs(score),'title':title,'evidence':evidence,'market_bias':bias,
                'importance_level':5 if abs(score)>=2 else 4 if abs(score)>=1.15 else 3,
                'importance':'★★★★★' if abs(score)>=2 else '★★★★' if abs(score)>=1.15 else '★★★',
                'transmission':transmission,'source_mode':'objective_market_reconstruction'})
        nz=v('NASDAQCOM',d,'z'); nc=v('NASDAQCOM',d,'change')
        if nz is not None and nc is not None: add('equity_risk_appetite',nz,f'Nasdaq daily move {nc:+.2f}%',f'NASDAQCOM {nc:+.2f}% vs prior close','risk_on' if nc>0 else 'risk_off','Equity move → risk appetite / duration repricing')
        vz=v('VIXCLS',d,'z'); vc=v('VIXCLS',d,'change')
        if vz is not None and vc is not None: add('volatility_event_risk',vz,f'VIX daily move {vc:+.2f}%',f'VIXCLS {vc:+.2f}%','risk_off' if vc>0 else 'risk_on','Volatility ↑ → hedging demand ↑ → equity risk appetite ↓' if vc>0 else 'Volatility ↓ → event premium eases')
        yz=v('DGS10',d,'z'); yc=v('DGS10',d,'change')
        if yz is not None and yc is not None: add('global_duration',yz,f'US 10Y moves {yc:+.1f}bp',f'DGS10 {yc:+.1f}bp','risk_off' if yc>0 else 'risk_on','10Y ↑ → discount rate ↑ → long-duration equity valuation ↓' if yc>0 else '10Y ↓ → discount rate eases')
        y2z=v('DGS2',d,'z'); y2c=v('DGS2',d,'change')
        if y2z is not None and y2c is not None: add('fed_policy_path',y2z,f'US 2Y moves {y2c:+.1f}bp',f'DGS2 {y2c:+.1f}bp','risk_off' if y2c>0 else 'risk_on','2Y ↑ → policy path reprices tighter' if y2c>0 else '2Y ↓ → policy path reprices easier')
        bz=v('DCOILBRENTEU',d,'z'); bc=v('DCOILBRENTEU',d,'change')
        if bz is not None and bc is not None: add('energy_inflation',bz,f'Brent daily move {bc:+.2f}%',f'DCOILBRENTEU {bc:+.2f}%','risk_off' if bc>0 else 'risk_on','Oil ↑ → inflation expectations ↑ → rates pressure ↑' if bc>0 else 'Oil ↓ → inflation impulse eases')
        uz=v('DTWEXBGS',d,'z'); uc=v('DTWEXBGS',d,'change')
        if uz is not None and uc is not None: add('usd_financial_conditions',uz,f'Broad USD daily move {uc:+.2f}%',f'DTWEXBGS {uc:+.2f}%','risk_off' if uc>0 else 'risk_on','USD ↑ → global financial conditions tighten' if uc>0 else 'USD ↓ → global conditions ease')
        cz=v('BAMLH0A0HYM2',d,'z'); cc=v('BAMLH0A0HYM2',d,'change')
        if cz is not None and cc is not None: add('credit_conditions',cz,f'HY OAS moves {cc:+.1f}bp',f'BAMLH0A0HYM2 {cc:+.1f}bp','risk_off' if cc>0 else 'risk_on','Credit spreads wider → funding conditions tighten' if cc>0 else 'Credit spreads tighter → funding conditions ease')
        # rotation: relative Nasdaq vs SPX move
        spc=v('SP500',d,'change')
        if nc is not None and spc is not None:
            rel=nc-spc
            add('growth_duration_rotation',rel/0.35,f'Nasdaq relative to S&P 500 {rel:+.2f}pp',f'NASDAQCOM {nc:+.2f}% vs SP500 {spc:+.2f}%','risk_on' if rel>0 else 'risk_off','Growth leadership strengthens' if rel>0 else 'Long-duration growth underperforms')

        # Verified policy/trade events complement the price-only reconstruction.
        # They remain explicitly labelled and never overwrite a native GMD daily view.
        for event in verified_events.get(d, []):
            tid=event['theme_id']
            candidates.append({
                'theme_id':tid,'theme_label':THEMES[tid][0],'category':event.get('category',THEMES[tid][1]),
                'score':float(event.get('ranking_score',1.5)),'title':event['title'],'evidence':event['evidence'],
                'market_bias':event.get('market_bias','mixed'),'importance_level':int(event.get('importance_level',4)),
                'importance':event.get('importance','★★★★'),'transmission':event.get('transmission',''),
                'confirmation':event.get('confirmation',''),'invalidation':event.get('invalidation',''),
                'source_mode':'verified_event','event_id':event.get('id'),'status':event.get('status','Confirmed'),
                'actual_event_date':event.get('actual_event_date',d),'source_name':event.get('source_name',''),
                'source_title':event.get('source_title',''),'source_url':event.get('source_url'),
                'source_tier':event.get('source_tier','Tier 1'),'confidence':event.get('confidence','High')
            })

        candidates.sort(key=lambda x:x['score'], reverse=True)
        top=[]
        seen=set()
        for c in candidates:
            if c['theme_id'] in seen: continue
            seen.add(c['theme_id']); c=dict(c); c['rank']=len(top)+1; c.pop('score',None); top.append(c)
            if len(top)==3: break
        # Transparent regime rules: count observable stress/relief conditions.
        # No weighted composite score is created or displayed.
        def z(sid): return v(sid,d,'z') or 0.0
        def ch(sid): return v(sid,d,'change') or 0.0
        stress_conditions = [
            z('NASDAQCOM') <= -0.75,
            z('VIXCLS') >= 0.75,
            z('BAMLH0A0HYM2') >= 0.75,
            z('DTWEXBGS') >= 0.85,
            z('DGS10') >= 0.85 and ch('NASDAQCOM') < 0,
            z('DCOILBRENTEU') >= 0.85 and (z('DGS10') > 0 or ch('NASDAQCOM') < 0),
        ]
        relief_conditions = [
            z('NASDAQCOM') >= 0.75,
            z('VIXCLS') <= -0.75,
            z('BAMLH0A0HYM2') <= -0.75,
            z('DTWEXBGS') <= -0.85,
            z('DGS10') <= -0.85 and ch('NASDAQCOM') > 0,
            z('DCOILBRENTEU') <= -0.85 and ch('NASDAQCOM') > 0,
        ]
        stress=sum(stress_conditions); relief=sum(relief_conditions)
        extreme=max(abs(z(s)) for s in ['NASDAQCOM','VIXCLS','DGS10','DCOILBRENTEU','DTWEXBGS','BAMLH0A0HYM2'])
        verified_risk_event=any(c.get('source_mode')=='verified_event' and c.get('market_bias')=='risk_off' and c.get('importance_level',3)>=5 for c in top)
        if (stress>=3 and extreme>=1.5) or (verified_risk_event and stress>=2): code='event_risk'; label='Event Risk'
        elif stress>=2 and stress>relief: code='risk_off'; label='Risk-Off'
        elif relief>=2 and relief>stress: code='risk_on'; label='Risk-On'
        else: code='neutral'; label='Neutral'
        signals={
            'growth':sign_symbol((z('NASDAQCOM')+z('SP500'))/2),
            'inflation':sign_symbol(z('DCOILBRENTEU')),
            'rates':sign_symbol((z('DGS2')+z('DGS10'))/2),
            'earnings':sign_symbol(((ch('NASDAQCOM')-ch('SP500'))/0.35)),
            'liquidity':sign_symbol(-(z('BAMLH0A0HYM2')+z('DTWEXBGS'))/2),
            'geopolitics':sign_symbol((z('VIXCLS')+max(0,z('DCOILBRENTEU')))/2),
        }
        days.append({'date':d,'source_mode':'objective_market_reconstruction','regime_code':code,'regime_label':label,
                     'dominant_theme_id':top[0]['theme_id'] if top else 'market_structure','signals':signals,'catalysts':top})

    # transitions
    transitions=[]
    prev=None
    for day in days:
        if prev and day['regime_code']!=prev['regime_code']:
            transitions.append({'date':day['date'],'from':prev['regime_label'],'to':day['regime_label'],'dominant_theme_id':day['dominant_theme_id']})
        prev=day

    # lifecycle
    occurrences=defaultdict(list)
    for day in days:
        for c in day['catalysts']:
            occurrences[c['theme_id']].append((day,c))
    persistent=[]
    for tid, occ in occurrences.items():
        ranks=[c['rank'] for _,c in occ]
        first=occ[0][0]['date']; last=occ[-1][0]['date']; latest_rank=occ[-1][1]['rank'] if last==days[-1]['date'] else None
        recent=sum(1 for day,_ in occ if date.fromisoformat(day['date']) >= as_of_date-timedelta(days=5))
        prior=sum(1 for day,_ in occ if as_of_date-timedelta(days=12) <= date.fromisoformat(day['date']) < as_of_date-timedelta(days=5))
        if first >= (as_of_date-timedelta(days=4)).isoformat(): state='New'
        elif recent>=2 and recent>prior: state='Escalating'
        elif last < (as_of_date-timedelta(days=5)).isoformat(): state='Resolved'
        elif recent==0: state='Easing'
        else: state='Persistent'
        latest=occ[-1][1]
        persistent.append({'theme_id':tid,'theme_label':THEMES.get(tid,(tid,''))[0],'category':THEMES.get(tid,('', 'market_structure'))[1],
                           'days_in_top3':len(occ),'best_rank':min(ranks),'first_seen':first,'last_seen':last,'latest_rank':latest_rank,
                           'state':state,'latest_transmission':latest.get('transmission',''),'source_modes':sorted(set(c.get('source_mode',day['source_mode']) for day,c in occ))})
    persistent.sort(key=lambda x:(-x['days_in_top3'],x['best_rank']))

    # current confirmation based on latest native day if available else last day
    current=days[-1]
    tid=current['dominant_theme_id']
    expected={
        'geopolitics_energy': {'DCOILBRENTEU':1,'VIXCLS':1,'DGS10':1,'NASDAQCOM':-1,'DTWEXBGS':1},
        'energy_inflation': {'DCOILBRENTEU':1,'DGS10':1,'NASDAQCOM':-1,'DTWEXBGS':1},
        'global_duration': {'DGS10':1,'DGS2':1,'NASDAQCOM':-1,'VIXCLS':1},
        'ai_earnings': {'NASDAQCOM':1,'SP500':1,'VIXCLS':-1},
        'fed_policy_path': {'DGS2':1,'DGS10':1,'NASDAQCOM':-1,'DTWEXBGS':1},
    }.get(tid, {'NASDAQCOM':1,'SP500':1,'VIXCLS':-1})
    # use native tape if present for current day; otherwise historical changes
    current_report=native.get(current['date'],{})
    tape={item.get('asset'):item for item in current_report.get('market_tape',[]) if isinstance(item,dict)}
    aliases={'NASDAQCOM':'Nasdaq Composite','SP500':'S&P 500','VIXCLS':'VIX','DGS2':'UST 2Y','DGS10':'UST 10Y','DCOILBRENTEU':'Brent','DTWEXBGS':'DXY','BAMLH0A0HYM2':'US High Yield OAS'}
    confirms=[]; diverges=[]; unavailable=[]
    for sid,sgn in expected.items():
        delta=v(sid,current['date'],'change')
        display_delta=None
        # native tape parsing when possible
        asset=tape.get(aliases.get(sid,''))
        if asset:
            rawc=str(asset.get('change_1d',''))
            try:
                num=float(rawc.replace('%','').replace('bp','').replace('+','').strip())
                delta=num
            except Exception: pass
            display_delta=rawc
        if delta is None:
            unavailable.append({'series_id':sid,'label':SERIES[sid]['label']}); continue
        actual=1 if delta>0 else -1 if delta<0 else 0
        item={'series_id':sid,'label':SERIES[sid]['label'],'change':display_delta or (f'{delta:+.1f}bp' if SERIES[sid]['kind']=='yield' else f'{delta:+.2f}%')}
        (confirms if actual==sgn else diverges).append(item)
    confirmation={'theme_id':tid,'theme_label':THEMES.get(tid,(tid,''))[0],'as_of':current['date'],'confirming':confirms,'diverging':diverges,'unavailable':unavailable,
                  'interpretation_note':f"{len(confirms)} 项资产确认当前主线，{len(diverges)} 项出现背离。",
                  'what_would_flip_it':current['catalysts'][0].get('invalidation','A material reversal in the key confirming assets.') if current['catalysts'] else ''}

    rolling={
        'schema_version':'1.0.0','as_of':as_of,'window_start':window_start,'window_end':as_of,
        'coverage':{'market_sessions':len(days),'native_daily_days':sum(1 for x in days if x['source_mode']=='native_daily'),'reconstructed_days':sum(1 for x in days if x['source_mode']!='native_daily'),'verified_event_days':sum(1 for x in days if any(c.get('source_mode')=='verified_event' for c in x.get('catalysts',[]))),
                    'historical_series_start':min(p['date'] for pts in raw.values() for p in pts)},
        'methodology':{'native_daily':'Original published GMD daily assessment.','verified_event':'Primary-source policy or trade event aligned to its first market session.','objective_market_reconstruction':'Rule-based reconstruction from contemporaneous market-price/rate changes; not a retroactive claim about the day’s news narrative.','no_black_box_score':True},
        'category_labels':CATEGORY_LABELS,'themes':{k:{'label':v[0],'category':v[1]} for k,v in THEMES.items()},
        'days':days,'regime_transitions':transitions,'persistent_themes':persistent[:12],'cross_asset_confirmation':confirmation,
        'series':{sid:{**SERIES[sid], 'points':[p for p in market_history['series'][sid]['points'] if window_start<=p['date']<=as_of]} for sid in SERIES}
    }
    (OUT_DIR/'market-history.json').write_text(json.dumps(market_history,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT_DIR/'rolling-30d.json').write_text(json.dumps(rolling,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT_DIR/'theme-registry.json').write_text(json.dumps({'schema_version':'1.0.0','themes':rolling['themes'],'categories':CATEGORY_LABELS},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'as_of':as_of,'window_start':window_start,'sessions':len(days),'native':rolling['coverage']['native_daily_days'],'reconstructed':rolling['coverage']['reconstructed_days'],'themes':len(persistent)},ensure_ascii=False))

if __name__=='__main__': build()
