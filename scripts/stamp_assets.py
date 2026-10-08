#!/usr/bin/env python3
"""Content-address static assets so returning readers receive matching new code."""
import argparse
import hashlib
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATTERN=re.compile(r'(?P<prefix>(?:src|href)=")(?P<path>assets/[^"?]+\.(?:js|css))(?:\?[^"\s]*)?(?P<suffix>")')
def stamp(html):
    def replace(m):
        digest=hashlib.sha256((ROOT/'docs'/m['path']).read_bytes()).hexdigest()[:12]
        return m['prefix']+m['path']+'?v='+digest+m['suffix']
    return PATTERN.sub(replace,html)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args();stale=[]
    for path in (ROOT/'docs/index.html',ROOT/'docs/trends.html'):
        before=path.read_text();after=stamp(before)
        if before!=after:
            if args.check:stale.append(str(path.relative_to(ROOT)))
            else:path.write_text(after)
    if stale:raise SystemExit('STALE ASSET URLS: '+', '.join(stale)+'; run python scripts/stamp_assets.py')
    print('ASSET CACHE CONTRACT PASSED' if args.check else 'Asset URLs stamped with current content hashes')
