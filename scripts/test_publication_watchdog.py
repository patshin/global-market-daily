#!/usr/bin/env python3
"""A delayed/missing lens must not masquerade as missing editorial research."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp); data=root/'docs/data';(data/'daily').mkdir(parents=True)
    day='2026-09-24'
    source=json.loads((ROOT/f'docs/data/daily/{day}.json').read_text())
    source['publication_cycle']={'cycle':'close','is_final':True,'archive_eligible':True,'market_lens_native_eligible':True}
    (data/f'daily/{day}.json').write_text(json.dumps(source))
    (data/'latest.json').write_text(json.dumps({'date':day,'daily_json_path':f'data/daily/{day}.json'}))
    (data/'archive.json').write_text(json.dumps({'entries':[{'date':day}]}))
    command=[sys.executable,str(ROOT/'scripts/verify_scheduled_publication.py'),'--root',str(root),'--date',day,'--cycle','close']
    assert subprocess.run(command,capture_output=True).returncode==0
    assert subprocess.run(command+['--require-lens'],capture_output=True).returncode!=0
    (data/'trends').mkdir();(data/'trends/rolling-30d.json').write_text('{')
    assert subprocess.run(command,capture_output=True).returncode==0
    assert subprocess.run(command+['--require-lens'],capture_output=True).returncode!=0
    # Under the new policy actual morning editions are final/native, backfills final/nonnative.
    day='2026-10-08';source['date']=day;source['publication_cycle']={'cycle':'morning','is_final':True,'archive_eligible':True,'market_lens_native_eligible':True}
    (data/f'daily/{day}.json').write_text(json.dumps(source))
    (data/'latest.json').write_text(json.dumps({'date':day,'daily_json_path':f'data/daily/{day}.json'}))
    (data/'archive.json').write_text(json.dumps({'entries':[{'date':day}]}))
    (data/'trends/rolling-30d.json').write_text(json.dumps({'days':[{'date':day,'source_mode':'native_daily'}]}))
    command=[sys.executable,str(ROOT/'scripts/verify_scheduled_publication.py'),'--root',str(root),'--date',day,'--cycle','morning','--require-lens']
    assert subprocess.run(command,capture_output=True).returncode==0
    source['reconstruction']={'is_reconstructed':True};source['publication_cycle']['market_lens_native_eligible']=False
    (data/f'daily/{day}.json').write_text(json.dumps(source))
    assert subprocess.run(command,capture_output=True).returncode!=0
    (data/'trends/rolling-30d.json').write_text(json.dumps({'days':[{'date':day,'source_mode':'reconstructed_daily'}]}))
    assert subprocess.run(command,capture_output=True).returncode==0
    source['publication_cycle']['is_final']=False;(data/f'daily/{day}.json').write_text(json.dumps(source))
    assert subprocess.run(command,capture_output=True).returncode!=0
print('PUBLICATION WATCHDOG REGRESSION PASSED — missing and corrupt lens separated from core publication')
