#!/usr/bin/env python3
"""Extra honesty and no-look-ahead gates for retrospective editions only."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1]

def check_report(report,source_doc,archive_dates):
    errors=[];recon=report.get('reconstruction') or {};day=report.get('date','')
    if not recon.get('is_reconstructed'):return errors
    def require(ok,msg):
        if not ok:errors.append(f'{day}: {msg}')
    cutoff=datetime.strptime(report['data_cutoff_sgt'],'%Y-%m-%d %H:%M SGT').replace(tzinfo=ZoneInfo('Asia/Singapore'))
    try:
        built=datetime.fromisoformat(recon['reconstructed_at'].replace('Z','+00:00'))
        require(built.tzinfo is not None and built>=cutoff,'reconstruction timestamp must be real, timezone-aware and after historical cutoff')
    except (KeyError,ValueError,TypeError):require(False,'invalid reconstruction timestamp')
    historic=recon.get('historical_cutoff_sgt','')
    if historic.endswith('SGT'):
        historical=datetime.strptime(historic,'%Y-%m-%d %H:%M SGT').replace(tzinfo=ZoneInfo('Asia/Singapore'))
    else:
        historical=datetime.fromisoformat(historic.replace('Z','+00:00'))
    require(historical==cutoff,'historical cutoff mismatch')
    require(isinstance(recon.get('limitations'),list) and bool(recon['limitations']),'evidence limitations required')
    cycle=report.get('publication_cycle') or {}
    require(cycle.get('market_lens_native_eligible') is False,'historical reconstruction must never be native eligible')
    require(report.get('source_mode')=='reconstructed_daily','source_mode must expose retrospective provenance')
    require(('reconstruction' in str(report.get('edition','')).lower()) or '补档' in str(report.get('edition','')),'edition must disclose reconstruction')
    require((day in archive_dates)==(cycle.get('is_final') is True),'archive must agree with final/provisional status')
    for source in source_doc.get('sources',[]):
        available=source.get('available_by_utc')
        published=source.get('published_at')
        if not available and isinstance(published,str) and 'T' in published:
            available=published
        if available:
            try:
                dt=datetime.fromisoformat(available.replace('Z','+00:00'))
                require(dt.tzinfo is not None and dt<=cutoff,f"source {source.get('id')} was not available by historical cutoff")
            except (TypeError,ValueError):require(False,f"source {source.get('id')} has invalid available_by_utc")
    for item in report.get('market_tape',[]):
        recovered=item.get('recovery_observation') or {}
        if recovered:
            require(recovered.get('session_date','')<day,f"{item.get('asset')} uses same-day/later US close")
            require(recovered.get('original_snapshot_recovered') is False,'historical series must not claim original SGT snapshot')
            for key in ('level','change_1d','change_5d'):
                val=recovered.get(key)
                require(val is None or isinstance(val,(int,float)) and not isinstance(val,bool) and math.isfinite(val),f'{item.get("asset")} {key} must be finite or explicitly missing')
    return errors

if __name__=='__main__':
    archive=json.loads((ROOT/'docs/data/archive.json').read_text());dates={e['date'] for e in archive['entries']};errors=[];count=0
    for path in sorted((ROOT/'docs/data/daily').glob('*.json')):
        report=json.loads(path.read_text())
        if (report.get('reconstruction') or {}).get('is_reconstructed'):
            count+=1;source=json.loads((ROOT/'docs'/report['sources_path']).read_text());errors.extend(check_report(report,source,dates))
    if errors:print('RECONSTRUCTION GATE FAILED\n'+'\n'.join(errors));raise SystemExit(1)
    print(f'RECONSTRUCTION GATE PASSED — {count} historical editions with distinct provenance')
