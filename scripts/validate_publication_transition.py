#!/usr/bin/env python3
"""Reject stale or downgrading scheduled publication candidates before promotion."""
import argparse
import json

def validate_transition(current, candidate):
    old_day=str(current.get('date',''));new_day=str(candidate.get('date',''))
    if not old_day or not new_day:
        raise ValueError('both publication pointers must carry a date')
    if new_day >= '2026-10-08':
        if candidate.get('publication_cycle') != 'morning' or candidate.get('edition_status') != 'official':
            raise ValueError('morning-only policy requires a canonical official morning candidate')
    if new_day < old_day:
        raise ValueError(f'stale candidate {new_day} would replace latest {old_day}')
    if new_day == old_day:
        old_final=current.get('edition_status')=='official'
        new_final=candidate.get('edition_status')=='official'
        if old_final and not new_final:
            raise ValueError('a provisional candidate cannot replace an official edition')
        if old_final and new_final and current.get('edition')!='Morning Fallback Final':
            raise ValueError('this date already has an official edition; use an explicitly reviewed correction PR')
    return True

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('current');p.add_argument('candidate');a=p.parse_args()
    validate_transition(json.load(open(a.current)),json.load(open(a.candidate)))
    print('PUBLICATION TRANSITION PASSED')
