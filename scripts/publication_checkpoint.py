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
from urllib.parse import urlsplit
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
    # Preserve invalid UTF-8 bytes for diagnostics; never mark them publishable.
    return data


def inspect_bundle(files: dict[str, bytes], day: str) -> dict[str, Any]:
    """Fail-closed recovery diagnostics, not the full repository Quality gate."""
    expected = paths_for(day)
    errors = [f'missing: {p}' for p in expected if p not in files]
    decoded: dict[str, Any] = {}
    texts: dict[str, str] = {}
    for path, data in files.items():
        try:
            texts[path] = data.decode('utf-8')
        except UnicodeError:
            errors.append(f'invalid UTF-8: {path}')
            continue
        if path.endswith('.json'):
            try:
                decoded[path] = json.loads(texts[path])
            except ValueError:
                errors.append(f'invalid JSON: {path}')
                continue
            if not isinstance(decoded[path], dict):
                errors.append(f'JSON root must be an object: {path}')
    report = decoded.get(expected[0])
    parity = {'passed': 0, 'required': 25, 'status': 'NOT_CHECKED'}
    if isinstance(report, dict) and expected[1] in texts:
        try:
            literals = [report['data_cutoff_sgt'], report['data_cutoff_et'],
                        report['thesis'], report['dominant_narrative']]
            order = report['section_order']
            cats, risks = report['top_catalysts'], report['top_risks']
            assert isinstance(order, list) and len(order) == 15 and len(set(order)) == 15
            assert isinstance(cats, list) and len(cats) == 3
            assert isinstance(risks, list) and len(risks) == 3
            titles = [report['sections'][key]['title'] for key in order]
            literals += titles + [x['event'] for x in cats] + [x['risk'] for x in risks]
            md = texts[expected[1]]
            passed = sum(isinstance(x, str) and bool(x) and x in md for x in literals)
            parity = {'passed': passed, 'required': 25,
                      'status': 'PASS' if passed == 25 else 'FAIL'}
            cursor = 0
            for title in titles:
                position = md.find(title, cursor) if isinstance(title, str) else -1
                if position < 0:
                    errors.append('canonical section titles must appear in order')
                    break
                cursor = position + len(title)
        except (KeyError, TypeError, AssertionError):
            parity['status'] = 'FAIL'
        if parity['status'] != 'PASS':
            errors.append('canonical literals must match 25/25')
        if report.get('date') != day:
            errors.append('daily date mismatch')
        if report.get('sources_path') != expected[2].removeprefix('docs/'):
            errors.append('daily sources_path mismatch')
    elif expected[0] in files:
        errors.append('daily object or Markdown unavailable')

    archive = decoded.get(expected[3])
    archive_dates: list[str] = []
    if isinstance(archive, dict):
        entries = archive.get('entries')
        if not isinstance(entries, list):
            errors.append('archive entries must be an array')
            entries = []
        for entry in entries:
            value = entry.get('date') if isinstance(entry, dict) else None
            try:
                if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
                    raise ValueError('date')
                archive_dates.append(value)
            except ValueError:
                errors.append('archive entry must be an object with a canonical date')
        if archive_dates.count(day) != 1:
            errors.append('archive must contain exactly one same-date entry')
        if len(set(archive_dates)) != len(archive_dates):
            errors.append('archive contains duplicate dates')
        if archive_dates != sorted(archive_dates, reverse=True):
            errors.append('archive dates must be newest first')

    latest = decoded.get(expected[4])
    if isinstance(latest, dict):
        latest_day = latest.get('date')
        try:
            if not isinstance(latest_day, str):
                raise ValueError('date')
            latest_paths = paths_for(latest_day)
            wanted = dict(zip(('daily_json_path', 'report_path', 'sources_path'),
                              [p.removeprefix('docs/') for p in latest_paths[:3]]))
            if latest_day < day or any(latest.get(k) != v for k, v in wanted.items()):
                errors.append('latest date or canonical paths mismatch')
            if archive_dates and (latest_day not in archive_dates or latest_day != max(archive_dates)):
                errors.append('latest must match the newest formal archive date')
        except ValueError:
            errors.append('latest requires a canonical date')

    source_doc = decoded.get(expected[2])
    ids: list[str] = []
    if isinstance(source_doc, dict):
        if source_doc.get('date') != day:
            errors.append('sources date mismatch')
        records = source_doc.get('sources')
        if not isinstance(records, list) or not records:
            errors.append('sources must be a non-empty array')
            records = []
        for source in records:
            if not isinstance(source, dict):
                errors.append('source record must be an object')
                continue
            source_id = source.get('id')
            if not isinstance(source_id, str) or not re.fullmatch(r'S\d{2,}', source_id):
                errors.append('source ID must look like S01')
            else:
                ids.append(source_id)
            url = source.get('source_url')
            try:
                parsed = urlsplit(url) if isinstance(url, str) else None
                if url is not None and (not parsed or parsed.scheme != 'https' or not parsed.hostname or '{{' in url):
                    errors.append('source URL must be resolved HTTPS or explicit null')
            except ValueError:
                errors.append('source URL is malformed')
        if len(set(ids)) != len(ids):
            errors.append('duplicate source IDs')
        valid_ids = set(ids)
        def check_refs(value: Any) -> None:
            if isinstance(value, list):
                for item in value:
                    check_refs(item)
            elif isinstance(value, dict):
                for key, child in value.items():
                    if key == 'sources':
                        if not isinstance(child, list):
                            errors.append('source references must be an array')
                        else:
                            for source_id in child:
                                if not isinstance(source_id, str) or source_id not in valid_ids:
                                    errors.append(f'unresolved source ID: {source_id}')
                    else:
                        check_refs(child)
        check_refs(report)
    return {'scope': 'STRUCTURAL_DIAGNOSTICS_ONLY', 'errors': list(dict.fromkeys(errors)),
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
        if 'diagnostics_version' in manifest:
            identity['diagnostics_version'] = manifest['diagnostics_version']
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
    identity = {'repository': REPOSITORY, 'date': day, 'base_main_sha': base_main_sha, 'files': records,
                'diagnostics_version': '2.0'}
    bundle_id = digest(json.dumps(identity, sort_keys=True).encode())
    diagnostics = inspect_bundle(files, day)
    manifest = {**identity, 'schema_version': '2.0.0', 'bundle_id': bundle_id,
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


def classify_failure(message: str, http_status: int | None = None, stage: str | None = None) -> dict[str, Any]:
    text = message.casefold()
    if any(x in text for x in ('safety checks', 'safety status', 'explicit safety block')):
        kind, action = 'SAFETY_BLOCKED', 'STOP_EXTERNAL_WRITES_AND_ESCALATE'
    elif stage in ('quality', 'preflight', 'chromium'):
        kind, action = 'QUALITY_FAILED', 'PRESERVE_EVIDENCE_AND_FIX_CANDIDATE'
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
    a.add_argument('--stage', choices=('research', 'write', 'pr', 'quality', 'preflight', 'chromium'))
    args = p.parse_args()
    if args.command == 'pack':
        result = {'checkpoint_path': str(pack(args.root, args.date, args.base_main_sha, args.out)),
                  'persistent_save': 'NOT_CONFIRMED', 'publication': 'NOT_SUBMITTED'}
    elif args.command == 'verify':
        result = verify_checkpoint(args.checkpoint)
    else:
        result = classify_failure(args.error_file.read_text(), args.http_status, args.stage)
    if args.command == 'pack':
        metadata = verify_checkpoint(Path(result['checkpoint_path']))
        result['content_complete'] = metadata['content_complete']
        result['diagnostics'] = metadata['diagnostics']
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if args.command == 'pack' and result['diagnostics']['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
