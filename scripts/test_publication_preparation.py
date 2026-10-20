#!/usr/bin/env python3
"""Fault-injection tests for offline assembly; no live credentials or publishers."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from publication_checkpoint import inspect_bundle, pack, paths_for, verify_checkpoint, classify_failure
from prepare_publication import assemble, git_blob_sha, index_entry, json_bytes, render_markdown, write_new_tree

DAY='2026-10-20'; BASE='a'*40

def fixture(day=DAY):
    order=[f'section_{i}' for i in range(1,16)]
    daily={'schema_version':'1.1.0','date':day,'edition':'Morning Official','edition_status':'official',
           'source_mode':'native_daily','last_updated':day+'T09:41:18+08:00',
           'data_cutoff_sgt':day+' 09:41 SGT','data_cutoff_et':'2026-10-19 21:41 EDT',
           'sources_path':f'data/sources/{day}.json','sources':['S01'],
           'thesis':'Canonical thesis remains exactly unchanged.',
           'dominant_narrative':'Canonical narrative remains exactly unchanged.',
           'market_regime':{'overall':'Mixed'},'section_order':order,
           'sections':{key:{'number':i,'title':f'Title {i:02d}.','summary':f'Body {i}.'} for i,key in enumerate(order,1)},
           'top_catalysts':[{'event':f'Event {i}.','sources':['S01']} for i in range(3)],
           'top_risks':[{'risk':f'Risk {i}.'} for i in range(3)],
           'publication_cycle':{'status':'official','cycle':'morning','is_final':True,'archive_eligible':True,'market_lens_native_eligible':True}}
    sources={'date':day,'sources':[{'id':'S01','source_url':'https://example.org/evidence'}]}
    prior=deepcopy(daily);prior['date']='2026-10-18';prior['last_updated']='2026-10-18T10:44:00+08:00'
    latest=index_entry(prior); archive={'schema_version':'1.1.0','updated_at':prior['last_updated'],
                                      'entries':[{k:v for k,v in latest.items() if k!='schema_version'}]}
    return daily,sources,archive,latest

def ready_parts():
    d,s,a,l=fixture(); b=[json_bytes(v) for v in [d,s,a,l]]
    return assemble(*b,base_main_sha=BASE,archive_blob_sha=git_blob_sha(b[2]),latest_blob_sha=git_blob_sha(b[3]))

class PreparationTests(unittest.TestCase):
    def call(self,d,s,a,l,**kw):
        b=[json_bytes(v) for v in [d,s,a,l]]
        return assemble(*b,base_main_sha=BASE,archive_blob_sha=git_blob_sha(b[2]),latest_blob_sha=git_blob_sha(b[3]),**kw)
    def test_assembled_five_files_preserve_original_content(self):
        d,s,a,l=fixture(); p,r=self.call(d,s,a,l)
        self.assertEqual(set(p),set(paths_for(DAY)))
        self.assertEqual(p[paths_for(DAY)[0]],json_bytes(d));self.assertEqual(p[paths_for(DAY)[2]],json_bytes(s))
        self.assertEqual(r['canonical_parity']['passed'],25);self.assertEqual(r['quality_parity'],'NOT_RUN')
        self.assertEqual(json.loads(p['docs/data/archive.json'])['entries'][1:],a['entries'])
    def test_original_markdown_bytes_can_be_preserved(self):
        d,s,a,l=fixture();md=render_markdown(d,s)+b'\noriginal bytes\n'
        p,_=self.call(d,s,a,l,markdown_bytes=md);self.assertEqual(p[paths_for(DAY)[1]],md)
    def test_baseline_hash_mismatch_fails(self):
        b=[json_bytes(v) for v in fixture()]
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            assemble(*b,base_main_sha=BASE,archive_blob_sha='0'*40,latest_blob_sha=git_blob_sha(b[3]))
    def test_baseline_archive_array_rejected(self):
        d,s,a,l=fixture()
        with self.assertRaisesRegex(ValueError,'root must be an object'):self.call(d,s,[],l)
    def test_baseline_latest_null_rejected(self):
        d,s,a,l=fixture()
        with self.assertRaisesRegex(ValueError,'root must be an object'):self.call(d,s,a,None)
    def test_duplicate_baseline_date_rejected(self):
        d,s,a,l=fixture();a['entries']*=2
        with self.assertRaisesRegex(ValueError,'unique'):self.call(d,s,a,l)
    def test_stale_baseline_latest_rejected(self):
        d,s,a,l=fixture();l['date']='2026-10-17'
        with self.assertRaisesRegex(ValueError,'newest'):self.call(d,s,a,l)
    def test_existing_official_never_replaced(self):
        d,s,a,l=fixture();a['entries'].insert(0,index_entry(d));l=index_entry(d)
        with self.assertRaisesRegex(ValueError,'ALREADY_ARCHIVED'):self.call(d,s,a,l)
    def test_historical_backfill_preserves_newer_latest_bytes(self):
        d,s,a,l=fixture('2026-10-17');d['edition']='Morning Historical Reconstruction'
        d['reconstruction']={'is_reconstructed':True,'reconstructed_at':'2026-10-20T11:30:00+08:00'}
        d['publication_cycle']['market_lens_native_eligible']=False;d['source_mode']='reconstructed_daily'
        p,r=self.call(d,s,a,l);self.assertEqual(p['docs/data/latest.json'],json_bytes(l))
        self.assertEqual(r['latest_date'],'2026-10-18')
    def test_false_native_reconstruction_rejected(self):
        d,s,a,l=fixture();d['reconstruction']={'is_reconstructed':True}
        with self.assertRaisesRegex(ValueError,'nonnative'):self.call(d,s,a,l)
    def test_provisional_rejected(self):
        d,s,a,l=fixture();d['publication_cycle']['is_final']=False
        with self.assertRaisesRegex(ValueError,'official/final'):self.call(d,s,a,l)
    def test_missing_source_id_rejected(self):
        d,s,a,l=fixture();d['sources'].append('S99')
        with self.assertRaisesRegex(ValueError,'unresolved'):self.call(d,s,a,l)
    def test_render_contains_all_fields_and_ordered_literals(self):
        d,s,a,l=fixture();d['sections']['section_1']['nested']={'critical':'DO NOT LOSE THIS FACT'}
        md=render_markdown(d,s).decode();self.assertIn('DO NOT LOSE THIS FACT',md)
        positions=[md.index(d['sections'][key]['title']) for key in d['section_order']]
        self.assertEqual(positions,sorted(positions))
    def test_target_existing_worktree_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,r=ready_parts();dest=Path(tmp)/'work';dest.mkdir();(dest/'original').write_text('keep')
            with self.assertRaises(FileExistsError):write_new_tree(p,dest)
            self.assertEqual((dest/'original').read_text(),'keep')
    def test_exact_five_file_tree_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,r=ready_parts();dest=Path(tmp)/'work';write_new_tree(p,dest)
            saved=pack(dest,DAY,BASE,Path(tmp)/'private')
            self.assertEqual(verify_checkpoint(saved)['diagnostics']['errors'],[])
    def test_traversal_payload_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p,r=ready_parts();p['../escape']=b'not allowed';target=Path(tmp)/'tree'
            with self.assertRaisesRegex(ValueError,'allowlist'):write_new_tree(p,target)
            self.assertFalse(target.exists());self.assertFalse((Path(tmp)/'escape').exists())
    def test_47_entry_archive_is_losslessly_extended(self):
        from datetime import date,timedelta
        d,s,a,l=fixture(); latest_day=date(2026,10,18)
        a['entries']=[{**a['entries'][0],'date':(latest_day-timedelta(days=i)).isoformat(),'untouched':i} for i in range(47)]
        p,r=self.call(d,s,a,l)
        self.assertEqual(json.loads(p['docs/data/archive.json'])['entries'][1:],a['entries'])
        self.assertEqual(r['original_archive_entries_preserved'],47)

class CheckpointHardeningTests(unittest.TestCase):
    def test_invalid_root_shapes_no_longer_look_clean(self):
        p,r=ready_parts()
        for path,data in [('docs/data/archive.json',b'[]'),('docs/data/archive.json',b'null'),
                          ('docs/data/latest.json',b'[]'),('docs/data/latest.json',b'null'),
                          (paths_for(DAY)[2],b'{}'),(paths_for(DAY)[2],b'[]')]:
            with self.subTest(path=path,data=data):
                x=dict(p);x[path]=data;self.assertTrue(inspect_bundle(x,DAY)['errors'])
    def test_invalid_utf8_saved_and_marked_failed(self):
        for name in [paths_for(DAY)[0],paths_for(DAY)[1]]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                p,r=ready_parts();p[name]=b'\xff';dest=Path(tmp)/'work';write_new_tree(p,dest)
                saved=pack(dest,DAY,BASE,Path(tmp)/'out');m=verify_checkpoint(saved)
                self.assertTrue(any('UTF-8' in e for e in m['diagnostics']['errors']))
                with zipfile.ZipFile(saved) as z:self.assertEqual(z.read(name),b'\xff')
    def test_duplicate_historical_archive_detected(self):
        p,r=ready_parts();a=json.loads(p['docs/data/archive.json']);a['entries'].append(a['entries'][-1])
        p['docs/data/archive.json']=json_bytes(a);self.assertIn('archive contains duplicate dates',inspect_bundle(p,DAY)['errors'])
    def test_out_of_order_titles_detected(self):
        p,r=ready_parts();d=json.loads(p[paths_for(DAY)[0]]);d['section_order'].reverse()
        p[paths_for(DAY)[0]]=json_bytes(d)
        self.assertIn('canonical section titles must appear in order',inspect_bundle(p,DAY)['errors'])
    def test_unresolved_nested_source_detected(self):
        p,r=ready_parts();d=json.loads(p[paths_for(DAY)[0]]);d['sections']['section_1']['sources']=['S88']
        p[paths_for(DAY)[0]]=json_bytes(d);self.assertTrue(any('S88' in e for e in inspect_bundle(p,DAY)['errors']))
    def test_chromium_timeout_not_network_retry(self):
        self.assertEqual(classify_failure('timed out',stage='chromium')['classification'],'QUALITY_FAILED')
    def test_safety_always_precedes_quality(self):
        r=classify_failure("blocked by OpenAI's safety checks",503,stage='quality')
        self.assertEqual(r['classification'],'SAFETY_BLOCKED');self.assertFalse(r['automatic_retry'])
    def test_true_connection_failure_still_distinct(self):
        self.assertEqual(classify_failure('connection reset',stage='pr')['classification'],'TRANSIENT_CONNECTION')

if __name__=='__main__':unittest.main()
