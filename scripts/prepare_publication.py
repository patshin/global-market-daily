#!/usr/bin/env python3
"""Assemble five publication files OFFLINE from canonical content and a pinned base.

No credentials, research calls, network, Git writes, or PR creation. This does not
run Quality or authorize retrying a denied publication. Baseline hashes must be
obtained by the caller from the SAME current-main GitHub read.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Any
from publication_checkpoint import inspect_bundle, paths_for, read_safe


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def load_object(data: bytes, label: str) -> dict[str, Any]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'{label}: duplicate JSON key {key}')
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError(f'{label}: invalid JSON constant {value}')
    result = json.loads(data.decode('utf-8'), object_pairs_hook=pairs,
                        parse_constant=invalid_constant)
    if not isinstance(result, dict):
        raise ValueError(f'{label}: JSON root must be an object')
    return result


def canonical_day(value: Any) -> str:
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError('canonical YYYY-MM-DD required')
    return value


def index_entry(report: dict[str, Any]) -> dict[str, Any]:
    day = canonical_day(report['date'])
    cycle = report.get('publication_cycle') or {}
    if (report.get('edition_status') != 'official' or cycle.get('status') != 'official'
            or cycle.get('cycle') != 'morning' or cycle.get('is_final') is not True
            or cycle.get('archive_eligible') is not True):
        raise ValueError('only an explicit official/final morning is eligible')
    reconstructed = (report.get('reconstruction') or {}).get('is_reconstructed') is True
    if reconstructed:
        if (cycle.get('market_lens_native_eligible') is not False
                or report.get('source_mode') != 'reconstructed_daily'):
            raise ValueError('reconstructed provenance must remain nonnative')
    elif cycle.get('market_lens_native_eligible') is not True or report.get('source_mode') != 'native_daily':
        raise ValueError('contemporaneous provenance must be explicit; do not infer it')
    paths = paths_for(day)
    regime = report['market_regime']['overall']
    if isinstance(regime, dict):
        regime = regime.get('state')
    if not isinstance(regime, str) or not regime.strip():
        raise ValueError('market_regime.overall must provide a non-empty state label')
    entry = {
        'schema_version': report.get('schema_version', '1.1.0'), 'date': day,
        'thesis': report['thesis'], 'overall_regime': regime,
        'dominant_narrative': report['dominant_narrative'],
        'report_path': paths[1].removeprefix('docs/'),
        'daily_json_path': paths[0].removeprefix('docs/'),
        'sources_path': paths[2].removeprefix('docs/'),
        'edition': report['edition'], 'edition_status': 'official',
        'publication_cycle': 'morning', 'source_mode': report['source_mode'],
        'last_updated': report['last_updated'],
    }
    # Carry historical markers without guessing or silently upgrading provenance.
    if reconstructed:
        entry['reconstruction'] = deepcopy(report['reconstruction'])
    return entry


def render_markdown(report: dict[str, Any], source_doc: dict[str, Any]) -> bytes:
    """Deterministic full-field representation; no paraphrasing canonical literals."""
    lines = [f'# {report["date"]} · {report["edition"]}', '',
             report['data_cutoff_sgt'], '', report['data_cutoff_et'], '',
             '## Investment Thesis', '', report['thesis'], '',
             '## Dominant Market Narrative', '', report['dominant_narrative'], '']
    def render(value: Any, depth: int = 3) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lines.extend([f'{"#" * min(depth, 6)} {key}', ''])
                render(child, depth + 1)
        elif isinstance(value, list):
            for item in value:
                render(item, depth)
        elif value is not None:
            lines.extend([str(value), ''])
    if (report.get('reconstruction') or {}).get('is_reconstructed'):
        lines.extend(['> 历史补档；并非当日发布。保留历史信息截止及重建证据限制。', ''])
    for key in ('run_timing', 'reconstruction', 'market_regime', 'market_tape',
                'market_tape_data_quality', 'what_changed', 'top_catalysts',
                'signal_panel', 'scenario_matrix', 'upcoming_market_watch',
                'top_risks', 'next_catalyst', 'asia_snapshot'):
        if key in report:
            lines.extend([f'## {key}', '']); render(report[key])
    for key in report['section_order']:
        section = report['sections'][key]
        lines.extend([f'## {section["title"]}', ''])
        render({k: v for k, v in section.items() if k != 'title'})
    lines.extend(['## Sources', '']); render(source_doc)
    return ('\n'.join(lines).rstrip() + '\n').encode('utf-8')


def assemble(daily_bytes: bytes, source_bytes: bytes, archive_bytes: bytes,
             latest_bytes: bytes, *, base_main_sha: str, archive_blob_sha: str,
             latest_blob_sha: str, markdown_bytes: bytes | None = None) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Pure assembly. All facts and original research timestamps are immutable."""
    for label, sha in [('main', base_main_sha), ('archive', archive_blob_sha), ('latest', latest_blob_sha)]:
        if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}', sha):
            raise ValueError(f'{label}: verified 40-character SHA required')
    for label, data, sha in [('archive', archive_bytes, archive_blob_sha), ('latest', latest_bytes, latest_blob_sha)]:
        if git_blob_sha(data) != sha:
            raise ValueError(f'{label}: current-main blob hash mismatch; do not reconstruct from snippets')
    report = load_object(daily_bytes, 'daily')
    sources = load_object(source_bytes, 'sources')
    archive = load_object(archive_bytes, 'archive')
    latest = load_object(latest_bytes, 'latest')
    day = canonical_day(report['date'])
    latest_day = canonical_day(latest.get('date'))
    entries = archive.get('entries')
    if not isinstance(entries, list) or not entries:
        raise ValueError('existing formal archive must be a non-empty array')
    dates = [canonical_day(e.get('date')) if isinstance(e, dict) else canonical_day(None) for e in entries]
    if len(set(dates)) != len(dates) or dates != sorted(dates, reverse=True):
        raise ValueError('baseline archive dates must be unique and descending')
    if latest_day != dates[0]:
        raise ValueError('baseline latest does not match newest archive')
    if day in dates:
        raise ValueError('ALREADY_ARCHIVED: do not replace an existing official edition; review separately')
    new_entry = index_entry(report)
    new_archive = deepcopy(archive)
    archive_entry = {k: v for k, v in new_entry.items() if k != 'schema_version'}
    new_archive['entries'] = sorted([archive_entry, *entries], key=lambda e: e['date'], reverse=True)
    # No artificial "now" enters the canonical report or archive timing.
    new_archive['updated_at'] = max(str(archive.get('updated_at', '')), str(report['last_updated']))
    new_latest_bytes = json_bytes(new_entry) if day > latest_day else latest_bytes
    names = paths_for(day)
    payload = dict(zip(names, [daily_bytes, markdown_bytes if markdown_bytes is not None else render_markdown(report, sources),
                              source_bytes, json_bytes(new_archive), new_latest_bytes]))
    diagnostics = inspect_bundle(payload, day)
    if diagnostics['errors']:
        raise ValueError('candidate structural errors: ' + '; '.join(diagnostics['errors'][:12]))
    receipt = {'status': 'ASSEMBLED_NOT_QUALITY_VALIDATED', 'base_main_sha': base_main_sha,
               'baseline_archive_blob_sha': archive_blob_sha, 'baseline_latest_blob_sha': latest_blob_sha,
               'date': day, 'latest_date': max(day, latest_day),
               'original_archive_entries_preserved': len(entries), 'canonical_parity': diagnostics['canonical_parity'],
               'quality_parity': 'NOT_RUN', 'chromium': 'NOT_RUN', 'publication': 'NOT_SUBMITTED',
               'files': {p: {'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest(), 'git_blob_sha': git_blob_sha(b)} for p,b in payload.items()}}
    return payload, receipt


def write_new_tree(files: dict[str, bytes], destination: Path) -> None:
    """Private staging only; exclusive destination and cleanup on any partial failure."""
    daily_paths = [p for p in files if re.fullmatch(r'docs/data/daily/\d{4}-\d{2}-\d{2}\.json', p)]
    if len(daily_paths) != 1 or set(files) != set(paths_for(Path(daily_paths[0]).stem)):
        raise ValueError('only the canonical five-file allowlist may be staged')
    destination = destination.absolute()
    for parent in [destination, *destination.parents]:
        if parent.is_symlink():
            raise ValueError('symlink destination is not allowed')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Reserve exclusively. Never replace a user's existing worktree.
    destination.mkdir(mode=0o700, exist_ok=False)
    try:
        for name, data in files.items():
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        if {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()} != set(files):
            raise ValueError('staging file set mismatch')
    except BaseException:
        shutil.rmtree(destination)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('daily', 'sources', 'baseline-root', 'out-root'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--markdown', type=Path)
    for option in ('base-main-sha', 'archive-blob-sha', 'latest-blob-sha'):
        parser.add_argument('--' + option, required=True)
    args = parser.parse_args()
    def bounded(path: Path) -> bytes:
        data = read_safe(path.parent.absolute(), path.name)
        if data is None: raise ValueError(f'missing input: {path}')
        return data
    archive = read_safe(args.baseline_root.absolute(), 'docs/data/archive.json')
    latest = read_safe(args.baseline_root.absolute(), 'docs/data/latest.json')
    if archive is None or latest is None:
        raise ValueError('both complete current-main index files are required')
    payload, receipt = assemble(bounded(args.daily), bounded(args.sources), archive, latest,
                               base_main_sha=args.base_main_sha, archive_blob_sha=args.archive_blob_sha,
                               latest_blob_sha=args.latest_blob_sha,
                               markdown_bytes=bounded(args.markdown) if args.markdown else None)
    write_new_tree(payload, args.out_root)
    print(json.dumps({**receipt, 'candidate_root': str(args.out_root)}, ensure_ascii=False, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
