from copy import deepcopy
from validate_reconstruction import check_report
report={'date':'2026-10-02','edition':'Historical Reconstruction','data_cutoff_sgt':'2026-10-02 18:00 SGT','source_mode':'reconstructed_daily','reconstruction':{'is_reconstructed':True,'reconstructed_at':'2026-10-08T06:00:00Z','historical_cutoff_sgt':'2026-10-02 18:00 SGT','limitations':['Original snapshot unavailable']},'publication_cycle':{'is_final':True,'market_lens_native_eligible':False},'market_tape':[{'asset':'Test','recovery_observation':{'session_date':'2026-10-01','original_snapshot_recovered':False,'level':1.0,'change_1d':None,'change_5d':None}}]}
sources={'sources':[{'id':'S01','available_by_utc':'2026-10-01T20:00:00Z'}]}
assert not check_report(report,sources,{'2026-10-02'})
bad=deepcopy(report);bad['publication_cycle']['market_lens_native_eligible']=True;assert check_report(bad,sources,{'2026-10-02'})
bad=deepcopy(report);bad['market_tape'][0]['recovery_observation']['session_date']='2026-10-02';assert check_report(bad,sources,{'2026-10-02'})
bad=deepcopy(report);bad['market_tape'][0]['recovery_observation']['level']=float('nan');assert check_report(bad,sources,{'2026-10-02'})
assert check_report(report,{'sources':[{'id':'S01','available_by_utc':'2026-10-02T12:30:00Z'}]},{'2026-10-02'})
assert check_report(report,{'sources':[{'id':'S01','published_at':'2099-01-01'}]},{'2026-10-02'})
assert check_report(report,{'sources':[{'id':'S01','published_at':'unknown'}]},{'2026-10-02'})
bad=deepcopy(report);bad['market_tape']=[{'asset':'Brent','as_of':'2026-10-02 US settlement'}];assert check_report(bad,sources,{'2026-10-02'})
print('RECONSTRUCTION REGRESSION PASSED — rejects future facts, false provenance and invalid observations')
