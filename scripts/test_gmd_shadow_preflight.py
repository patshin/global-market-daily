#!/usr/bin/env python3
"""Offline fault-injection tests for the read-only GMD shadow. Stdlib only."""
from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch
import os
from pathlib import Path
from gmd_shadow_preflight import QualityStep, classify_core, classify_public, classify_pr_status, inspect_github_pr, parse_quality_commands


class ShadowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        p = self.root / 'docs/data/daily'
        p.mkdir(parents=True)
        (self.root / 'docs/data/trends').mkdir()
        self.day = '2026-11-02'
        latest = {'date': self.day, 'thesis': 'Test publication thesis',
                  'dominant_narrative': 'Narrative', 'source_mode': 'native_daily',
                  'daily_json_path': 'data/daily/2026-11-02.json',
                  'report_path': 'reports/2026/11/2026-11-02.md',
                  'sources_path': 'data/sources/2026-11-02.json', 'edition_status': 'official'}
        report = {'date': self.day, 'thesis': latest['thesis'], 'edition': 'Morning Official',
                  'edition_status': 'official', 'source_mode': 'native_daily',
                  'publication_cycle': {'cycle': 'morning', 'is_final': True,
                                        'market_lens_native_eligible': True}}
        archive = {'entries': [{'date': self.day}]}
        lens = {'days': [{'date': self.day, 'source_mode': 'native_daily'}]}
        self.write('docs/data/latest.json', latest)
        self.write('docs/data/daily/2026-11-02.json', report)
        self.write('docs/data/archive.json', archive)
        self.write('docs/data/trends/rolling-30d.json', lens)
        self.latest = latest

    def write(self, relative: str, data: dict):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    def test_current_native(self):
        state = classify_core(self.root, self.day)
        self.assertEqual(state['status'], 'CURRENT_NATIVE_OFFICIAL')
        self.assertEqual(state['lens_status'], 'CURRENT_SOURCE_REPRESENTED')

    def test_stale_main(self):
        self.assertEqual(classify_core(self.root, '2026-11-03')['status'], 'STALE_MAIN')

    def test_historical_is_not_native(self):
        daily = self.root / 'docs/data/daily/2026-11-02.json'
        doc = json.loads(daily.read_text())
        doc['source_mode'] = 'reconstructed_daily'
        doc['reconstruction'] = {'is_reconstructed': True}
        doc['publication_cycle']['market_lens_native_eligible'] = False
        self.write('docs/data/daily/2026-11-02.json', doc)
        self.assertEqual(classify_core(self.root, self.day)['status'], 'CURRENT_HISTORICAL_BACKFILL_NOT_NATIVE')

    def test_archive_duplicate_is_invalid(self):
        self.write('docs/data/archive.json', {'entries': [{'date': self.day}, {'date': self.day}]})
        self.assertEqual(classify_core(self.root, self.day)['status'], 'MAIN_INVALID')

    def test_public_same_date_but_different_thesis(self):
        public = dict(self.latest)
        public['thesis'] = 'not the canonical thesis'
        self.assertEqual(classify_public(self.latest, public, self.day)['status'], 'PUBLIC_DRIFT')

    def test_public_stale_independent_of_main(self):
        public = dict(self.latest)
        public['date'] = '2026-11-01'
        self.assertEqual(classify_public(self.latest, public, self.day)['status'], 'PUBLIC_LAGS_MAIN')

    def test_public_backfill_not_native(self):
        local = dict(self.latest, source_mode='reconstructed_daily')
        self.assertEqual(classify_public(local, dict(local), self.day)['status'], 'PUBLIC_CONSISTENT_BUT_NOT_NATIVE_CURRENT')

    def test_no_pr_vs_failed_ci_and_green(self):
        self.assertEqual(classify_pr_status([], [], self.day)['status'], 'NO_SAME_DATE_PUBLISH_PR')
        pr = {'title': f'GMD Publish {self.day} Morning', 'number': 12,
              'state': 'open', 'merged_at': None,
              'head': {'ref': f'publish/gmd-{self.day}-morning', 'sha': 'abc'},
              'base': {'ref': 'main'}}
        fail = {'name': 'Publication Quality Gate', 'event': 'pull_request',
                'head_sha': 'abc', 'status': 'completed', 'conclusion': 'failure'}
        self.assertEqual(classify_pr_status([pr], [fail], self.day)['status'], 'PR_QUALITY_FAILED')
        success = dict(fail, conclusion='success')
        self.assertEqual(classify_pr_status([pr], [success], self.day)['status'], 'PR_GREEN_AWAITING_PROMOTION')
        self.assertEqual(classify_pr_status([pr, pr], [], self.day)['status'], 'DUPLICATE_SAME_DATE_PRS')

    def test_github_pr_search_is_bounded_and_exact(self):
        class Response:
            def __init__(self, payload):
                self.payload = json.dumps(payload).encode('utf-8')
            def __enter__(self): return self
            def __exit__(self, *args): return None
            def read(self, n): return self.payload
        urls = []
        def fake_open(request, timeout):
            urls.append(request.full_url)
            return Response({'total_count': 0, 'items': []})
        with patch.dict(os.environ, {'GH_TOKEN': 'unit-test-only',
                                     'GITHUB_REPOSITORY': 'patshin/global-market-daily'}):
            with patch('gmd_shadow_preflight.urlopen', side_effect=fake_open):
                state = inspect_github_pr(self.day)
        self.assertEqual(state['status'], 'NO_SAME_DATE_PUBLISH_PR')
        self.assertEqual(len(urls), 1)
        self.assertIn('/search/issues?', urls[0])
        self.assertIn('GMD+Publish+', urls[0])

    def test_quality_parser_mandatory_gate_enforced(self):
        with self.assertRaisesRegex(ValueError, 'missing mandatory'):
            parse_quality_commands('jobs:\n  validate:\n    steps:\n      - name: One\n        run: echo ok\n')

    def test_quality_parser_current_repo(self):
        workflow = Path(__file__).resolve().parents[1] / '.github/workflows/quality.yml'
        if not workflow.exists():
            self.skipTest('Full repository checkout unavailable')
        steps = parse_quality_commands(workflow.read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(steps), 12)
        self.assertTrue(any('verify_candidate_browser.py' in x.command for x in steps))
        self.assertTrue(any('validate_publish_v2.py' in x.command for x in steps))
        self.assertTrue(any('node --check' in x.command for x in steps))


if __name__ == '__main__':
    unittest.main(verbosity=2)
