#!/usr/bin/env python3
"""Pure DOM assertions only. These tests never claim to execute Chromium."""
import unittest
from verify_candidate_browser import check_dom

class BrowserContractTests(unittest.TestCase):
    def setUp(self):
        self.latest={'date':'2026-10-20','thesis':'A & B < C'}
        self.html='''<html data-gmd-editorial-ready="true" data-gmd-signal-count="6" data-gmd-signal-facts-distinct="true" data-gmd-horizontal-overflow="false" data-gmd-watch-count="3"><body><main id="report-shell"><h1 id="edition-title">2026-10-20 · Morning Official</h1><p id="thesis">A &amp; B &lt; C</p></main><div id="error-state" hidden></div></body></html>'''
    def check(self,html,report=None):check_dom(html,self.latest,report or {},{},'','fixture')
    def test_valid_visible_canonical_content(self):self.check(self.html)
    def test_date_hidden_elsewhere_cannot_mask_stale_title(self):
        html=self.html.replace('2026-10-20 · Morning Official','2026-10-18 · Morning Official')+'<!-- 2026-10-20 -->'
        with self.assertRaises(AssertionError):self.check(html)
    def test_stale_thesis_cannot_pass(self):
        with self.assertRaises(AssertionError):self.check(self.html.replace('A &amp; B &lt; C','Stale thesis'))
    def test_hidden_report_cannot_pass(self):
        with self.assertRaises(AssertionError):self.check(self.html.replace('id="report-shell"','id="report-shell" hidden'))
    def test_visible_error_cannot_pass(self):
        with self.assertRaises(AssertionError):self.check(self.html.replace('id="error-state" hidden','id="error-state"'))
    def test_missing_signal_still_fails(self):
        with self.assertRaises(AssertionError):self.check(self.html.replace('data-gmd-signal-count="6"','data-gmd-signal-count="5"'))
    def test_reconstructed_requires_disclosure(self):
        with self.assertRaises(AssertionError):self.check(self.html,{'reconstruction':{'is_reconstructed':True}})
        self.check(self.html+'历史补档，并非当日发布',{'reconstruction':{'is_reconstructed':True}})

if __name__=='__main__':unittest.main()
