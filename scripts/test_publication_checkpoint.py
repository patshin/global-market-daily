#!/usr/bin/env python3
"""Offline regression tests: preserving work never authorizes a denied write."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from publication_checkpoint import pack, verify_checkpoint, paths_for, classify_failure

DAY = '2026-10-18'
SHA = 'a' * 40

class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / 'repo'; self.root.mkdir()
        self.out = self.base / 'out'
        order = [str(i) for i in range(15)]
        self.report = {'date': DAY, 'data_cutoff_sgt': '2026-10-18 10:44 SGT',
                       'data_cutoff_et': '2026-10-17 22:44 EDT',
                       'sources_path': f'data/sources/{DAY}.json', 'sources': ['S01'],
                       'thesis': 'fixture thesis', 'dominant_narrative': 'fixture narrative',
                       'section_order': order, 'sections': {k: {'title': f'Title {k}.'} for k in order},
                       'top_catalysts': [{'event': f'Catalyst {i}.'} for i in range(3)],
                       'top_risks': [{'risk': f'Risk {i}.'} for i in range(3)]}
        paths = paths_for(DAY)
        literal = [self.report[k] for k in ('data_cutoff_sgt','data_cutoff_et','thesis','dominant_narrative')]
        literal += [self.report['sections'][k]['title'] for k in order]
        literal += [x['event'] for x in self.report['top_catalysts']] + [x['risk'] for x in self.report['top_risks']]
        payloads = [json.dumps(self.report), '\n'.join(literal), json.dumps({'date': DAY, 'sources': [{'id':'S01','source_url':'https://example.org/source'}]}),
                    json.dumps({'entries': [{'date': DAY}]}), json.dumps({'date': DAY,
                      **dict(zip(('daily_json_path','report_path','sources_path'),[p.removeprefix('docs/') for p in paths[:3]]))})]
        for name, content in zip(paths, payloads):
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content)
    def tearDown(self): self.tmp.cleanup()
    def test_complete_exact_bytes_and_original_cutoff(self):
        result = pack(self.root, DAY, SHA, self.out)
        meta = verify_checkpoint(result)
        self.assertTrue(meta['content_complete'])
        self.assertEqual(meta['diagnostics']['errors'], [])
        self.assertEqual(meta['diagnostics']['canonical_parity']['passed'], 25)
        with zipfile.ZipFile(result) as z:
            for p in paths_for(DAY): self.assertEqual(z.read(p), (self.root/p).read_bytes())
    def test_local_is_not_persistent_or_published(self):
        m = verify_checkpoint(pack(self.root, DAY, SHA, self.out))
        self.assertEqual(m['publication_status'], 'NOT_SUBMITTED')
        self.assertEqual(m['diagnostics']['quality_parity'], 'NOT_RUN')
        self.assertIn('NOT_CONFIRMED', m['storage_status'])
    def test_same_payload_is_idempotent(self):
        p = pack(self.root, DAY, SHA, self.out); before = p.read_bytes()
        self.assertEqual(pack(self.root, DAY, SHA, self.out), p)
        self.assertEqual(p.read_bytes(), before)
    def test_changed_payload_preserved_separately(self):
        old = pack(self.root, DAY, SHA, self.out)
        p = self.root/paths_for(DAY)[1]; p.write_text(p.read_text()+'\nchange')
        new = pack(self.root, DAY, SHA, self.out)
        self.assertNotEqual(old, new); verify_checkpoint(old); verify_checkpoint(new)
    def test_partial_bundle_is_saved_not_lost(self):
        (self.root/paths_for(DAY)[2]).unlink()
        m = verify_checkpoint(pack(self.root, DAY, SHA, self.out))
        self.assertFalse(m['content_complete']); self.assertTrue(m['diagnostics']['errors'])
    def test_malformed_json_preserved_with_failure(self):
        (self.root/paths_for(DAY)[0]).write_text('{')
        m = verify_checkpoint(pack(self.root, DAY, SHA, self.out))
        self.assertTrue(any('invalid JSON' in e for e in m['diagnostics']['errors']))
    def test_parity_failure_is_not_ready(self):
        (self.root/paths_for(DAY)[1]).write_text('missing literals')
        m = verify_checkpoint(pack(self.root, DAY, SHA, self.out))
        self.assertEqual(m['diagnostics']['canonical_parity']['status'], 'FAIL')
    def test_reject_symlink(self):
        p=self.root/paths_for(DAY)[0]; p.unlink(); p.symlink_to('/etc/passwd')
        with self.assertRaises(ValueError): pack(self.root, DAY, SHA, self.out)
    def test_only_five_whitelisted_files(self):
        (self.root/'secret.txt').write_text('must never be packaged')
        with zipfile.ZipFile(pack(self.root, DAY, SHA, self.out)) as z:
            self.assertEqual(set(z.namelist()), {'manifest.json', *paths_for(DAY)})
    def test_reject_bad_date_or_sha(self):
        for day, sha in [('../other', SHA), (DAY, 'main'), ('2026-02-30',SHA)]:
            with self.assertRaises(ValueError): pack(self.root, day, sha, self.out)
    def test_corrupted_payload_is_rejected(self):
        p=pack(self.root, DAY, SHA, self.out)
        with zipfile.ZipFile(p) as z: members={n:z.read(n) for n in z.namelist()}
        members[paths_for(DAY)[0]]=b'{}'
        with zipfile.ZipFile(p,'w') as z:
            for n,b in members.items(): z.writestr(n,b)
        with self.assertRaises(ValueError): verify_checkpoint(p)
    def test_safety_block_is_terminal_even_with_503(self):
        r=classify_failure("This tool call was blocked by OpenAI's safety checks.",503)
        self.assertEqual(r['classification'],'SAFETY_BLOCKED')
        self.assertFalse(r['automatic_retry']); self.assertFalse(r['alternate_transport_allowed'])
    def test_different_failures_are_not_conflated(self):
        for message,status,expected in [('denied',403,'PERMISSION_DENIED'),('Approval required',None,'APPROVAL_REQUIRED'),('connection reset',None,'TRANSIENT_CONNECTION'),('AssertionError',None,'UNKNOWN_FAILURE')]:
            self.assertEqual(classify_failure(message,status)['classification'],expected)
    def test_duplicate_archive_is_not_ready(self):
        (self.root/paths_for(DAY)[3]).write_text(json.dumps({'entries':[{'date':DAY},{'date':DAY}]}))
        m=verify_checkpoint(pack(self.root, DAY, SHA, self.out))
        self.assertTrue(any('exactly one' in e for e in m['diagnostics']['errors']))

if __name__=='__main__': unittest.main()
