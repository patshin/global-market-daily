#!/usr/bin/env python3
"""Offline regression coverage against the actual builder, including delayed releases."""
import contextlib
import importlib.util
import io
import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('builder', ROOT/'scripts/build_market_lens.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

def report(day, reconstructed=False, provisional=False):
    return {'date':day,'publication_cycle':{'is_final':not provisional},
            'reconstruction':{'is_reconstructed':reconstructed},
            'market_regime':{'overall':{'state':'Neutral'}},
            'top_catalysts':[{'rank':i,'event':f'Fed catalyst {i}','what_happened':'Fixture only'} for i in range(1,4)]}

assert builder.theme_from_text('Fed minutes retain restrictive outlook')=='fed_policy_path'
assert builder.theme_from_text('FOMC said policy remains restrictive')=='fed_policy_path'
assert builder.theme_from_text('Officials said the plan remains unchanged')!='ai_earnings'
assert builder.theme_from_text('AI服务器需求增长')=='ai_earnings'
assert builder.theme_from_text('Stocks traded higher')!='us_china_trade_controls'
assert builder.theme_from_text('Forward outlook toward rewards')!='geopolitics_energy'
with tempfile.TemporaryDirectory() as tmp:
    base=Path(tmp)
    builder.HISTORY_DIR=base/'history';builder.HISTORY_DIR.mkdir()
    builder.DAILY_DIR=base/'daily';builder.DAILY_DIR.mkdir()
    builder.OUT_DIR=base/'out';builder.OUT_DIR.mkdir()
    builder.VERIFIED_EVENTS_PATH=base/'events.json'
    builder.ARCHIVE_PATH=base/'archive.json'
    dates=[(date(2026,8,22)+timedelta(days=i)).isoformat() for i in range(40)]
    for sid in builder.SERIES:
        # Latest equity session precedes all other providers' last release.
        rows=dates if sid in {'NASDAQCOM','SP500'} else dates[:-1]
        (builder.HISTORY_DIR/f'{sid}.csv').write_text('observation_date,'+sid+'\n'+''.join(f'{day},{100+i}\n' for i,day in enumerate(rows)))
    for day,reconstructed,provisional in [(dates[15],False,False),(dates[25],False,False),(dates[26],True,False),(dates[27],False,True)]:
        (builder.DAILY_DIR/f'{day}.json').write_text(json.dumps(report(day,reconstructed,provisional)))
    builder.ARCHIVE_PATH.write_text(json.dumps({'entries':[{'date':d} for d in (dates[15],dates[25],dates[26])]}))
    with contextlib.redirect_stdout(io.StringIO()):builder.build(refresh=False)
    data=json.loads((builder.OUT_DIR/'rolling-30d.json').read_text())
    for theme in data['persistent_themes']:
        unique={d['date'] for d in data['days'] if any(c['theme_id']==theme['theme_id'] for c in d['catalysts'])}
        assert theme['days_in_top3']==len(unique)
    native=[d['date'] for d in data['days'] if d['source_mode']=='native_daily']
    assert native==[dates[15],dates[25]],native
    assert next(d for d in data['days'] if d['date']==dates[26])['source_mode']=='reconstructed_daily'
    assert next(d for d in data['days'] if d['date']==dates[27])['source_mode']=='objective_market_reconstruction'
    last=data['days'][-1]
    assert last['data_quality']['status']=='partial',last
    assert len(last['catalysts'])==2,last
    assert last['regime_code']=='unavailable',last
    assert last['signals']['rates']=='?' and last['signals']['liquidity']=='?'
    assert data['coverage']['native_daily_days']==2
    assert data['coverage']['reconstructed_daily_days']==1
    assert data['coverage']['partial_days']==1
    # Three ranked proxies do not mean full macro observation coverage.
    vix=builder.HISTORY_DIR/'VIXCLS.csv'
    vix.write_text(vix.read_text()+f'{dates[-1]},150\n')
    with contextlib.redirect_stdout(io.StringIO()):builder.build(refresh=False)
    last=json.loads((builder.OUT_DIR/'rolling-30d.json').read_text())['days'][-1]
    assert len(last['catalysts'])==3 and last['data_quality']['status']=='partial'
    assert last['regime_code']=='unavailable'
    # A historical editorial edition cannot borrow a later same-date cash close.
    latest_report=report(dates[-1],reconstructed=True)
    latest_report['market_tape']=[{'asset':'DXY','change_1d':'+1.0%'},{'asset':'Brent','change_1d':'+2.0%'}]
    (builder.DAILY_DIR/f'{dates[-1]}.json').write_text(json.dumps(latest_report))
    archived=json.loads(builder.ARCHIVE_PATH.read_text());archived['entries'].append({'date':dates[-1]});builder.ARCHIVE_PATH.write_text(json.dumps(archived))
    with contextlib.redirect_stdout(io.StringIO()):builder.build(refresh=False)
    confirmation=json.loads((builder.OUT_DIR/'rolling-30d.json').read_text())['cross_asset_confirmation']
    assert not confirmation['confirming'] and not confirmation['diverging']
print('MARKET LENS REGRESSION PASSED — native accumulation, provisional exclusion, historical provenance, delayed releases')
