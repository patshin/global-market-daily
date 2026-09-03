#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
errors=[]
def req(cond,msg):
    if not cond: errors.append(msg)
try: data=json.loads((ROOT/'docs/data/trends/rolling-30d.json').read_text(encoding='utf-8'))
except Exception as e:
    print('MARKET LENS GATE FAILED'); print(e); sys.exit(1)
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
        req(c.get('source_mode')==d.get('source_mode'),f'day {i} catalyst {j} provenance mismatch')
req(len(data.get('persistent_themes',[]))>=5,'persistent theme lifecycle too thin')
series=data.get('series',{}); req(len(series)>=7,'cross-asset series coverage too thin')
for sid,s in series.items(): req(len(s.get('points',[]))>=10,f'{sid} too few 30D observations')
confirm=data.get('cross_asset_confirmation',{}); req(confirm.get('theme_id'),'cross-asset confirmation missing theme')
index=(ROOT/'docs/index.html').read_text(encoding='utf-8')
trends=(ROOT/'docs/trends.html').read_text(encoding='utf-8')
p0=(ROOT/'docs/assets/p0.js').read_text(encoding='utf-8')
tjs=(ROOT/'docs/assets/trends.js').read_text(encoding='utf-8')
css=(ROOT/'docs/assets/market-lens.css').read_text(encoding='utf-8')
for token in ['30D Market Lens','Cross-Asset Confirmation','reader-bar']:
    req(token in index,f'index missing {token}')
for token in ['Overall Regime Ribbon','Six-Signal Matrix','Top Catalyst Map','Persistent Risk Themes','Cross-Asset Validation']:
    req(token in trends,f'trends missing {token}')
req('source_mode' in p0 and 'source_mode' in tjs and 'Market Reconstruction' in p0 and 'Market Reconstruction' in tjs,'provenance not exposed to frontend')
req('reader-bar' in css and '@media(max-width:900px)' in css,'mobile compact reader bar CSS missing')
if errors:
    print('MARKET LENS GATE FAILED')
    for x in errors: print(' -',x)
    sys.exit(1)
print(f"MARKET LENS GATE PASSED — {len(days)} sessions, {data['coverage']['native_daily_days']} native, {data['coverage']['reconstructed_days']} reconstructed, {len(data['persistent_themes'])} lifecycle themes")
