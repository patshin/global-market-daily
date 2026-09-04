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

# Publication architecture contract:
# ChatGPT owns research/cadence and writes source-backed publication files.
# GitHub Actions only validate, derive deterministic trend data, and deploy Pages.
legacy_workflow=ROOT/'.github/workflows/daily-market-update.yml'
req(not legacy_workflow.exists(),'legacy API-key research scheduler must remain absent')
workflow_dir=ROOT/'.github/workflows'
active_workflows=list(workflow_dir.glob('*.yml')) + list(workflow_dir.glob('*.yaml'))
for wf in active_workflows:
    text=wf.read_text(encoding='utf-8')
    req('OPENAI_API_KEY' not in text,f'{wf.name}: Actions must not require OPENAI_API_KEY')
    req('api.openai.com' not in text,f'{wf.name}: Actions must not call OpenAI API directly')
for required in ['quality.yml','pages.yml','trends-refresh.yml']:
    req((workflow_dir/required).exists(),f'required validation/deployment workflow missing: {required}')

# The builder must explicitly ignore provisional morning reports as native daily history.
req("cycle.get('is_final') is False" in builder,
    'market-lens builder must skip publication_cycle.is_final=false reports')

# The latest live report may be provisional; formal archive remains official-only.
latest=json.loads((ROOT/'docs/data/latest.json').read_text(encoding='utf-8'))
latest_path=ROOT/'docs'/str(latest.get('daily_json_path',''))
if latest_path.exists():
    latest_report=json.loads(latest_path.read_text(encoding='utf-8'))
    cycle=latest_report.get('publication_cycle') or {}
    if cycle.get('is_final') is False:
        req(cycle.get('archive_eligible') is False,'provisional report must be archive_eligible=false')
        req(cycle.get('market_lens_native_eligible') is False,'provisional report must be market_lens_native_eligible=false')
        native_dates={d.get('date') for d in days if d.get('source_mode')=='native_daily'}
        req(latest_report.get('date') not in native_dates,
            'provisional latest edition leaked into native 30D history')

if errors:
    print('MARKET LENS GATE FAILED')
    for x in errors: print(' -',x)
    sys.exit(1)
print(f"MARKET LENS GATE PASSED — {len(days)} sessions, {data['coverage']['native_daily_days']} native, {data['coverage']['reconstructed_days']} reconstructed, {data['coverage'].get('verified_event_days',0)} verified-event days, {len(data['persistent_themes'])} lifecycle themes")
