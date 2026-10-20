#!/usr/bin/env python3
"""Nested regime shape used by actual daily JSON, not simplified test fixtures."""
import json
import unittest
from prepare_publication import assemble, git_blob_sha, json_bytes
from test_publication_preparation import fixture, BASE

class RealShapeTests(unittest.TestCase):
    def prepare(self, report, sources, archive, latest):
        payload=[json_bytes(v) for v in (report,sources,archive,latest)]
        return assemble(*payload,base_main_sha=BASE,
                        archive_blob_sha=git_blob_sha(payload[2]),
                        latest_blob_sha=git_blob_sha(payload[3]))
    def test_nested_regime_state_flattens_into_index(self):
        report,sources,archive,latest=fixture()
        report['market_regime']['overall']={'state':'Mixed','evidence':'Observed facts'}
        payload,_=self.prepare(report,sources,archive,latest)
        self.assertEqual(json.loads(payload['docs/data/latest.json'])['overall_regime'],'Mixed')
        self.assertEqual(json.loads(payload['docs/data/archive.json'])['entries'][0]['overall_regime'],'Mixed')
    def test_missing_regime_state_fails(self):
        report,sources,archive,latest=fixture()
        report['market_regime']['overall']={'evidence':'No label'}
        with self.assertRaisesRegex(ValueError,'state label'):
            self.prepare(report,sources,archive,latest)

if __name__=='__main__':unittest.main()
