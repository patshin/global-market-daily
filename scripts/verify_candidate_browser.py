#!/usr/bin/env python3
"""Render the actual candidate tree before merge using installed Chromium."""
import functools
import http.server
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1]
class Probe(HTMLParser):
    def __init__(self):super().__init__();self.root={};self.nodes={}
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='html':self.root=attrs
        if attrs.get('id'):self.nodes[attrs['id']]=attrs
browser=next((shutil.which(x) for x in ('google-chrome','chromium','chromium-browser') if shutil.which(x)),None)
assert browser,'Chromium is required for candidate browser verification'
handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT/'docs'))
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'
latest=json.loads((ROOT/'docs/data/latest.json').read_text())
output=Path(os.environ.get('GMD_BROWSER_ARTIFACTS','/tmp/gmd-browser-artifacts'));output.mkdir(parents=True,exist_ok=True)
try:
    for name,size in [('desktop','1440,1200'),('mobile','390,844')]:
        for route in ['', 'trends.html']:
            result=subprocess.run([browser,'--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--force-device-scale-factor=1',f'--window-size={size}','--virtual-time-budget=15000','--dump-dom',base+'/'+route],text=True,capture_output=True,timeout=60)
            assert result.returncode==0,result.stderr
            html=result.stdout;label=f'{name}-{route or "index"}'
            (output/f'{label}.html').write_text(html)
            probe=Probe();probe.feed(html)
            if not route:
                assert latest['date'] in html
                assert 'hidden' not in probe.nodes['report-shell']
                assert 'hidden' in probe.nodes['error-state']
                for k,v in {'data-gmd-editorial-ready':'true','data-gmd-signal-count':'6','data-gmd-signal-facts-distinct':'true','data-gmd-horizontal-overflow':'false'}.items():assert probe.root.get(k)==v,(label,k,probe.root)
                assert probe.root.get('data-gmd-watch-count') in {'2','3'}
                report=json.loads((ROOT/'docs'/latest['daily_json_path']).read_text())
                if (report.get('reconstruction') or {}).get('is_reconstructed'):assert '历史补档' in html and '并非当日发布' in html
            else:
                lens=json.loads((ROOT/'docs/data/trends/rolling-30d.json').read_text())
                assert f'As of {lens["as_of"]}' in html
                assert '30D Lens data unavailable:' not in html
                if lens['days'][-1].get('data_quality',{}).get('status')=='partial':assert '数据待齐' in html
            print(f'CANDIDATE BROWSER PASSED {label}')
finally:server.shutdown()
