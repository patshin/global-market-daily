#!/usr/bin/env python3
"""Render a candidate in real Chromium. Failures retain DOM/stderr diagnostics."""
from __future__ import annotations
import functools
import http.server
import json
import os
from pathlib import Path
from html.parser import HTMLParser
import shutil
import subprocess
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
class Probe(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root={};self.nodes={};self.texts={};self.stack=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='html':self.root=attrs
        node_id=attrs.get('id')
        if node_id:self.nodes[node_id]=attrs;self.texts[node_id]=[]
        if tag not in VOID:self.stack.append((tag,node_id))
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                del self.stack[i:];break
    def handle_data(self,data):
        for _,node_id in self.stack:
            if node_id:self.texts[node_id].append(data)
    def text(self,node_id):return ''.join(self.texts.get(node_id,[])).strip()


def check_dom(html,latest,report,lens,route,label):
    probe=Probe();probe.feed(html)
    if not route:
        assert latest['date'] in probe.text('edition-title'),(label,'visible edition date mismatch')
        assert probe.text('thesis')==latest['thesis'],(label,'visible canonical thesis mismatch')
        assert 'report-shell' in probe.nodes and 'hidden' not in probe.nodes['report-shell']
        assert 'error-state' in probe.nodes and 'hidden' in probe.nodes['error-state']
        for key,value in {'data-gmd-editorial-ready':'true','data-gmd-signal-count':'6',
                          'data-gmd-signal-facts-distinct':'true','data-gmd-horizontal-overflow':'false'}.items():
            assert probe.root.get(key)==value,(label,key,probe.root)
        assert probe.root.get('data-gmd-watch-count') in {'2','3'}
        if (report.get('reconstruction') or {}).get('is_reconstructed'):
            assert '历史补档' in html and '并非当日发布' in html
    else:
        assert f'As of {lens["as_of"]}' in html
        assert '30D Lens data unavailable:' not in html
        if lens['days'][-1].get('data_quality',{}).get('status')=='partial':assert '数据待齐' in html


def main():
    browser=next((shutil.which(x) for x in ('google-chrome','chromium','chromium-browser') if shutil.which(x)),None)
    assert browser,'Chromium is required for candidate browser verification'
    latest=json.loads((ROOT/'docs/data/latest.json').read_text(encoding='utf-8'))
    report=json.loads((ROOT/'docs'/latest['daily_json_path']).read_text(encoding='utf-8'))
    lens=json.loads((ROOT/'docs/data/trends/rolling-30d.json').read_text(encoding='utf-8'))
    output=Path(os.environ.get('GMD_BROWSER_ARTIFACTS','/tmp/gmd-browser-artifacts'))
    output.mkdir(parents=True,exist_ok=True)
    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT/'docs'))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        for name,size in [('desktop','1440,1200'),('mobile','390,844')]:
            for route in ['', 'trends.html']:
                label=f'{name}-{route or "index"}'
                with tempfile.TemporaryDirectory(prefix='gmd-chromium-') as profile:
                    command=[browser,'--headless=new','--no-sandbox','--disable-gpu','--disable-dev-shm-usage',
                             '--no-first-run','--no-default-browser-check',f'--user-data-dir={profile}',
                             '--force-device-scale-factor=1',f'--window-size={size}',
                             '--virtual-time-budget=15000','--dump-dom',base+'/'+route]
                    start=time.monotonic();stdout='';stderr='';returncode=None;status='FAILED';failure=None
                    try:
                        result=subprocess.run(command,text=True,capture_output=True,timeout=60)
                        stdout,stderr,returncode=result.stdout,result.stderr,result.returncode
                        assert returncode==0,(label,stderr)
                        check_dom(stdout,latest,report,lens,route,label)
                        status='PASS'
                    except subprocess.TimeoutExpired as exc:
                        def decode(value):return value.decode('utf-8',errors='replace') if isinstance(value,bytes) else (value or '')
                        stdout,stderr=decode(exc.stdout),decode(exc.stderr)
                        status='CHROMIUM_TIMEOUT';failure=str(exc)
                        raise
                    except Exception as exc:
                        failure=repr(exc)
                        raise
                    finally:
                        (output/f'{label}.html').write_text(stdout,encoding='utf-8')
                        (output/f'{label}.stderr.log').write_text(stderr,encoding='utf-8')
                        (output/f'{label}.result.json').write_text(json.dumps({'status':status,'returncode':returncode,
                            'duration_seconds':round(time.monotonic()-start,3),'route':route,'viewport':size,
                            'expected_date':latest['date'],'error':failure},indent=2)+'\n',encoding='utf-8')
                    print(f'CANDIDATE BROWSER PASSED {label}')
    finally:
        server.shutdown();server.server_close();worker.join(timeout=2)
    return 0

if __name__=='__main__':raise SystemExit(main())
