#!/usr/bin/env python3
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
errors=[]
def req(cond,msg):
    if not cond: errors.append(msg)

data=json.loads((ROOT/'docs/data/trends/rolling-30d.json').read_text(encoding='utf-8'))
req(data.get('schema_version')=='1.0.0','rolling schema version')
req(data.get('methodology',{}).get('no_black_box_score') is True,'black-box score must be prohibited')
days=data.get('days',[]); req(len(days)>=20,'need at least 20 market sessions for Day-1 30D lens')
req(data.get('coverage',{}).get('native_daily_days',0)>=1,'need at least one native daily assessment')
req(data.get('coverage',{}).get('reconstructed_days',0)>=1,'historical reconstruction coverage missing')
for i,d in enumerate(days):
    req(d.get('source_mode') in {'native_daily','objective_market_reconstruction'},f'day {i} source_mode invalid')
    req(d.get('regime_code') in {'risk_on','neutral','risk_off','event_risk'},f'day {i} regime invalid')
    req(len(d.get('catalysts',[]))==3,f'day {i} must expose three ranked driver proxies/catalysts')
    for j,c in enumerate(d.get('catalysts',[])):
        req(c.get('theme_id'),f'day {i} catalyst {j} theme_id missing')
        req(c.get('category'),f'day {i} catalyst {j} category missing')
        req(c.get('source_mode') in {'native_daily','objective_market_reconstruction','verified_event'},f'day {i} catalyst {j} provenance invalid')
        if d.get('source_mode')=='native_daily': req(c.get('source_mode')=='native_daily',f'day {i} native catalyst {j} provenance mismatch')
        if c.get('source_mode')=='verified_event':
            req(str(c.get('source_url','')).startswith('https://'),f'day {i} verified catalyst {j} source_url missing')
            req(bool(c.get('source_name')),f'day {i} verified catalyst {j} source_name missing')
            req(bool(c.get('event_id')),f'day {i} verified catalyst {j} event_id missing')

categories=data.get('category_labels',{})
req('china_trade_policy' in categories,'China / Trade / Industrial Policy category missing')
verified_path=ROOT/'docs/data/trends/verified-events.json'
req(verified_path.exists(),'verified policy event archive missing')
if verified_path.exists():
    verified=json.loads(verified_path.read_text(encoding='utf-8')).get('events',[])
    eligible={e.get('category') for e in verified if data.get('window_start','')<=e.get('market_date','')<=data.get('window_end','')}
    displayed={c.get('category') for day in days for c in day.get('catalysts',[]) if c.get('source_mode')=='verified_event'}
    for category in eligible:
        req(category in displayed,f'eligible verified event category not displayed: {category}')

req(len(data.get('persistent_themes',[]))>=5,'persistent theme lifecycle too thin')
series=data.get('series',{}); req(len(series)>=7,'cross-asset series coverage too thin')
for sid,s in series.items(): req(len(s.get('points',[]))>=10,f'{sid} too few 30D observations')
confirm=data.get('cross_asset_confirmation',{}); req(confirm.get('theme_id'),'cross-asset confirmation missing theme')
index=(ROOT/'docs/index.html').read_text(encoding='utf-8')
trends=(ROOT/'docs/trends.html').read_text(encoding='utf-8')
p0=(ROOT/'docs/assets/p0.js').read_text(encoding='utf-8')
tjs=(ROOT/'docs/assets/trends.js').read_text(encoding='utf-8')
css=(ROOT/'docs/assets/market-lens.css').read_text(encoding='utf-8')
builder=(ROOT/'scripts/build_market_lens.py').read_text(encoding='utf-8')
for token in ['30D Market Lens','Cross-Asset Confirmation','reader-bar']:
    req(token in index,f'index missing {token}')
for token in ['Overall Regime Ribbon','Six-Signal Matrix','Top Catalyst Map','Persistent Risk Themes','Cross-Asset Validation']:
    req(token in trends,f'trends missing {token}')
for phrase in ['离散状态，不使用黑箱综合分数','粗酒红下划线代表','六条信号与同一交易日对齐','横轴是日期，纵轴是稳定主题类别','衡量的是进入 Top 3 的持续性','每个资产独立小图','不等同于因果证明']:
    req(phrase not in trends,f'user-facing trends copy contains internal narration: {phrase}')
req('risk_score=' not in builder and 'cross-asset risk score' not in builder,'weighted regime score reintroduced')
req('source_mode' in p0 and 'source_mode' in tjs and '市场重建' in tjs,'provenance not exposed to frontend')
req('verified_event' in tjs and 'Verified Event' in tjs,'verified event provenance missing from frontend')
req('reader-bar' in css and '@media(max-width:900px)' in css,'mobile compact reader bar CSS missing')

workflow=(ROOT/'.github/workflows/daily-market-update.yml')
prompt=(ROOT/'prompts/global-market-daily-master.md')
generator=(ROOT/'scripts/generate_daily_update.py')
req(workflow.exists() and prompt.exists() and generator.exists(),'twice-daily publication automation files missing')
if workflow.exists():
    w=workflow.read_text(encoding='utf-8')
    for token in ['0 1 * * *','0 10 * * *','gpt-5.6-sol','xhigh','OPENAI_API_KEY']:
        req(token in w,f'daily automation missing {token}')
if prompt.exists():
    t=prompt.read_text(encoding='utf-8')
    req('morning' in t and 'close' in t and 'canonical daily archive' in t,'publication-cycle contract missing')

if errors:
    print('MARKET LENS GATE FAILED')
    for x in errors: print(' -',x)
    sys.exit(1)
print(f"MARKET LENS GATE PASSED — {len(days)} sessions, {data['coverage']['native_daily_days']} native, {data['coverage']['reconstructed_days']} reconstructed, {data['coverage'].get('verified_event_days',0)} verified-event days, {len(data['persistent_themes'])} lifecycle themes")
