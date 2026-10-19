#!/usr/bin/env python3
"""Offline, immutable publication checkpoints. No network or publishing capability.

A checkpoint preserves work; it is neither persistent storage nor permission to
retry a denied action. Existing repository Quality gates remain authoritative.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
import zipfile
from zoneinfo import ZoneInfo

REPOSITORY = 'patshin/global-market-daily'
MAX_FILE_BYTES = 8 * 1024 * 1024
SGT = ZoneInfo('Asia/Singapore')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def paths_for(day: str) -> list[str]:
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError('date must be canonical YYYY-MM-DD')
    return [f'docs/data/daily/{day}.json',
            f'docs/reports/{day[:4]}/{day[5:7]}/{day}.md',
            f'docs/data/sources/{day}.json',
            'docs/data/archive.json', 'docs/data/latest.json']


def read_safe(root: Path, relative: str) -> bytes | None:
    path = root
    for component in Path(relative).parts:
        path = path / component
        if path.is_symlink():
            raise ValueError(f'symlink not allowed: {relative}')
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f'not a bounded regular file: {relative}')
    data = path.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f'file grew beyond size limit: {relative}')
    data.decode('utf-8')
    return data


def inspect_bundle(files: dict[str, bytes], day: str) -> dict[str, Any]:
    """Basic recovery diagnostics only, never a substitute for Quality."""
    expected = paths_for(day)
    errors = [f'missing: {p}' for p in expected if p not in files]
    decoded: dict[str, Any] = {}
    for p, data in files.items():
        if p.endswith('.json'):
            try:
                decoded[p] = json.loads(data)
            except (ValueError, UnicodeError):
                errors.append(f'invalid JSON: {p}')
    report = decoded.get(expected[0])
    parity = {'passed': 0, 'required': 25, 'status': 'NOT_CHECKED'}
    if isinstance(report, dict) and expected[1] in files:
        try:
            literals = [report['data_cutoff_sgt'], report['data_cutoff_et'],
                        report['thesis'], report['dominant_narrative']]
            order = report['section_order']
            cats, risks = report['top_catalysts'], report['top_risks']
            assert len(order) == 15 and len(set(order)) == 15
            assert len(cats) == 3 and len(risks) == 3
            literals += [report['sections'][k]['title'] for k in order]
            literals += [x['event'] for x in cats] + [x['risk'] for x in risks]
            md = files[expected[1]].decode('utf-8')
            passed = sum(isinstance(x, str) and bool(x) and x in md for x in literals)
            parity = {'passed': passed, 'required': 25,
                      'status': 'PASS' if passed == 25 else 'FAIL'}
        except (KeyError, TypeError, AssertionError):
            parity['status'] = 'FAIL'
        if parity['status'] != 'PASS':
            errors.append('canonical literals must match 25/25')
        if report.get('date') != day:
            errors.append('daily date mismatch')
    elif expected[0] in files:
        errors.append('daily object or Markdown unavailable')
    latest = decoded.get(expected[4])
    if isinstance(latest, dict):
        wanted = dict(zip(('daily_json_path', 'report_path', 'sources_path'),
                          [p.removeprefix('docs/') for p in expected[:3]]))
        if latest.get('date') != day or any(latest.get(k) != v for k, v in wanted.items()):
            errors.append('latest date or canonical paths mismatch')
    archive = decoded.get(expected[3])
    if isinstance(archive, dict):
        entries = archive.get('entries')
        if not isinstance(entries, list) or sum(isinstance(e, dict) and e.get('date') == day for e in entries) != 1:
            errors.append('archive must contain exactly one same-date entry')
    return {'scope': 'STRUCTURAL_DIAGNOSTICS_ONLY', 'errors': errors,
            'canonical_parity': parity, 'quality_parity': 'NOT_RUN',
            'chromium': 'NOT_RUN'}


def verify_checkpoint(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('duplicate ZIP entries')
        if z.getinfo('manifest.json').file_size > 1024 * 1024:
            raise ValueError('oversized manifest')
        manifest = json.loads(z.read('manifest.json'))
        if manifest.get('repository') != REPOSITORY:
            raise ValueError('repository mismatch')
        allowed = set(paths_for(manifest['date']))
        records = manifest['files']
        if not isinstance(records, dict) or not set(records) <= allowed:
            raise ValueError('unexpected payload path')
        if set(z.namelist()) != {'manifest.json', *records}:
            raise ValueError('unexpected ZIP members')
        payloads = {}
        for name, record in records.items():
            info = z.getinfo(name)
            if info.file_size > MAX_FILE_BYTES or info.file_size != record['bytes']:
                raise ValueError(f'payload size mismatch: {name}')
            payloads[name] = z.read(name)
            if digest(payloads[name]) != record['sha256']:
                raise ValueError(f'payload digest mismatch: {name}')
        identity = {'repository': REPOSITORY, 'date': manifest['date'],
                    'base_main_sha': manifest['base_main_sha'], 'files': records}
        if digest(json.dumps(identity, sort_keys=True).encode()) != manifest['bundle_id']:
            raise ValueError('manifest identity mismatch')
        # Recompute rather than trusting a stored diagnostics claim.
        if inspect_bundle(payloads, manifest['date']) != manifest['diagnostics']:
            raise ValueError('diagnostics mismatch')
        return manifest


def pack(root: Path, day: str, base_main_sha: str, out: Path) -> Path:
    if not re.fullmatch(r'[0-9a-f]{40}', base_main_sha):
        raise ValueError('a verified 40-character main commit SHA is required')
    root = root.resolve(strict=True)
    files = {p: data for p in paths_for(day) if (data := read_safe(root, p)) is not None}
    records = {p: {'bytes': len(data), 'sha256': digest(data)} for p, data in files.items()}
    identity = {'repository': REPOSITORY, 'date': day, 'base_main_sha': base_main_sha, 'files': records}
    bundle_id = digest(json.dumps(identity, sort_keys=True).encode())
    diagnostics = inspect_bundle(files, day)
    manifest = {**identity, 'schema_version': '1.0.0', 'bundle_id': bundle_id,
                'created_at_sgt': datetime.now(SGT).isoformat(timespec='seconds'),
                'storage_status': 'LOCAL_ONLY_PERSISTENT_SAVE_NOT_CONFIRMED',
                'publication_status': 'NOT_SUBMITTED',
                'content_complete': len(files) == 5, 'diagnostics': diagnostics,
                'notice': 'Private recovery artifact. Not a Quality pass, approval, or permission to retry a denied action.'}
    out.mkdir(parents=True, exist_ok=True)
    target = out / f'GMD-{day}-{bundle_id}.zip'
    if target.exists():
        verify_checkpoint(target)
        return target
    fd, tmp = tempfile.mkstemp(prefix='.gmd-checkpoint-', suffix='.zip', dir=out)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
            for name, data in files.items():
                z.writestr(name, data)
        verify_checkpoint(Path(tmp))
        # Exclusive link: concurrent identical packs cannot overwrite each other.
        try:
            os.link(tmp, target)
        except FileExistsError:
            verify_checkpoint(target)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return target


def classify_failure(message: str, http_status: int | None = None) -> dict[str, Any]:
    text = message.casefold()
    if any(x in text for x in ('safety checks', 'safety status', 'explicit safety block')):
        kind, action = 'SAFETY_BLOCKED', 'STOP_EXTERNAL_WRITES_AND_ESCALATE'
    elif http_status in (401, 403) or any(x in text for x in ('permission denied', 'bad credentials', 'not authorized')):
        kind, action = 'PERMISSION_DENIED', 'REVIEW_PROVIDER_AUTHORIZATION'
    elif any(x in text for x in ('approval required', 'awaiting approval')):
        kind, action = 'APPROVAL_REQUIRED', 'USE_SUPPORTED_APPROVAL_FLOW'
    elif http_status in (408, 429, 502, 503, 504) or any(x in text for x in ('timed out', 'connection reset', 'could not resolve host')):
        kind, action = 'TRANSIENT_CONNECTION', 'READ_BACK_BEFORE_ONE_ORDINARY_RETRY'
    else:
        kind, action = 'UNKNOWN_FAILURE', 'READ_BACK_AND_DIAGNOSE_NO_AUTOMATIC_RETRY'
    return {'classification': kind, 'next_action': action,
            'automatic_retry': False, 'alternate_transport_allowed': False}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('pack'); a.add_argument('--root', type=Path, required=True)
    a.add_argument('--date', required=True); a.add_argument('--base-main-sha', required=True)
    a.add_argument('--out', type=Path, required=True)
    a = sub.add_parser('verify'); a.add_argument('checkpoint', type=Path)
    a = sub.add_parser('classify'); a.add_argument('--error-file', type=Path, required=True)
    a.add_argument('--http-status', type=int)
    args = p.parse_args()
    if args.command == 'pack':
        result = {'checkpoint_path': str(pack(args.root, args.date, args.base_main_sha, args.out)),
                  'persistent_save': 'NOT_CONFIRMED', 'publication': 'NOT_SUBMITTED'}
    elif args.command == 'verify':
        result = verify_checkpoint(args.checkpoint)
    else:
        result = classify_failure(args.error_file.read_text(), args.http_status)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
